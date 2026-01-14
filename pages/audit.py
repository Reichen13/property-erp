"""审计查询和变更历史页面"""
import streamlit as st
import pandas as pd
import datetime
import json
from models.base import SessionLocal
from models.entities import AuditLog, User, DataChangeHistory
from sqlalchemy.sql import desc

def page_audit_query(user, role):
    """审计日志查询工作台"""
    st.title("🔎 审计日志查询工作台")
    if role not in ['管理员', '集团财务']:
        st.error("⛔️ 权限不足")
        return
    
    s = SessionLocal()
    try:
        col1, col2, col3 = st.columns(3)
        users = s.query(User.username).all()
        user_list = ['全部'] + [u[0] for u in users]
        selected_user = col1.selectbox("操作用户", user_list)
        
        actions = s.query(AuditLog.action).distinct().all()
        action_list = ['全部'] + [a[0] for a in actions if a[0]]
        selected_action = col2.selectbox("操作类型", action_list)
        
        date_range = col3.selectbox("时间范围", ["最近1天", "最近7天", "最近30天", "全部"])
        
        query = s.query(AuditLog).order_by(desc(AuditLog.created_at))
        if selected_user != '全部':
            query = query.filter(AuditLog.user == selected_user)
        if selected_action != '全部':
            query = query.filter(AuditLog.action == selected_action)
        if date_range == "最近1天":
            query = query.filter(AuditLog.created_at >= datetime.datetime.now() - datetime.timedelta(days=1))
        elif date_range == "最近7天":
            query = query.filter(AuditLog.created_at >= datetime.datetime.now() - datetime.timedelta(days=7))
        elif date_range == "最近30天":
            query = query.filter(AuditLog.created_at >= datetime.datetime.now() - datetime.timedelta(days=30))
        
        logs = query.limit(1000).all()
        if not logs:
            st.info("未找到符合条件的日志")
            return
        
        st.markdown(f"### 📋 查询结果 (共 {len(logs)} 条)")
        log_data = [{"ID": log.id, "时间": log.created_at.strftime("%Y-%m-%d %H:%M:%S"), "用户": log.user,
            "操作": log.action, "目标": log.target, "详情": log.details[:50] + "..." if len(log.details or '') > 50 else log.details,
            "trace_id": log.trace_id} for log in logs]
        st.dataframe(pd.DataFrame(log_data), use_container_width=True, height=400)
        
        st.markdown("### 🔗 操作链路追踪")
        trace_id_input = st.text_input("输入 trace_id 追踪操作链路")
        if trace_id_input:
            related_logs = s.query(AuditLog).filter(AuditLog.trace_id == trace_id_input).order_by(AuditLog.created_at).all()
            if related_logs:
                st.success(f"找到 {len(related_logs)} 条相关日志")
                for log in related_logs:
                    with st.expander(f"{log.created_at.strftime('%H:%M:%S')} - {log.action} - {log.target}"):
                        try:
                            st.json(json.loads(log.details) if log.details and log.details.startswith('{') else {"raw": log.details})
                        except Exception:
                            st.text(log.details)
            else:
                st.warning("未找到相关日志")
    finally:
        s.close()

def page_data_change_history(user, role):
    """数据变更历史查询"""
    st.title("📜 数据变更历史")
    if role not in ['管理员', '集团财务']:
        st.error("⛔️ 权限不足")
        return
    
    s = SessionLocal()
    try:
        col1, col2, col3 = st.columns(3)
        tables = ['全部', 'rooms', 'bills', 'payment_records', 'users']
        selected_table = col1.selectbox("数据表", tables)
        record_id_input = col2.text_input("记录ID (可选)")
        date_range = col3.selectbox("时间范围", ["最近1天", "最近7天", "最近30天", "全部"], key="change_date")
        
        query = s.query(DataChangeHistory).order_by(desc(DataChangeHistory.changed_at))
        if selected_table != '全部':
            query = query.filter(DataChangeHistory.table_name == selected_table)
        if record_id_input:
            try:
                query = query.filter(DataChangeHistory.record_id == int(record_id_input))
            except ValueError:
                pass
        if date_range == "最近1天":
            query = query.filter(DataChangeHistory.changed_at >= datetime.datetime.now() - datetime.timedelta(days=1))
        elif date_range == "最近7天":
            query = query.filter(DataChangeHistory.changed_at >= datetime.datetime.now() - datetime.timedelta(days=7))
        elif date_range == "最近30天":
            query = query.filter(DataChangeHistory.changed_at >= datetime.datetime.now() - datetime.timedelta(days=30))
        
        changes = query.limit(500).all()
        if not changes:
            st.info("未找到变更记录")
            return
        
        st.markdown(f"### 📋 变更记录 (共 {len(changes)} 条)")
        change_data = [{"时间": c.changed_at.strftime("%Y-%m-%d %H:%M:%S"), "数据表": c.table_name, "记录ID": c.record_id,
            "字段": c.field_name, "原值": c.old_value[:30] + "..." if len(c.old_value or '') > 30 else c.old_value,
            "新值": c.new_value[:30] + "..." if len(c.new_value or '') > 30 else c.new_value,
            "操作人": c.changed_by, "原因": c.reason or ""} for c in changes]
        st.dataframe(pd.DataFrame(change_data), use_container_width=True, height=400)
    finally:
        s.close()
