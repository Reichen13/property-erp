"""物业ERP系统 - 模块化主入口"""
import streamlit as st
import streamlit.components.v1 as components
import datetime
import shutil
import os

import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import config
from models import SessionLocal, engine, Base, User, Property
from services.auth import AuthService
from services.audit import AuditService
from pages import (
    page_dashboard, page_cashier, page_billing, page_query, page_resources, page_admin,
    page_quick_dashboard, page_reconciliation_workbench, page_three_way_reconciliation,
    page_financial_check, page_audit_query, page_data_change_history, page_batch_operations,
    page_payment_reconciliation, page_arrears_tracking, page_financial_reports,
    page_backup_management, page_system_monitor, page_permission_management,
    page_system_init, page_clear_test_data, page_change_password,
    page_parking_management, page_utility_meter_management, page_utility_reading,
    page_property_management
)

# 页面配置
st.set_page_config(page_title=config.APP_NAME, layout="wide", page_icon="🏙️")

# 初始化数据库表
Base.metadata.create_all(engine)


def _seed_default_admin():
    """创建默认物业和管理员账号"""
    s = SessionLocal()
    try:
        prop = s.query(Property).filter_by(code="default").first()
        if not prop:
            prop = Property(name="默认物业", code="default")
            s.add(prop)
            s.flush()
        admin = s.query(User).filter_by(username=config.DEFAULT_ADMIN_USER).first()
        if not admin:
            h = AuthService.hash_password(config.DEFAULT_ADMIN_PASS)
            s.add(User(username=config.DEFAULT_ADMIN_USER, password_hash=h, role="管理员", property_id=prop.id))
        s.commit()
    except Exception:
        s.rollback()
    finally:
        s.close()


def daily_auto_backup():
    """每日自动备份"""
    backup_dir = "backups"
    try:
        os.makedirs(backup_dir, exist_ok=True)
        today = datetime.datetime.now().strftime("%Y%m%d")
        backup_file = os.path.join(backup_dir, f"property_erp_{today}.db")
        if not os.path.exists(backup_file) and os.path.exists(config.DB_PATH):
            shutil.copy2(config.DB_PATH, backup_file)
    except Exception:
        pass


def _set_session_cookie_js(token, max_age=28800):
    js = f"""<script>
    document.cookie='erp_session={token};path=/;max-age={max_age};SameSite=Lax';
    localStorage.setItem('erp_session', '{token}');
    </script>"""
    components.html(js, height=0)


def _clear_session_cookie_js():
    js = """<script>
    document.cookie='erp_session=;path=/;max-age=0;SameSite=Lax';
    localStorage.removeItem('erp_session');
    </script>"""
    components.html(js, height=0)


def _read_session_from_storage():
    """通过 JavaScript 读取 localStorage 中的 session"""
    js_code = """
    <script>
    (function() {
        var token = localStorage.getItem('erp_session');
        if (token && !window.location.search.includes('session=')) {
            var url = new URL(window.location.href);
            url.searchParams.set('session', token);
            window.location.replace(url.toString());
        }
    })();
    </script>
    """
    components.html(js_code, height=0)


def check_login():
    """登录检查"""
    if st.session_state.get('logged_in'):
        return True
    
    # 尝试从URL参数恢复会话
    params = st.query_params
    token = params.get('session')
    
    if token:
        s = SessionLocal()
        user = AuthService.validate_token(s, token)
        if user:
            st.session_state.logged_in = True
            st.session_state.username = user.username
            st.session_state.user_role = user.role
            st.session_state.user_id = user.id
            st.session_state.property_id = user.property_id
            s.close()
            return True
        s.close()
    
    # 尝试从 localStorage 恢复会话
    _read_session_from_storage()
    
    # 显示登录界面
    c1, c2, c3 = st.columns([1, 2, 1])
    with c2:
        st.markdown(f"## 🔐 {config.APP_NAME}")
        username = st.text_input("账号")
        password = st.text_input("密码", type="password")
        
        if st.button("登录系统", use_container_width=True):
            if AuthService.is_locked(username):
                st.error("账号已锁定，请稍后再试")
                return False
            
            s = SessionLocal()
            try:
                user = s.query(User).filter_by(username=username).first()
                if user and AuthService.check_password(password, user.password_hash):
                    token = AuthService.create_session(s, user.id, config.SESSION_HOURS)
                    st.session_state.logged_in = True
                    st.session_state.username = user.username
                    st.session_state.user_role = user.role
                    st.session_state.user_id = user.id
                    st.session_state.property_id = user.property_id
                    AuthService.clear_fail(username)
                    AuditService.log(user.username, "系统登录", "Auth")
                    daily_auto_backup()
                    _set_session_cookie_js(token)
                    st.success(f"登录成功！欢迎, {user.role}")
                    st.rerun()
                else:
                    AuthService.record_fail(username)
                    st.error("账号或密码错误")
            finally:
                s.close()
    return False


def logout():
    """退出登录"""
    if st.session_state.get('username'):
        AuditService.log(st.session_state.username, "系统登出", "Auth")
    s = SessionLocal()
    AuthService.clear_token(s, user_id=st.session_state.get('user_id'))
    s.close()
    _clear_session_cookie_js()
    for key in ['logged_in', 'username', 'user_role', 'user_id', 'property_id']:
        st.session_state.pop(key, None)
    st.rerun()


# 页面映射（分组）
PAGES = {
    # 核心业务
    "🏠 运营驾驶舱": page_dashboard,
    "💰 收银台": page_cashier,
    "📋 财务管理": page_billing,
    "📊 数据中心": page_query,
    "🏢 资源档案": page_resources,
    "⚡ 快捷面板": page_quick_dashboard,
    # 车位与水电
    "🚗 车位管理": page_parking_management,
    "📊 水电表管理": page_utility_meter_management,
    "💧 水电抄表": page_utility_reading,
    # 数据与审计
    "🔍 收费核对": page_reconciliation_workbench,
    "🔄 三方核对": page_three_way_reconciliation,
    "⚖️ 财务检查": page_financial_check,
    "🔎 审计查询": page_audit_query,
    "📜 变更历史": page_data_change_history,
    "⚙️ 批量操作": page_batch_operations,
    # 报表与备份
    "💳 收款对账": page_payment_reconciliation,
    "📈 欠费追踪": page_arrears_tracking,
    "📊 财务报表": page_financial_reports,
    "💾 数据备份": page_backup_management,
    # 系统与运维
    "📡 系统监控": page_system_monitor,
    "🔐 权限管理": page_permission_management,
    "🔧 系统初始化": page_system_init,
    "🗑️ 清除测试数据": page_clear_test_data,
    "🔑 修改密码": page_change_password,
    "⚙️ 系统管理": page_admin,
    "🏘️ 物业管理": page_property_management,
}

# 页面分组（用于侧边栏显示）
PAGE_GROUPS = {
    "核心业务": ["🏠 运营驾驶舱", "💰 收银台", "📋 财务管理", "📊 数据中心", "🏢 资源档案", "⚡ 快捷面板"],
    "车位与水电": ["🚗 车位管理", "📊 水电表管理", "💧 水电抄表"],
    "数据与审计": ["🔍 收费核对", "🔄 三方核对", "⚖️ 财务检查", "🔎 审计查询", "📜 变更历史", "⚙️ 批量操作"],
    "报表与备份": ["💳 收款对账", "📈 欠费追踪", "📊 财务报表", "💾 数据备份"],
    "系统与运维": ["📡 系统监控", "🔐 权限管理", "🔧 系统初始化", "🗑️ 清除测试数据", "🔑 修改密码", "⚙️ 系统管理", "🏘️ 物业管理"],
}


def main():
    _seed_default_admin()
    
    if not check_login():
        return
    
    user = st.session_state.username
    role = st.session_state.user_role
    
    # 侧边栏
    st.sidebar.markdown(f"👤 **{user}** ({role})")
    property_name = st.session_state.get('property_name', '默认物业')
    st.sidebar.caption(f"🏘️ {property_name}")
    st.sidebar.divider()
    
    # 分组导航
    page = None
    for group, pages in PAGE_GROUPS.items():
        with st.sidebar.expander(group, expanded=(group == "核心业务")):
            for p in pages:
                if p in PAGES and st.button(p, key=f"nav_{p}", use_container_width=True):
                    st.session_state.current_page = p
    
    page = st.session_state.get('current_page', "🏠 运营驾驶舱")
    
    st.sidebar.divider()
    if st.sidebar.button("🚪 退出登录", use_container_width=True):
        logout()
    
    # 渲染页面
    PAGES[page](user, role)


if __name__ == '__main__':
    main()
