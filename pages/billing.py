"""财务管理页面"""
import streamlit as st
import datetime
from models import SessionLocal, Bill, FeeType, PeriodClose, Invoice, DiscountRequest, AdjustmentEntry
from services.audit import AuditService
from services.billing import BillingService
from utils.helpers import format_money
from utils.transaction import transaction_scope


def page_billing(user, role):
    st.title("📝 财务管理中心")
    if role not in ['管理员', '项目财务', '审批员']:
        st.error("⛔️ 权限不足")
        return
    
    s = SessionLocal()
    try:
        t1, t2, t3, t4 = st.tabs(["⚡ 批量生成账单", "📅 月度关账", "🧾 发票管理", "✅ 减免审批"])
        
        with t1:
            fees = [f.name for f in s.query(FeeType).all()] or ["物业费"]
            
            st.markdown("### 📋 批量生成账单")
            with st.form("batch_billing"):
                c1, c2 = st.columns(2)
                gen_mode = c1.radio("生成依据", ["按档案预设金额", "按单价x面积"])
                b_fee = c1.selectbox("费用类型", fees)
                gen_all = c2.checkbox("生成所有费用项目", value=True)
                b_price = c2.number_input("单价(元/㎡)", value=2.0) if "单价" in gen_mode else None
                b_period = c2.text_input("账期", value=datetime.datetime.now().strftime("%Y-%m"))
                
                if st.form_submit_button("🚀 全量生成"):
                    try:
                        with transaction_scope() as (s_trx, audit_buffer):
                            result = BillingService.generate_bills_for_period(
                                s_trx, b_period, b_fee, user, gen_all, b_price
                            )
                            AuditService.log_deferred(s_trx, audit_buffer, user, "批量计费", "全小区", result)
                        st.success(f"生成 {result['count']} 笔，合计 {format_money(result['total'])}")
                    except Exception as e:
                        st.error(str(e))
            
            st.markdown("---")
            st.markdown("### ✍️ 手动开账单")
            from models import Room
            rooms = s.query(Room).filter(Room.is_deleted == False).all()
            if not rooms:
                st.warning("暂无房产档案")
            else:
                with st.form("manual_billing"):
                    room_map = {r.room_number: r for r in rooms}
                    selected_room = st.selectbox("选择房号", list(room_map.keys()))
                    c1, c2 = st.columns(2)
                    manual_fee = c1.selectbox("费用类型", fees, key="manual_fee")
                    manual_period = c2.text_input("账期(YYYY-MM)", value=datetime.datetime.now().strftime("%Y-%m"), key="manual_period")
                    manual_amount = st.number_input("应收金额", min_value=0.0, step=0.01, key="manual_amount")
                    manual_remark = st.text_input("备注（可选）", key="manual_remark")
                    
                    if st.form_submit_button("✅ 创建账单", use_container_width=True):
                        if manual_amount <= 0:
                            st.error("应收金额必须大于0")
                        else:
                            try:
                                with transaction_scope() as (s_trx, audit_buffer):
                                    room = room_map[selected_room]
                                    bill = Bill(
                                        room_id=room.id,
                                        fee_type=manual_fee,
                                        period=manual_period,
                                        accounting_period=manual_period,
                                        amount_due=manual_amount,
                                        amount_paid=0.0,
                                        discount=0.0,
                                        status='未缴',
                                        operator=user,
                                        remark=manual_remark or '手动开单'
                                    )
                                    s_trx.add(bill)
                                    AuditService.log_deferred(s_trx, audit_buffer, user, "手动开单", 
                                                            selected_room, {"fee": manual_fee, "period": manual_period, "amount": manual_amount})
                                st.success(f"账单创建成功：{selected_room} | {manual_fee} | {manual_period} | {format_money(manual_amount)}")
                            except Exception as e:
                                st.error(f"创建失败: {e}")
        
        with t2:
            st.subheader("📅 月度关账")
            period = st.text_input("账期(YYYY-MM)", value=datetime.datetime.now().strftime("%Y-%m"))
            c1, c2 = st.columns(2)
            if c1.button("关账"):
                try:
                    with transaction_scope() as (s_trx, audit_buffer):
                        pc = s_trx.query(PeriodClose).filter_by(period=period).first()
                        now = datetime.datetime.now()
                        if not pc:
                            pc = PeriodClose(period=period, closed=True, closed_at=now)
                            s_trx.add(pc)
                        else:
                            pc.closed = True
                            pc.closed_at = now
                        AuditService.log_deferred(s_trx, audit_buffer, user, "关账", period, {})
                    st.success("已关账")
                except Exception as e:
                    st.error(str(e))
            if c2.button("解锁"):
                try:
                    with transaction_scope() as (s_trx, audit_buffer):
                        pc = s_trx.query(PeriodClose).filter_by(period=period).first()
                        if pc:
                            pc.closed = False
                            AuditService.log_deferred(s_trx, audit_buffer, user, "解锁账期", period, {})
                            st.warning("已解锁")
                except Exception as e:
                    st.error(str(e))
        
        with t3:
            st.subheader("🧾 发票管理")
            # 查询已缴费但未开票的账单
            invoiced_bills = s.query(Invoice.bill_id).subquery()
            paid_bills = s.query(Bill).filter(Bill.status == '已缴', ~Bill.id.in_(invoiced_bills)).all()
            
            if not paid_bills:
                st.info("暂无可开票账单")
            else:
                import uuid
                sel_bill = st.selectbox("选择账单", paid_bills, format_func=lambda b: f"{b.room.room_number if b.room else ''} | {b.fee_type} | {b.period} | ¥{b.amount_paid:.2f}")
                if sel_bill:
                    fee = s.query(FeeType).filter(FeeType.name == sel_bill.fee_type).first()
                    rate = float(fee.tax_rate) if fee else 0.0
                    # 价内税计算：含税金额拆分
                    amt_incl = float(sel_bill.amount_paid)
                    amt_excl = amt_incl / (1 + rate) if rate > 0 else amt_incl
                    tax_amt = amt_incl - amt_excl
                    
                    st.write(f"税率: {rate*100:.1f}% | 不含税: ¥{amt_excl:.2f} | 税额: ¥{tax_amt:.2f} | 含税: ¥{amt_incl:.2f}")
                    inv_no = st.text_input("发票编号", value=f"INV-{uuid.uuid4().hex[:8].upper()}")
                    title = st.text_input("发票抬头", value=sel_bill.room.owner_name if sel_bill.room else "")
                    
                    if st.button("开具发票"):
                        try:
                            with transaction_scope() as (s_trx, audit_buffer):
                                inv = Invoice(bill_id=sel_bill.id, invoice_no=inv_no, title=title, tax_rate=rate,
                                             amount_excl_tax=amt_excl, tax_amount=tax_amt, amount_incl_tax=amt_incl, status='已开具')
                                s_trx.add(inv)
                                AuditService.log_deferred(s_trx, audit_buffer, user, "开票", f"Bill:{sel_bill.id}", 
                                                        {"inv_no": inv_no, "rate": rate, "amt_excl": amt_excl, "tax": tax_amt})
                            st.success("发票已开具")
                            st.rerun()
                        except Exception as e:
                            st.error(f"开票失败: {e}")
        
        with t4:
            st.subheader("✅ 减免审批")
            pending = s.query(DiscountRequest).filter(DiscountRequest.status == '待审核').all()
            if not pending:
                st.info("暂无待审核申请")
            else:
                for r in pending:
                    b = s.query(Bill).get(r.bill_id)
                    with st.expander(f"申请ID:{r.id} | 金额:{format_money(r.amount)} | 申请人:{r.requested_by}"):
                        st.write(f"账单: {b.fee_type} | {b.period}")
                        st.write(f"理由: {r.reason}")
                        c1, c2 = st.columns(2)
                        if c1.button("通过", key=f"approve_{r.id}"):
                            try:
                                with transaction_scope() as (s_trx, audit_buffer):
                                    req = s_trx.query(DiscountRequest).get(r.id)
                                    bill = s_trx.query(Bill).get(req.bill_id)
                                    bill.discount += float(req.amount)
                                    s_trx.add(AdjustmentEntry(bill_id=bill.id, amount=float(req.amount),
                                                            reason=req.reason, approved_by=user))
                                    req.status = '已通过'
                                    req.approved_by = user
                                    req.approved_at = datetime.datetime.now()
                                    AuditService.log_deferred(s_trx, audit_buffer, user, "审批通过减免",
                                                            f"Bill:{bill.id}", {"amount": float(req.amount)})
                                st.success("已通过")
                                st.rerun()
                            except Exception as e:
                                st.error(str(e))
                        if c2.button("拒绝", key=f"reject_{r.id}"):
                            try:
                                with transaction_scope() as (s_trx, audit_buffer):
                                    req = s_trx.query(DiscountRequest).get(r.id)
                                    req.status = '已拒绝'
                                    req.approved_by = user
                                    AuditService.log_deferred(s_trx, audit_buffer, user, "拒绝减免",
                                                            f"Bill:{req.bill_id}", {})
                                st.warning("已拒绝")
                                st.rerun()
                            except Exception as e:
                                st.error(str(e))
    finally:
        s.close()
