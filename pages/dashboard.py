"""运营驾驶舱页面"""
import streamlit as st
import datetime
from sqlalchemy.sql import func
from models import SessionLocal, PaymentRecord, Bill, Room
from utils.helpers import to_decimal, format_money


def page_dashboard(user, role):
    st.title("📊 运营驾驶舱")
    s = SessionLocal()
    try:
        c1, c2 = st.columns(2)
        today = datetime.date.today()
        first_day = today.replace(day=1)
        q_start = c1.date_input("开始日期", first_day)
        q_end = c2.date_input("结束日期", today)
        st.divider()
        
        period_revenue = to_decimal(
            s.query(func.sum(PaymentRecord.amount))
             .filter(PaymentRecord.amount > 0)
             .filter(PaymentRecord.pay_method != '期初导入')
             .filter(func.date(PaymentRecord.created_at) >= q_start)
             .filter(func.date(PaymentRecord.created_at) <= q_end)
             .scalar() or 0
        )
        period_loss = to_decimal(
            s.query(func.sum(Bill.discount))
             .filter(func.date(Bill.created_at) >= q_start)
             .filter(func.date(Bill.created_at) <= q_end)
             .scalar() or 0
        )
        period_arrears = to_decimal(
            s.query(func.sum(Bill.amount_due - Bill.amount_paid - Bill.discount))
             .filter(Bill.status != '作废')
             .filter(func.date(Bill.created_at) >= q_start)
             .filter(func.date(Bill.created_at) <= q_end)
             .scalar() or 0
        )
        total_prepay = to_decimal(s.query(func.sum(Room.balance)).scalar() or 0)
        
        k1, k2, k3, k4 = st.columns(4)
        k1.metric("💰 期间实收", format_money(period_revenue))
        k2.metric("📉 期间折扣", format_money(period_loss), delta_color="inverse")
        k3.metric("🚨 期间新增欠费", format_money(period_arrears), delta_color="inverse")
        k4.metric("🏦 预存余额", format_money(total_prepay))
    finally:
        s.close()
