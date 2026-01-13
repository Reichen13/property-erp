"""批量操作页面"""
import streamlit as st
import pandas as pd
import datetime
import time
from decimal import Decimal
from models.base import SessionLocal
from models.entities import Room, Bill, PaymentRecord, Invoice
from sqlalchemy.sql import func, desc
from utils.helpers import format_money, to_decimal
from utils.transaction import transaction_scope
from services.audit import AuditService
from services.ledger import LedgerService

def page_batch_operations(user, role):
    """批量操作中心"""
    st.title("⚙️ 批量操作中心")
    if role not in ['管理员', '财务']:
        st.error("⛔️ 权限不足")
        return
    
    s = SessionLocal()
    try:
        tab1, tab2, tab3, tab4 = st.tabs(["批量缴费", "批量减免", "批量开票", "批量导出"])
        
        with tab1:
            st.markdown("### 💰 批量缴费")
            periods = s.query(Bill.period).distinct().order_by(desc(Bill.period)).all()
            period_list = [p[0] for p in periods if p[0]]
            if not period_list:
                st.info("暂无账单数据")
                return
            
            selected_period = st.selectbox("选择账期", period_list)
            arrears_query = s.query(Room.id, Room.room_number, Room.owner_name,
                func.sum(Bill.amount_due - Bill.amount_paid - Bill.discount).label('arrears')
            ).join(Bill, Room.id == Bill.room_id).filter(
                Bill.period == selected_period, Bill.status != '已缴', Bill.status != '作废'
            ).group_by(Room.id, Room.room_number, Room.owner_name).all()
            
            data = [{"选中": False, "房产ID": r.id, "房号": r.room_number, "业主": r.owner_name, "欠费金额": float(r.arrears)}
                for r in arrears_query if r.arrears > 0.01]
            
            if data:
                df = pd.DataFrame(data)
                edited_df = st.data_editor(df, column_config={"选中": st.column_config.CheckboxColumn(required=True),
                    "欠费金额": st.column_config.NumberColumn(format="¥%.2f", disabled=True)},
                    disabled=["房产ID", "房号", "业主", "欠费金额"], hide_index=True, use_container_width=True)
                
                selected_rows = edited_df[edited_df["选中"]]
                if not selected_rows.empty:
                    total_amount = selected_rows["欠费金额"].sum()
                    st.markdown(f"#### 已选择 {len(selected_rows)} 个房产，合计欠费: :red[{format_money(total_amount)}]")
                    pay_method = st.selectbox("支付方式", ["微信", "支付宝", "现金", "银行转账"])
                    
                    if st.button("🚀 批量缴费", type="primary"):
                        try:
                            with transaction_scope() as (s_trx, audit_buffer):
                                count = 0
                                for _, row in selected_rows.iterrows():
                                    room_id = row['房产ID']
                                    bills = s_trx.query(Bill).filter(Bill.room_id == room_id, Bill.period == selected_period,
                                        Bill.status != '已缴', Bill.status != '作废').all()
                                    for bill in bills:
                                        owe = to_decimal(bill.amount_due) - to_decimal(bill.amount_paid) - to_decimal(bill.discount)
                                        if owe > Decimal('0.01'):
                                            bill.amount_paid += float(owe)
                                            bill.status = '已缴'
                                            # 复式记账：借方=预收账款(3)，贷方=物业费收入(2)
                                            LedgerService.post_double_entry(s_trx, bill.period, 3, 2, float(owe), room_id=room_id, ref_bill_id=bill.id)
                                    s_trx.add(PaymentRecord(room_id=room_id, amount=float(row['欠费金额']),
                                        biz_type='批量缴费', pay_method=pay_method, operator=user))
                                    count += 1
                                AuditService.log_deferred(s_trx, audit_buffer, user, "批量缴费", selected_period, {"房产数": count, "总金额": str(total_amount)})
                            st.success(f"✅ 批量缴费成功！共处理 {count} 个房产")
                            time.sleep(1)
                            st.rerun()
                        except Exception as e:
                            st.error(f"批量缴费失败: {e}")
            else:
                st.success("✅ 该账期无欠费房产")
        
        with tab2:
            st.markdown("### ➖ 批量减免")
            st.info("为多个房产批量申请减免（功能简化版）")
        
        with tab3:
            st.markdown("### 🧾 批量开票")
            # 查询已缴费但未开票的账单
            invoiced_bills = s.query(Invoice.bill_id).subquery()
            paid_bills = s.query(Bill).filter(Bill.status == '已缴', ~Bill.id.in_(invoiced_bills)).all()
            
            if not paid_bills:
                st.info("暂无可开票账单")
            else:
                data = [{"选中": False, "ID": b.id, "房号": b.room.room_number if b.room else "", 
                        "科目": b.fee_type, "账期": b.period, "金额": float(b.amount_paid)} for b in paid_bills]
                df = pd.DataFrame(data)
                edited = st.data_editor(df, column_config={"选中": st.column_config.CheckboxColumn(required=True),
                    "金额": st.column_config.NumberColumn(format="¥%.2f", disabled=True)},
                    disabled=["ID", "房号", "科目", "账期", "金额"], hide_index=True)
                
                selected = edited[edited["选中"]]
                if not selected.empty:
                    total = selected["金额"].sum()
                    st.markdown(f"#### 已选 {len(selected)} 笔，合计: :red[{format_money(total)}]")
                    inv_title = st.text_input("发票抬头", value="个人")
                    tax_rate = st.number_input("税率", min_value=0.0, max_value=0.13, value=0.0, step=0.01)
                    
                    if st.button("🚀 批量开票", type="primary"):
                        import uuid
                        try:
                            with transaction_scope() as (s_trx, audit_buffer):
                                count = 0
                                for _, row in selected.iterrows():
                                    amt_incl = row['金额']
                                    amt_excl = amt_incl / (1 + tax_rate) if tax_rate > 0 else amt_incl
                                    tax_amt = amt_incl - amt_excl
                                    inv_no = f"INV-{uuid.uuid4().hex[:8].upper()}"
                                    s_trx.add(Invoice(bill_id=int(row['ID']), invoice_no=inv_no, title=inv_title,
                                        tax_rate=tax_rate, amount_excl_tax=amt_excl, tax_amount=tax_amt, amount_incl_tax=amt_incl))
                                    count += 1
                                AuditService.log_deferred(s_trx, audit_buffer, user, "批量开票", "多账单", {"数量": count, "总额": str(total)})
                            st.success(f"✅ 已开具 {count} 张发票")
                            time.sleep(1)
                            st.rerun()
                        except Exception as e:
                            st.error(f"批量开票失败: {e}")
        
        with tab4:
            st.markdown("### 📥 批量导出")
            export_type = st.selectbox("选择导出类型", ["全部房产档案", "全部账单数据", "全部收款记录"])
            if st.button("📥 开始导出"):
                if export_type == "全部房产档案":
                    rooms = s.query(Room).filter(Room.is_deleted.is_(False)).all()
                    df_export = pd.DataFrame([{"房号": r.room_number, "业主": r.owner_name, "电话": r.owner_phone,
                        "面积": r.area, "余额": r.balance} for r in rooms])
                elif export_type == "全部账单数据":
                    bills = s.query(Bill).all()
                    df_export = pd.DataFrame([{"房号": b.room_id, "科目": b.fee_type, "账期": b.period,
                        "应缴": b.amount_due, "实缴": b.amount_paid, "状态": b.status} for b in bills])
                else:
                    payments = s.query(PaymentRecord).all()
                    df_export = pd.DataFrame([{"房号": p.room_id, "金额": p.amount, "方式": p.pay_method,
                        "时间": p.created_at.strftime('%Y-%m-%d %H:%M') if p.created_at else ""} for p in payments])
                
                filename = f"{export_type}_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
                st.download_button("⬇️ 下载CSV", df_export.to_csv(index=False).encode('utf-8-sig'), filename, "text/csv")
    finally:
        s.close()
