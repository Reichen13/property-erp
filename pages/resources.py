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
                no = st.text_input("房号", placeholder="必填")
                owner = st.text_input("业主")
                owner_phone = st.text_input("业主电话")
                area = st.number_input("面积", min_value=0.0)
                
                import datetime
                move_in_date = st.date_input("入伙时间", value=datetime.datetime.now())
                
                for idx, item in enumerate(st.session_state.room_fee_items):
                    cols = st.columns([2, 2])
                    item["name"] = cols[0].selectbox("费用科目", fee_types, 
                        index=(fee_types.index(item["name"]) if item["name"] in fee_types else 0), key=f"fee_name_{idx}")
                    item["std"] = cols[1].text_input("标准金额", value=item.get("std",""), key=f"fee_std_{idx}")
                
                submitted = st.form_submit_button("✅ 添加", use_container_width=True)
                
                if submitted:
                    if not no or not no.strip():
                        st.error("房号不能为空")
                    elif s.query(Room).filter(Room.room_number == no).first():
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
                        from models import PaymentRecord, LedgerEntry
                        with transaction_scope() as (s_trx, audit_buffer):
                            apply_count = 0
                            bill_count = 0
                            prepay_total = 0
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
                                # 预缴金额设置到余额，并创建会计分录
                                try:
                                    prepay = float(row.get('预缴金额', 0) or 0)
                                    if prepay > 0:
                                        r.balance = (r.balance or 0) + prepay
                                        prepay_total += prepay
                                        # 创建预收账款会计分录（贷方，direction=-1）
                                        import datetime
                                        ledger = LedgerEntry(
                                            room_id=r.id,
                                            account_id=3,  # 预收账款科目
                                            amount=prepay,
                                            period=datetime.datetime.now().strftime('%Y-%m'),
                                            direction=-1,  # 贷方
                                            details=f'期初导入-{r.room_number}预缴-操作员:{user}'
                                        )
                                        s_trx.add(ledger)
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
                                # 历史欠费生成账单 - 添加数据验证
                                def safe_float(val, field_name):
                                    """安全转换为浮点数，过滤无效值"""
                                    if pd.isna(val) or val == '' or val is None:
                                        return 0.0
                                    val_str = str(val).strip()
                                    # 过滤明显无效的值
                                    if val_str.lower() in ['nan', 'none', 'null', '[object object]', 'undefined']:
                                        st.warning(f"房号{rn}的{field_name}包含无效值'{val_str}'，已忽略")
                                        return 0.0
                                    try:
                                        return float(val_str)
                                    except (ValueError, TypeError):
                                        st.warning(f"房号{rn}的{field_name}无法转换为数字'{val_str}'，已忽略")
                                        return 0.0
                                
                                arrears = safe_float(row.get('历史欠费', 0), '历史欠费')
                                paid = safe_float(row.get('已缴金额', 0), '已缴金额')
                                discount = safe_float(row.get('减免金额', 0), '减免金额')
                                period_start = str(row.get('欠费周期起', '')).strip()
                                period_end = str(row.get('欠费周期终', '')).strip()
                                if arrears > 0 and fee_name and period_start:
                                    # 解析周期，拆分为单月账单
                                    import datetime as dt
                                    def parse_period(p):
                                        """解析日期字符串为年月"""
                                        p = p.strip()
                                        if len(p) >= 10:  # 2025-08-01格式
                                            return p[:7]
                                        elif len(p) == 7:  # 2025-08格式
                                            return p
                                        return None
                                    
                                    start_ym = parse_period(period_start)
                                    end_ym = parse_period(period_end) if period_end else start_ym
                                    
                                    # 生成月份列表
                                    months = []
                                    if start_ym and end_ym:
                                        try:
                                            sy, sm = int(start_ym[:4]), int(start_ym[5:7])
                                            ey, em = int(end_ym[:4]), int(end_ym[5:7])
                                            while (sy, sm) <= (ey, em):
                                                months.append(f"{sy:04d}-{sm:02d}")
                                                sm += 1
                                                if sm > 12:
                                                    sm = 1
                                                    sy += 1
                                        except:
                                            months = [start_ym]
                                    else:
                                        months = [start_ym] if start_ym else []
                                    
                                    # 按月份数量平分金额
                                    month_count = len(months) if months else 1
                                    monthly_due = round(arrears / month_count, 2)
                                    monthly_paid = round(paid / month_count, 2)
                                    monthly_discount = round(discount / month_count, 2)
                                    
                                    for i, month in enumerate(months):
                                        # 最后一个月处理余数
                                        if i == month_count - 1:
                                            m_due = arrears - monthly_due * (month_count - 1)
                                            m_paid = paid - monthly_paid * (month_count - 1)
                                            m_disc = discount - monthly_discount * (month_count - 1)
                                        else:
                                            m_due, m_paid, m_disc = monthly_due, monthly_paid, monthly_discount
                                        
                                        status = '已缴' if m_paid >= m_due - m_disc else '未缴'
                                        bill = Bill(room_id=r.id, fee_type=fee_name, period=month,
                                                   accounting_period=month,
                                                   amount_due=m_due, amount_paid=m_paid, discount=m_disc,
                                                   status=status, batch_id=batch_id, operator=user, remark='期初导入')
                                        s_trx.add(bill)
                                        bill_count += 1
                                    
                                    # 已缴金额创建PaymentRecord（只创建一条汇总记录）
                                    if paid > 0:
                                        pr = PaymentRecord(room_id=r.id, amount=paid, biz_type='缴费',
                                                          pay_method='期初导入', operator=user, remark=f'期初导入-{fee_name}')
                                        s_trx.add(pr)
                                apply_count += 1
                            AuditService.log_deferred(s_trx, audit_buffer, user, "批量导入", "房档案", 
                                                     {"batch": batch_id, "rows": apply_count, "bills": bill_count, "prepay": prepay_total})
                        st.success(f"导入完成，批次ID: {batch_id}，房产{apply_count}条，账单{bill_count}条，预缴金额{prepay_total:.2f}元")
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
