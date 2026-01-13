"""财务报表和欠费追踪页面"""
import streamlit as st
import pandas as pd
import datetime
from models.base import SessionLocal
from models.entities import Room, Bill, PaymentRecord
from sqlalchemy.sql import func, desc
from utils.helpers import format_money

def page_payment_reconciliation(user, role):
    """收款对账单"""
    st.title("💳 收款对账单")
    if role not in ['管理员', '财务']:
        st.error("⛔️ 权限不足")
        return
    
    s = SessionLocal()
    try:
        col1, col2 = st.columns(2)
        start_date = col1.date_input("开始日期", value=datetime.datetime.now().replace(day=1))
        end_date = col2.date_input("结束日期", value=datetime.datetime.now())
        
        start_datetime = datetime.datetime.combine(start_date, datetime.time.min)
        end_datetime = datetime.datetime.combine(end_date, datetime.time.max)
        
        payments = s.query(PaymentRecord).filter(
            PaymentRecord.created_at >= start_datetime, PaymentRecord.created_at <= end_datetime
        ).order_by(PaymentRecord.created_at).all()
        
        if not payments:
            st.info("该期间无收款记录")
            return
        
        st.markdown("### 💰 按支付方式统计")
        payment_by_method = {}
        for p in payments:
            method = p.pay_method or "未知"
            payment_by_method[method] = payment_by_method.get(method, 0.0) + p.amount
        
        st.dataframe(pd.DataFrame([{"支付方式": m, "金额": a} for m, a in payment_by_method.items()]), use_container_width=True)
        st.metric("收款总额", format_money(sum(p.amount for p in payments)), delta=f"共 {len(payments)} 笔")
    finally:
        s.close()

def page_arrears_tracking(user, role):
    """欠费追踪看板"""
    st.title("📊 欠费追踪看板")
    
    s = SessionLocal()
    try:
        st.markdown("### 📈 欠费总览")
        total_arrears = s.query(func.sum(Bill.amount_due - Bill.amount_paid - Bill.discount)).filter(
            Bill.status != '已缴', Bill.status != '作废').scalar() or 0.0
        arrears_room_count = s.query(Room.id).join(Bill, Room.id == Bill.room_id).filter(
            Bill.status != '已缴', Bill.status != '作废').distinct().count()
        total_room_count = s.query(Room).filter(Room.is_deleted.is_(False)).count()
        
        col1, col2, col3 = st.columns(3)
        col1.metric("欠费总额", format_money(total_arrears), delta_color="inverse")
        col2.metric("欠费房产数", arrears_room_count)
        col3.metric("总房产数", total_room_count)
        
        st.markdown("### 🏆 欠费房产排行 (Top 20)")
        arrears_ranking = s.query(Room.room_number, Room.owner_name, Room.owner_phone,
            func.sum(Bill.amount_due - Bill.amount_paid - Bill.discount).label('total_arrears')
        ).join(Bill, Room.id == Bill.room_id).filter(Bill.status != '已缴', Bill.status != '作废'
        ).group_by(Room.room_number, Room.owner_name, Room.owner_phone).order_by(desc('total_arrears')).limit(20).all()
        
        if arrears_ranking:
            st.dataframe(pd.DataFrame([{"排名": i+1, "房号": r.room_number, "业主": r.owner_name,
                "联系电话": r.owner_phone or "未填写", "欠费金额": float(r.total_arrears)}
                for i, r in enumerate(arrears_ranking)]), use_container_width=True)
    finally:
        s.close()

def page_financial_reports(user, role):
    """财务报表中心"""
    st.title("📊 财务报表中心")
    if role not in ['管理员', '财务']:
        st.error("⛔️ 权限不足")
        return
    
    s = SessionLocal()
    try:
        tab1, tab2 = st.tabs(["利润表", "账期对比"])
        
        with tab1:
            st.markdown("### 📋 利润表（简化版）")
            col1, col2 = st.columns(2)
            start_period = col1.text_input("开始账期", value=(datetime.datetime.now() - datetime.timedelta(days=90)).strftime("%Y-%m"))
            end_period = col2.text_input("结束账期", value=datetime.datetime.now().strftime("%Y-%m"))
            
            revenue_due = s.query(func.sum(Bill.amount_due)).filter(Bill.period >= start_period, Bill.period <= end_period).scalar() or 0.0
            discount = s.query(func.sum(Bill.discount)).filter(Bill.period >= start_period, Bill.period <= end_period).scalar() or 0.0
            revenue_received = s.query(func.sum(Bill.amount_paid)).filter(Bill.period >= start_period, Bill.period <= end_period).scalar() or 0.0
            
            st.dataframe(pd.DataFrame([
                {"项目": "应收收入", "金额": revenue_due},
                {"项目": "减：减免金额", "金额": discount},
                {"项目": "已收款金额", "金额": revenue_received},
                {"项目": "未收款金额", "金额": revenue_due - discount - revenue_received}
            ]), use_container_width=True)
        
        with tab2:
            st.markdown("### 📋 账期对比分析")
            periods = s.query(Bill.period).distinct().order_by(Bill.period).all()
            period_list = [p[0] for p in periods if p[0]]
            if len(period_list) >= 2:
                col1, col2 = st.columns(2)
                period1 = col1.selectbox("账期1", period_list, index=max(0, len(period_list)-2))
                period2 = col2.selectbox("账期2", period_list, index=len(period_list)-1)
                
                def get_data(p):
                    due = s.query(func.sum(Bill.amount_due)).filter(Bill.period == p).scalar() or 0.0
                    paid = s.query(func.sum(Bill.amount_paid)).filter(Bill.period == p).scalar() or 0.0
                    return {"应收": due, "实收": paid, "收缴率": (paid/due*100) if due > 0 else 0}
                
                d1, d2 = get_data(period1), get_data(period2)
                st.dataframe(pd.DataFrame([
                    {"指标": "应收金额", period1: d1["应收"], period2: d2["应收"]},
                    {"指标": "实收金额", period1: d1["实收"], period2: d2["实收"]},
                    {"指标": "收缴率(%)", period1: d1["收缴率"], period2: d2["收缴率"]}
                ]), use_container_width=True)
    finally:
        s.close()
