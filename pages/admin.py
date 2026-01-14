"""系统管理页面"""
import streamlit as st
import pandas as pd
import bcrypt
import json
import hashlib
import datetime
from sqlalchemy.exc import IntegrityError
from models import SessionLocal, User, Property, FeeType, Room, Bill, PaymentRecord, AuditLog
from services.audit import AuditService


def page_admin(user, role):
    st.title("🛠️ 系统管理")
    if role != '管理员':
        st.error("⛔️ 权限不足")
        return
    
    s = SessionLocal()
    try:
        t1, t2, t3, t4 = st.tabs(["👤 用户管理", "🏢 物业项目", "🧩 费用科目", "🗄️ 数据备份"])
        
        with t1:
            st.subheader("用户列表")
            users = s.query(User).outerjoin(Property).all()
            df_users = pd.DataFrame([{
                "ID": u.id, "账号": u.username, "角色": u.role,
                "归属物业": u.property.name if u.property else "全局/未绑定",
                "创建": u.created_at.strftime('%Y-%m-%d') if u.created_at else ""
            } for u in users])
            st.dataframe(df_users, use_container_width=True)
            
            # 修改/删除用户
            if users:
                st.markdown("### 修改/删除用户")
                all_props = s.query(Property).all()
                prop_opts = {"(无/全局管理员)": None}
                for p in all_props:
                    prop_opts[p.name] = p.id
                
                user_opts = {f"{u.username} (ID:{u.id})": u.id for u in users}
                sel_user = st.selectbox("选择用户", list(user_opts.keys()), key="edit_user_sel")
                sel_user_id = user_opts[sel_user]
                sel_user_obj = s.query(User).get(sel_user_id)
                
                c1, c2 = st.columns(2)
                new_role = c1.selectbox("角色", ["管理员", "集团财务", "项目财务", "审批员"], 
                    index=["管理员", "集团财务", "项目财务", "审批员"].index(sel_user_obj.role) if sel_user_obj.role in ["管理员", "集团财务", "项目财务", "审批员"] else 0, key="edit_user_role")
                cur_prop = sel_user_obj.property.name if sel_user_obj.property else "(无/全局管理员)"
                new_prop = c2.selectbox("归属物业", list(prop_opts.keys()), 
                    index=list(prop_opts.keys()).index(cur_prop) if cur_prop in prop_opts else 0, key="edit_user_prop")
                new_pw = st.text_input("新密码（留空不修改）", type="password", key="edit_user_pw")
                
                col1, col2 = st.columns(2)
                if col1.button("保存修改", key="save_user"):
                    sel_user_obj.role = new_role
                    sel_user_obj.property_id = prop_opts[new_prop]
                    if new_pw:
                        sel_user_obj.password_hash = bcrypt.hashpw(new_pw.encode(), bcrypt.gensalt()).decode()
                    s.commit()
                    AuditService.log(user, "修改用户", sel_user_obj.username, {"role": new_role})
                    st.success("用户已更新")
                    st.rerun()
                
                if col2.button("🗑️ 删除用户", type="secondary", key="del_user"):
                    st.session_state['confirm_del_user'] = sel_user_id
                
                if st.session_state.get('confirm_del_user') == sel_user_id:
                    st.warning(f"⚠️ 确定要删除用户 **{sel_user_obj.username}** 吗？此操作不可恢复！")
                    c1, c2 = st.columns(2)
                    if c1.button("✅ 确认删除", type="primary", key="confirm_del_user_btn"):
                        AuditService.log(user, "删除用户", sel_user_obj.username, {})
                        s.delete(sel_user_obj)
                        s.commit()
                        st.session_state.pop('confirm_del_user', None)
                        st.success("用户已删除")
                        st.rerun()
                    if c2.button("取消", key="cancel_del_user"):
                        st.session_state.pop('confirm_del_user', None)
                        st.rerun()
            
            st.markdown("### 新增用户")
            with st.form("add_user"):
                c1, c2 = st.columns(2)
                un = c1.text_input("账号")
                pw = c2.text_input("初始密码", type="password")
                rl = c1.selectbox("角色", ["管理员", "集团财务", "项目财务", "审批员"])
                all_props = s.query(Property).all()
                prop_opts_add = {"(无/全局管理员)": None}
                for p in all_props:
                    prop_opts_add[p.name] = p.id
                sel_prop_name = c2.selectbox("归属物业", list(prop_opts_add.keys()))
                
                if st.form_submit_button("添加用户"):
                    if not un or not pw:
                        st.error("账号密码必填")
                    else:
                        try:
                            h = bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()
                            s.add(User(username=un, password_hash=h, role=rl, property_id=prop_opts_add[sel_prop_name]))
                            s.commit()
                            st.success("用户已添加")
                            st.rerun()
                        except IntegrityError:
                            s.rollback()
                            st.error("账号已存在")
        
        with t2:
            st.subheader("物业项目列表")
            props = s.query(Property).all()
            if props:
                st.dataframe(pd.DataFrame([{"ID": p.id, "名称": p.name, "地址": p.address} for p in props]), use_container_width=True)
                
                st.markdown("### 修改/删除项目")
                prop_opts = {f"{p.name} (ID:{p.id})": p.id for p in props}
                sel_prop = st.selectbox("选择项目", list(prop_opts.keys()), key="edit_prop_sel")
                sel_prop_id = prop_opts[sel_prop]
                sel_prop_obj = s.query(Property).get(sel_prop_id)
                
                c1, c2 = st.columns(2)
                new_name = c1.text_input("项目名称", value=sel_prop_obj.name, key="edit_prop_name")
                new_addr = c2.text_input("地址", value=sel_prop_obj.address or "", key="edit_prop_addr")
                
                col1, col2 = st.columns(2)
                if col1.button("保存修改", key="save_prop"):
                    sel_prop_obj.name = new_name
                    sel_prop_obj.address = new_addr
                    s.commit()
                    AuditService.log(user, "修改物业项目", new_name, {})
                    st.success("项目已更新")
                    st.rerun()
                
                if col2.button("🗑️ 删除项目", type="secondary", key="del_prop"):
                    st.session_state['confirm_del_prop'] = sel_prop_id
                
                if st.session_state.get('confirm_del_prop') == sel_prop_id:
                    st.warning(f"⚠️ 确定要删除项目 **{sel_prop_obj.name}** 吗？关联的用户将失去归属！")
                    c1, c2 = st.columns(2)
                    if c1.button("✅ 确认删除", type="primary", key="confirm_del_prop_btn"):
                        AuditService.log(user, "删除物业项目", sel_prop_obj.name, {})
                        s.delete(sel_prop_obj)
                        s.commit()
                        st.session_state.pop('confirm_del_prop', None)
                        st.success("项目已删除")
                        st.rerun()
                    if c2.button("取消", key="cancel_del_prop"):
                        st.session_state.pop('confirm_del_prop', None)
                        st.rerun()
            
            st.markdown("### 新建项目")
            with st.form("add_prop"):
                pn = st.text_input("项目名称")
                pa = st.text_input("地址")
                if st.form_submit_button("新建项目"):
                    if pn:
                        try:
                            s.add(Property(name=pn, address=pa))
                            s.commit()
                            st.success("项目已创建")
                            st.rerun()
                        except IntegrityError:
                            st.error("项目名称重复")
                    else:
                        st.error("名称必填")
        
        with t3:
            st.subheader("费用科目")
            fees = s.query(FeeType).all()
            df_fee = pd.DataFrame([{"ID": f.id, "科目": f.name, "税率": f.tax_rate} for f in fees])
            st.dataframe(df_fee, use_container_width=True)
            
            if fees:
                st.markdown("### 修改/删除科目")
                fee_opts = {f"{f.name} (ID:{f.id})": f.id for f in fees}
                sel_fee = st.selectbox("选择科目", list(fee_opts.keys()), key="edit_fee_sel")
                sel_fee_id = fee_opts[sel_fee]
                sel_fee_obj = s.query(FeeType).get(sel_fee_id)
                
                c1, c2 = st.columns(2)
                new_fee_name = c1.text_input("科目名称", value=sel_fee_obj.name, key="edit_fee_name")
                new_fee_rate = c2.number_input("税率", min_value=0.0, max_value=0.13, value=float(sel_fee_obj.tax_rate or 0), key="edit_fee_rate")
                
                col1, col2 = st.columns(2)
                if col1.button("保存修改", key="save_fee"):
                    sel_fee_obj.name = new_fee_name
                    sel_fee_obj.tax_rate = new_fee_rate
                    s.commit()
                    AuditService.log(user, "修改费用科目", new_fee_name, {})
                    st.success("科目已更新")
                    st.rerun()
                
                if col2.button("🗑️ 删除科目", type="secondary", key="del_fee"):
                    st.session_state['confirm_del_fee'] = sel_fee_id
                
                if st.session_state.get('confirm_del_fee') == sel_fee_id:
                    st.warning(f"⚠️ 确定要删除科目 **{sel_fee_obj.name}** 吗？已关联的账单可能受影响！")
                    c1, c2 = st.columns(2)
                    if c1.button("✅ 确认删除", type="primary", key="confirm_del_fee_btn"):
                        AuditService.log(user, "删除费用科目", sel_fee_obj.name, {})
                        s.delete(sel_fee_obj)
                        s.commit()
                        st.session_state.pop('confirm_del_fee', None)
                        st.success("科目已删除")
                        st.rerun()
                    if c2.button("取消", key="cancel_del_fee"):
                        st.session_state.pop('confirm_del_fee', None)
                        st.rerun()
            
            st.markdown("### 新增科目")
            with st.form("add_fee"):
                name = st.text_input("新科目名称")
                rate = st.number_input("默认税率", min_value=0.0, max_value=0.13, value=0.0)
                if st.form_submit_button("添加科目"):
                    s.add(FeeType(name=name, tax_rate=rate))
                    s.commit()
                    st.success("已添加")
                    st.rerun()
        
        with t4:
            st.subheader("🗄️ 数据备份与校验和")
            if st.button("生成备份包并下载"):
                export = {
                    'rooms': [{"id": r.id, "room": r.room_number, "owner": r.owner_name, "area": r.area, "balance": r.balance} for r in s.query(Room).all()],
                    'bills': [{"id": b.id, "room_id": b.room_id, "fee": b.fee_type, "period": b.period, "due": b.amount_due, "paid": b.amount_paid, "status": b.status} for b in s.query(Bill).all()],
                    'payments': [{"id": p.id, "room_id": p.room_id, "amount": p.amount, "method": p.pay_method, "time": p.created_at.isoformat() if p.created_at else ""} for p in s.query(PaymentRecord).all()],
                    'audit': [{"time": a.created_at.isoformat() if a.created_at else "", "user": a.user, "action": a.action, "target": a.target} for a in s.query(AuditLog).all()]
                }
                data = json.dumps(export, ensure_ascii=False, indent=2)
                checksum = hashlib.sha256(data.encode()).hexdigest()
                fname = f"backup_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                with open(fname, 'w', encoding='utf-8') as f:
                    f.write(data)
                st.code(f"SHA256: {checksum}")
                with open(fname, 'rb') as f:
                    st.download_button("下载备份JSON", f, file_name=fname)
                AuditService.log(user, "备份导出", "全库", {"file": fname, "sha256": checksum})
    finally:
        s.close()
