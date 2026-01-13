"""物业管理页面"""
import streamlit as st
import pandas as pd
import time
from models.base import SessionLocal, get_session_factory, init_property_db
from models.entities import Property
from services.audit import AuditService

def page_property_management(user, role):
    """物业管理与切换"""
    st.title("🏘️ 物业管理")
    
    if role not in ['管理员']:
        st.error("⛔️ 权限不足")
        return
    
    s = SessionLocal()
    try:
        t1, t2 = st.tabs(["切换物业", "物业列表"])
        
        with t1:
            st.markdown("### 🔄 切换当前物业")
            properties = s.query(Property).filter(Property.is_deleted.is_(False)).all()
            
            current_code = st.session_state.get('property_code', '')
            current_name = st.session_state.get('property_name', '默认物业')
            st.info(f"当前物业: **{current_name}** ({current_code or '默认'})")
            
            if properties:
                options = {f"{p.name} ({p.code})": p for p in properties}
                options["默认物业 (default)"] = None
                
                selected = st.selectbox("选择物业", list(options.keys()))
                
                if st.button("🔄 切换", type="primary"):
                    prop = options[selected]
                    if prop:
                        st.session_state.property_code = prop.code
                        st.session_state.property_name = prop.name
                        init_property_db(prop.code)
                        AuditService.log(user, "切换物业", prop.name, {"code": prop.code})
                    else:
                        st.session_state.property_code = ''
                        st.session_state.property_name = '默认物业'
                        AuditService.log(user, "切换物业", "默认物业", {})
                    st.success(f"✅ 已切换到: {selected}")
                    time.sleep(1)
                    st.rerun()
            else:
                st.warning("暂无物业，请先添加")
        
        with t2:
            st.markdown("### 📋 物业列表")
            properties = s.query(Property).filter(Property.is_deleted.is_(False)).all()
            if properties:
                st.dataframe(pd.DataFrame([{"ID": p.id, "名称": p.name, "编码": p.code, "地址": p.address or ""} for p in properties]), use_container_width=True)
            
            st.markdown("### ➕ 新增物业")
            with st.form("add_property"):
                name = st.text_input("物业名称", placeholder="如：世纪名城")
                code = st.text_input("物业编码", placeholder="如：sjmc（用于数据库文件名）")
                address = st.text_input("地址")
                
                if st.form_submit_button("添加物业", type="primary"):
                    if not name or not code:
                        st.error("请填写名称和编码")
                    elif s.query(Property).filter(Property.code == code).first():
                        st.error("编码已存在")
                    else:
                        prop = Property(name=name, code=code, address=address)
                        s.add(prop)
                        s.commit()
                        init_property_db(code)
                        AuditService.log(user, "新增物业", name, {"code": code})
                        st.success(f"✅ 物业 {name} 添加成功！数据库已初始化")
                        time.sleep(1)
                        st.rerun()
    finally:
        s.close()

def get_current_session():
    """获取当前物业的数据库会话"""
    property_code = st.session_state.get('property_code', '')
    if property_code:
        return get_session_factory(property_code)()
    return SessionLocal()
