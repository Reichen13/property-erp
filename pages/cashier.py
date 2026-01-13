"""收银台页面"""
import streamlit as st
import datetime
import time
from decimal import Decimal
from models import SessionLocal, Room, Bill, PaymentRecord
from services.audit import AuditService
from services.ledger import LedgerService
from utils.helpers import to_decimal, format_money
from utils.transaction import transaction_scope


def generate_receipt_html(data):
    items_html = "".join([f"<tr><td>{i['name']}</td><td style='text-align:right'>{i['amount']}</td></tr>" for i in data['items']])
    return f"""
    <div style="border:1px solid #aaa; padding:15px; width:300px; font-family:monospace; background:#fff; color:#000;">
      <h3 style="text-align:center; margin:0;">世纪名城物业中心</h3>
      <p style="text-align:center; font-size:12px; border-bottom:1px dashed #000; padding-bottom:10px;">收款收据</p>
      <p>房号: {data['room']}<br>业主: {data['owner']}<br>时间: {data['time']}</p>
      <table style="width:100%; font-size:14px; border-bottom:1px dashed #000;">{items_html}</table>
      <h3 style="text-align:right; margin-top:10px;">实收: {data['total']}</h3>
      <p style="font-size:12px;">收银员: {data['operator']}</p>
    </div>
    """


def page_cashier(user, role):
    st.title("💸 收银台")
    s = SessionLocal()
    try:
        rooms = s.query(Room).filter(not Room.is_deleted).all()
        if not rooms:
            st.warning("暂无档案数据")
            return
        
        r_map = {r.room_number: r for r in rooms}
        sel_no = st.selectbox("搜索/选择房号", list(r_map.keys()))
        curr = r_map[sel_no]
        st.write(f"业主: {curr.owner_name} | 余额: {format_money(curr.balance)}")
        
        # 充值
        with st.expander("💰 钱包充值", expanded=True):
            recharge_val = st.number_input("充值金额", min_value=0.0, step=100.0)
            pay_method = st.selectbox("收款方式", ["微信", "支付宝", "现金", "银行转账"])
            
            if st.button("确认充值", use_container_width=True):
                if recharge_val <= 0:
                    st.error("金额必须大于0")
                else:
                    try:
                        with transaction_scope() as (s_trx, audit_buffer):
                            room = s_trx.query(Room).get(curr.id)
                            room.balance += float(recharge_val)
                            pr = PaymentRecord(room_id=curr.id, amount=float(recharge_val), 
                                             biz_type='充值', pay_method=pay_method, operator=user)
                            s_trx.add(pr)
                            s_trx.flush()
                            period = datetime.datetime.now().strftime("%Y-%m")
                            # 复式记账：借方=现金(1)，贷方=预收账款(3)
                            LedgerService.post_double_entry(s_trx, period, 1, 3, float(recharge_val),
                                                           room_id=curr.id, ref_payment_id=pr.id)
                            AuditService.log_deferred(s_trx, audit_buffer, user, "充值", curr.room_number,
                                                     {"金额": str(recharge_val), "方式": pay_method})
                        st.success("充值成功")
                        time.sleep(0.5)
                        st.rerun()
                    except Exception as e:
                        st.error(f"充值失败: {e}")
        
        # 待缴费账单
        st.markdown("### 🧾 待缴费账单")
        bills = s.query(Bill).filter(Bill.room_id == curr.id, Bill.status != '已缴', Bill.status != '作废').all()
        
        valid_rows = []
        for b in bills:
            owe = to_decimal(b.amount_due) - to_decimal(b.amount_paid) - to_decimal(b.discount)
            if owe > Decimal('0.01'):
                valid_rows.append((b, owe))
        
        if not valid_rows:
            st.success("✅ 当前无欠费")
        else:
            import pandas as pd
            data = [{"选中": False, "ID": b.id, "项目": b.fee_type, "账期": b.period, 
                    "剩余欠费": float(owe)} for b, owe in valid_rows]
            df = pd.DataFrame(data)
            edited = st.data_editor(df, column_config={
                "选中": st.column_config.CheckboxColumn(required=True),
                "剩余欠费": st.column_config.NumberColumn(format="¥%.2f", disabled=True)
            }, disabled=["ID", "项目", "账期", "剩余欠费"], hide_index=True)
            
            selected = edited[edited["选中"]]
            if not selected.empty:
                to_pay = sum([to_decimal(row['剩余欠费']) for _, row in selected.iterrows()])
                st.markdown(f"#### 待付: :red[{format_money(to_pay)}]")
                
                pay_way = st.radio("支付方式", ["余额抵扣", "微信/支付宝"], horizontal=True)
                can_pay = True
                if pay_way == "余额抵扣" and to_decimal(curr.balance) < to_pay:
                    st.error(f"余额不足 (当前: {format_money(curr.balance)})")
                    can_pay = False
                
                if st.button("🚀 确认支付", type="primary", disabled=not can_pay):
                    try:
                        with transaction_scope() as (s_trx, audit_buffer):
                            for _, row in selected.iterrows():
                                bill = s_trx.query(Bill).get(row['ID'])
                                pay_val = to_decimal(row['剩余欠费'])
                                bill.amount_paid += float(pay_val)
                                owe_after = to_decimal(bill.amount_due) - to_decimal(bill.amount_paid) - to_decimal(bill.discount)
                                bill.status = '已缴' if owe_after < Decimal('0.01') else '部分已缴'
                                # 复式记账：借方=预收账款(3)，贷方=物业费收入(2)
                                LedgerService.post_double_entry(s_trx, bill.period, 3, 2, float(pay_val),
                                                               room_id=curr.id, ref_bill_id=bill.id)
                            
                            if pay_way == "余额抵扣":
                                room = s_trx.query(Room).get(curr.id)
                                room.balance -= float(to_pay)
                            
                            s_trx.add(PaymentRecord(room_id=curr.id, amount=float(to_pay),
                                                   biz_type='缴费', pay_method=pay_way, operator=user))
                            AuditService.log_deferred(s_trx, audit_buffer, user, "收费", curr.room_number,
                                                     {"总额": str(to_pay), "方式": pay_way})
                        st.success("支付成功")
                        time.sleep(0.5)
                        st.rerun()
                    except Exception as e:
                        st.error(f"支付失败: {e}")
    finally:
        s.close()
