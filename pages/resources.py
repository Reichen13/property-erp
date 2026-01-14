"""资源档案管理页面"""
import streamlit as st
import pandas as pd
import uuid
from models import SessionLocal, Room, Bill, FeeType
from services.audit import AuditService
from utils.transaction import transaction_scope


def page_resources(user, role):
    st.title("🏗️ 资源档案管理")
    if role not in ['管理员', '项目财务']:
        st.error("⛔️ 权限不足")
        return
    s = SessionLocal()
    try:
        t1, t2, t3, t4 = st.tabs(["🔍 查询/维护", "➕ 入伙/新增", "📥 批量导入", "↩️ 批次回滚"])
        
        with t1:
            search_key = st.text_input("搜索房号", placeholder="输入关键词...")
            query = s.query(Room).filter(Room.is_deleted.is_(False))
            if search_key:
                query = query.filter(Room.room_number.like(f"%{search_key}%"))
            rooms = query.limit(50).all()
            st.dataframe(pd.DataFrame([{
                "房号": r.room_number, "业主": r.owner_name, 
                "电话": getattr(r, 'owner_phone', ''), "面积": r.area,
                "项目1": getattr(r, 'fee1_name', ''), "标准1": getattr(r, 'fee1_std', 0.0),
                "项目2": getattr(r, 'fee2_name', ''), "标准2": getattr(r, 'fee2_std', 0.0),
                "项目3": getattr(r, 'fee3_name', ''), "标准3": getattr(r, 'fee3_std', 0.0)
            } for r in rooms]), use_container_width=True)
        
        with t2:
            fee_types = [f.name for f in s.query(FeeType).all()]
            if 'room_fee_items' not in st.session_state:
                st.session_state.room_fee_items = [{"name": fee_types[0] if fee_types else "", "std": "0"}]
            
            st.markdown("#### 费用项目")
            if st.button("➕ 新增费用项目") and len(st.session_state.room_fee_items) < 3:
                st.session_state.room_fee_items.append({"name": fee_types[0] if fee_types else "", "std": "0"})
            
            with st.form("add_room"):
                no = st.text_input("房号")
                owner = st.text_input("业主")
                owner_phone = st.text_input("业主电话")
                area = st.number_input("面积", min_value=0.0)
                
                for idx, item in enumerate(st.session_state.room_fee_items):
                    cols = st.columns([2, 2])
                    item["name"] = cols[0].selectbox("费用科目", fee_types, 
                        index=(fee_types.index(item["name"]) if item["name"] in fee_types else 0), key=f"fee_name_{idx}")
                    item["std"] = cols[1].text_input("标准金额", value=item.get("std",""), key=f"fee_std_{idx}")
                
                if st.form_submit_button("添加", disabled=(not no)):
                    exists = s.query(Room).filter(Room.room_number == no).first()
                    if exists:
                        st.error("房号已存在")
                    else:
                        fee_vals = st.session_state.room_fee_items[:3]
                        def parse_std(val):
                            try:
                                return float(val)
                            except Exception:
                                return 0.0
                        room = Room(room_number=no, owner_name=owner, owner_phone=owner_phone, area=area)
                        if len(fee_vals) >= 1:
                            room.fee1_name = fee_vals[0]["name"]
                            room.fee1_std = parse_std(fee_vals[0]["std"])
                        if len(fee_vals) >= 2:
                            room.fee2_name = fee_vals[1]["name"]
                            room.fee2_std = parse_std(fee_vals[1]["std"])
                        if len(fee_vals) >= 3:
                            room.fee3_name = fee_vals[2]["name"]
                            room.fee3_std = parse_std(fee_vals[2]["std"])
                        s.add(room)
                        s.commit()
                        st.success("添加成功")
        
        with t3:
            st.info("模板列：房号 | 业主 | 业主电话 | 面积 | 费用项目 | 项目月标准金额 | 历史欠费 | 欠费周期起 | 欠费周期终 | 预缴金额 | 已缴金额(可选) | 减免金额(可选) | 会计归属期(可选,YYYY-MM)")
            
            # 下载模板按钮
            import os
            template_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates", "资源档案批量导入示例.csv")
            if os.path.exists(template_path):
                with open(template_path, "rb") as tf:
                    st.download_button("📥 下载导入模板", tf.read(), "资源档案批量导入模板.csv", mime="text/csv")
            
            dry_run = st.checkbox("先试运行(Dry-run)", value=True)
            f = st.file_uploader("上传文件 (Excel/CSV)", type=['xlsx','csv'])
            
            if f and st.button("开始导入"):
                try:
                    df = pd.read_csv(f) if f.name.lower().endswith('.csv') else pd.read_excel(f)
                    batch_id = str(uuid.uuid4())
                    
                    if dry_run:
                        st.warning("试运行不入库，供预览检验")
                        st.dataframe(df.head(20), use_container_width=True)
                    else:
                        from models import PaymentRecord
                        with transaction_scope() as (s_trx, audit_buffer):
                            apply_count = 0
                            bill_count = 0
                            for _, row in df.iterrows():
                                rn = str(row.get('房号','')).strip()
                                if not rn:
                                    continue
                                r = s_trx.query(Room).filter_by(room_number=rn).first()
                                if not r:
                                    r = Room(room_number=rn, property_id=1)
                                    s_trx.add(r)
                                    s_trx.flush()
                                r.owner_name = str(row.get('业主', r.owner_name or ''))
                                r.owner_phone = str(row.get('业主电话', r.owner_phone or ''))
                                try:
                                    r.area = float(row.get('面积', r.area or 0))
                                except Exception:
                                    pass
                                # 预缴金额设置到余额
                                try:
                                    prepay = float(row.get('预缴金额', 0) or 0)
                                    if prepay > 0:
                                        r.balance = (r.balance or 0) + prepay
                                except Exception:
                                    pass
                                # 费用项目设置
                                fee_name = str(row.get('费用项目', '')).strip()
                                try:
                                    fee_std = float(row.get('项目月标准金额', 0) or 0)
                                except Exception:
                                    fee_std = 0
                                if fee_name:
                                    if not r.fee1_name:
                                        r.fee1_name, r.fee1_std = fee_name, fee_std
                                    elif not r.fee2_name and r.fee1_name != fee_name:
                                        r.fee2_name, r.fee2_std = fee_name, fee_std
                                    elif not r.fee3_name and r.fee1_name != fee_name and r.fee2_name != fee_name:
                                        r.fee3_name, r.fee3_std = fee_name, fee_std
                                # 历史欠费生成账单
                                try:
                                    arrears = float(row.get('历史欠费', 0) or 0)
                                except Exception:
                                    arrears = 0
                                try:
                                    paid = float(row.get('已缴金额', 0) or 0)
                                except Exception:
                                    paid = 0
                                try:
                                    discount = float(row.get('减免金额', 0) or 0)
                                except Exception:
                                    discount = 0
                                period_start = str(row.get('欠费周期起', '')).strip()
                                period_end = str(row.get('欠费周期终', '')).strip()
                                if arrears > 0 and fee_name and period_start:
                                    period_str = f"{period_start}~{period_end}" if period_end else period_start
                                    status = '已缴' if paid >= arrears - discount else '未缴'
                                    # 会计归属期：优先使用导入值，否则取欠费周期起的月份
                                    acc_period = str(row.get('会计归属期', '')).strip()
                                    if not acc_period and period_start:
                                        acc_period = period_start[:7] if len(period_start) >= 7 else period_start
                                    bill = Bill(room_id=r.id, fee_type=fee_name, period=period_str,
                                               accounting_period=acc_period if acc_period else None,
                                               amount_due=arrears, amount_paid=paid, discount=discount,
                                               status=status, batch_id=batch_id, operator=user, remark='期初导入')
                                    s_trx.add(bill)
                                    s_trx.flush()
                                    bill_count += 1
                                    # 已缴金额创建PaymentRecord
                                    if paid > 0:
                                        pr = PaymentRecord(room_id=r.id, amount=paid, biz_type='缴费',
                                                          pay_method='期初导入', operator=user, remark=f'期初导入-{fee_name}')
                                        s_trx.add(pr)
                                apply_count += 1
                            AuditService.log_deferred(s_trx, audit_buffer, user, "批量导入", "房档案", 
                                                     {"batch": batch_id, "rows": apply_count, "bills": bill_count})
                        st.success(f"导入完成，批次ID: {batch_id}，房产{apply_count}条，账单{bill_count}条")
                except Exception as e:
                    st.error(str(e))
        
        with t4:
            bid = st.text_input("输入批次ID进行回滚")
            if st.button("回滚执行") and bid:
                cnt = s.query(Bill).filter(Bill.batch_id == bid).delete()
                s.commit()
                AuditService.log(user, "批次回滚", "账单", {"batch": bid, "count": cnt})
                st.success(f"已回滚账单 {cnt} 条")
    finally:
        s.close()
