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
            
            st.markdown("### 新增用户")
            with st.form("add_user"):
                c1, c2 = st.columns(2)
                un = c1.text_input("账号")
                pw = c2.text_input("初始密码", type="password")
                rl = c1.selectbox("角色", ["管理员", "财务", "收银员"])
                all_props = s.query(Property).all()
                prop_opts = {"(无/全局管理员)": None}
                for p in all_props:
                    prop_opts[p.name] = p.id
                sel_prop_name = c2.selectbox("归属物业", list(prop_opts.keys()))
                
                if st.form_submit_button("添加用户"):
                    if not un or not pw:
                        st.error("账号密码必填")
                    else:
                        try:
                            h = bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()
                            s.add(User(username=un, password_hash=h, role=rl, property_id=prop_opts[sel_prop_name]))
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
            
            with st.form("add_fee"):
                name = st.text_input("新科目名称")
                rate = st.number_input("默认税率", min_value=0.0, max_value=0.13, value=0.0)
                if st.form_submit_button("添加科目"):
                    s.add(FeeType(name=name, tax_rate=rate))
                    s.commit()
                    st.success("已添加")
        
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
