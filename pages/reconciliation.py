"""收费核对相关页面"""
import streamlit as st
import pandas as pd
from models.base import SessionLocal
from models.entities import Room, Bill, FeeType, LedgerEntry, PaymentRecord
from sqlalchemy.sql import func, desc
from utils.helpers import format_money

def page_reconciliation_workbench(user, role):
    """收费核对工作台"""
    st.title("🔍 收费核对工作台")
    if role not in ['管理员', '财务']:
        st.error("⛔️ 权限不足")
        return
    
    s = SessionLocal()
    try:
        periods = s.query(Bill.period).distinct().order_by(desc(Bill.period)).all()
        period_list = [p[0] for p in periods if p[0]]
        if not period_list:
            st.warning("暂无账单数据")
            return
        
        col1, col2 = st.columns(2)
        selected_period = col1.selectbox("选择账期", period_list)
        fee_types = s.query(FeeType.name).all()
        fee_list = ['全部'] + [f[0] for f in fee_types]
        selected_fee = col2.selectbox("费用类型", fee_list)
        
        query = s.query(Room.room_number, Room.owner_name, Bill.fee_type,
            func.sum(Bill.amount_due).label('total_due'),
            func.sum(Bill.amount_paid).label('total_paid'),
            func.sum(Bill.discount).label('total_discount')
        ).join(Room, Bill.room_id == Room.id).filter(Bill.period == selected_period)
        
        if selected_fee != '全部':
            query = query.filter(Bill.fee_type == selected_fee)
        
        results = query.group_by(Room.room_number, Room.owner_name, Bill.fee_type).all()
        if not results:
            st.info("该账期暂无数据")
            return
        
        data = []
        total_due_sum = total_paid_sum = total_arrears_sum = 0
        for r in results:
            due = float(r.total_due or 0)
            paid = float(r.total_paid or 0)
            discount = float(r.total_discount or 0)
            arrears = due - paid - discount
            status = "✅ 已结清" if abs(arrears) < 0.01 else ("⚠️ 部分已缴" if paid > 0 else "❌ 未缴")
            data.append({"房号": r.room_number, "业主": r.owner_name, "费用类型": r.fee_type,
                "应收金额": due, "实收金额": paid, "减免金额": discount, "欠费金额": arrears, "状态": status})
            total_due_sum += due
            total_paid_sum += paid
            total_arrears_sum += arrears
        
        st.markdown("### 📊 核对汇总")
        k1, k2, k3, k4 = st.columns(4)
        k1.metric("应收总额", format_money(total_due_sum))
        k2.metric("实收总额", format_money(total_paid_sum))
        k3.metric("欠费总额", format_money(total_arrears_sum), delta_color="inverse")
        k4.metric("收缴率", f"{(total_paid_sum/total_due_sum*100) if total_due_sum > 0 else 0:.1f}%")
        
        st.markdown("### 📋 明细数据")
        st.dataframe(pd.DataFrame(data), use_container_width=True, height=400)
    finally:
        s.close()

def page_three_way_reconciliation(user, role):
    """三方核对机制"""
    st.title("🔄 三方核对机制")
    if role not in ['管理员', '财务']:
        st.error("⛔️ 权限不足")
        return
    
    s = SessionLocal()
    try:
        st.info("三方核对：业务数据 vs 会计科目余额 vs 实际资金")
        
        st.markdown("#### 1️⃣ 房产余额 vs 预收账款科目余额")
        total_room_balance = s.query(func.sum(Room.balance)).filter(Room.is_deleted.is_(False)).scalar() or 0.0
        ledger_balance = s.query(func.sum(LedgerEntry.amount)).filter(LedgerEntry.account_id == 1).scalar() or 0.0
        diff1 = abs(total_room_balance - ledger_balance)
        
        col1, col2, col3 = st.columns(3)
        col1.metric("房产余额总和", format_money(total_room_balance))
        col2.metric("预收账款科目余额", format_money(ledger_balance))
        col3.metric("差异", format_money(diff1), delta_color="inverse")
        
        if diff1 < 0.01:
            st.success("✅ 房产余额与预收账款科目余额一致")
        else:
            st.error(f"❌ 存在差异 {format_money(diff1)}")
        
        st.markdown("#### 2️⃣ 账单应收总额")
        total_arrears = s.query(func.sum(Bill.amount_due - Bill.amount_paid - Bill.discount)).filter(
            Bill.status != '已缴', Bill.status != '作废').scalar() or 0.0
        st.metric("账单应收总额", format_money(total_arrears))
        
        st.markdown("#### 3️⃣ 收款记录统计")
        payment_stats = s.query(PaymentRecord.pay_method, func.sum(PaymentRecord.amount).label('total')
            ).group_by(PaymentRecord.pay_method).all()
        if payment_stats:
            st.dataframe(pd.DataFrame([{"支付方式": ps.pay_method or "未知", "金额": float(ps.total or 0)} for ps in payment_stats]), use_container_width=True)
    finally:
        s.close()

def page_financial_check(user, role):
    """财务勾稽关系检查"""
    st.title("⚖️ 财务勾稽关系检查")
    if role not in ['管理员', '财务']:
        st.error("⛔️ 权限不足")
        return
    
    s = SessionLocal()
    try:
        st.markdown("### 🔍 财务数据完整性检查")
        check_results = []
        
        # 检查负余额房产
        negative_balance_rooms = s.query(Room).filter(Room.balance < 0, Room.is_deleted.is_(False)).all()
        if negative_balance_rooms:
            check_results.append({"检查项": "负余额房产", "状态": "⚠️ 警告", "详情": f"发现 {len(negative_balance_rooms)} 个房产余额为负"})
        else:
            check_results.append({"检查项": "负余额房产", "状态": "✅ 通过", "详情": "无负余额房产"})
        
        # 检查超额缴费
        overpaid_bills = s.query(Bill).filter(Bill.amount_paid > Bill.amount_due).all()
        if overpaid_bills:
            check_results.append({"检查项": "超额缴费", "状态": "⚠️ 警告", "详情": f"发现 {len(overpaid_bills)} 笔账单实缴超过应缴"})
        else:
            check_results.append({"检查项": "超额缴费", "状态": "✅ 通过", "详情": "无超额缴费"})
        
        st.dataframe(pd.DataFrame(check_results), use_container_width=True)
        
        passed = len([r for r in check_results if "✅" in r['状态']])
        warning = len([r for r in check_results if "⚠️" in r['状态']])
        col1, col2 = st.columns(2)
        col1.metric("通过", passed)
        col2.metric("警告", warning, delta_color="inverse")
    finally:
        s.close()
