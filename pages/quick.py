"""快捷面板页面"""
import streamlit as st
import datetime
from models.base import SessionLocal
from models.entities import Room, Bill, DiscountRequest, PeriodClose, AuditLog, PaymentRecord
from sqlalchemy.sql import func
from utils.helpers import format_money

def page_quick_dashboard(user, role):
    """快捷操作面板"""
    st.title("⚡ 快捷操作面板")
    
    s = SessionLocal()
    try:
        st.markdown("### 📌 待办事项")
        col1, col2, col3 = st.columns(3)
        
        pending_discounts = s.query(DiscountRequest).filter(DiscountRequest.status == '待审核').count()
        with col1:
            st.metric("待审批减免", pending_discounts)
            if pending_discounts > 0:
                if st.button("去审批", key="goto_discount"):
                    st.session_state['nav_target'] = "财务管理"
                    st.rerun()
        
        datetime.datetime.now().strftime("%Y-%m")
        last_period = (datetime.datetime.now() - datetime.timedelta(days=30)).strftime("%Y-%m")
        period_closed = s.query(PeriodClose).filter(PeriodClose.period == last_period, PeriodClose.closed).first()
        
        with col2:
            if period_closed:
                st.metric("上月账期", "已关账")
            else:
                st.metric("上月账期", "未关账", delta="需关账", delta_color="inverse")
        
        negative_balance_count = s.query(Room).filter(Room.balance < 0, not Room.is_deleted).count()
        with col3:
            st.metric("负余额房产", negative_balance_count)
        
        st.markdown("### 🚀 常用功能")
        col_func1, col_func2, col_func3, col_func4 = st.columns(4)
        
        with col_func1:
            if st.button("💰 收银台", use_container_width=True):
                st.session_state['nav_target'] = "收银台"
                st.rerun()
        with col_func2:
            if st.button("📝 批量计费", use_container_width=True):
                st.session_state['nav_target'] = "财务管理"
                st.rerun()
        with col_func3:
            if st.button("🔍 收费核对", use_container_width=True):
                st.session_state['nav_target'] = "🔍 收费核对"
                st.rerun()
        with col_func4:
            if st.button("📋 资源档案", use_container_width=True):
                st.session_state['nav_target'] = "资源档案"
                st.rerun()
        
        st.markdown("### 🔎 快捷搜索")
        search_type = st.radio("搜索类型", ["房号", "业主姓名", "电话"], horizontal=True)
        search_input = st.text_input("输入搜索关键词")
        
        if search_input:
            if search_type == "房号":
                rooms = s.query(Room).filter(Room.room_number.like(f"%{search_input}%"), not Room.is_deleted).limit(10).all()
            elif search_type == "业主姓名":
                rooms = s.query(Room).filter(Room.owner_name.like(f"%{search_input}%"), not Room.is_deleted).limit(10).all()
            else:
                rooms = s.query(Room).filter(Room.owner_phone.like(f"%{search_input}%"), not Room.is_deleted).limit(10).all()
            
            if rooms:
                st.success(f"找到 {len(rooms)} 个结果")
                for r in rooms:
                    with st.expander(f"{r.room_number} - {r.owner_name}"):
                        st.markdown(f"**房号**: {r.room_number} | **业主**: {r.owner_name} | **余额**: {format_money(r.balance)}")
            else:
                st.info("未找到匹配的结果")
        
        st.markdown("### 📈 今日数据")
        today_start = datetime.datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        today_payment = s.query(func.sum(PaymentRecord.amount)).filter(PaymentRecord.created_at >= today_start).scalar() or 0.0
        today_bills = s.query(func.count(Bill.id)).filter(Bill.created_at >= today_start).scalar() or 0
        today_operations = s.query(func.count(AuditLog.id)).filter(AuditLog.created_at >= today_start).scalar() or 0
        
        col_today1, col_today2, col_today3 = st.columns(3)
        col_today1.metric("今日收款", format_money(today_payment))
        col_today2.metric("今日新增账单", today_bills)
        col_today3.metric("今日操作次数", today_operations)
    finally:
        s.close()
