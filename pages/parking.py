"""车位管理和水电抄表页面"""
import streamlit as st
import pandas as pd
import datetime
import time
import io
from models.base import SessionLocal
from models.entities import ParkingSpace, UtilityMeter, UtilityReading, ParkingType, Bill
from sqlalchemy.sql import desc
from utils.transaction import transaction_scope
from services.audit import AuditService

# 默认车位类型
DEFAULT_PARKING_TYPES = ["地下车位", "地面车位", "车库", "子母车位"]

def get_parking_types(s):
    """获取所有车位类型"""
    types = s.query(ParkingType).filter(ParkingType.is_deleted.is_(False)).all()
    if types:
        return [t.name for t in types]
    return DEFAULT_PARKING_TYPES

def page_parking_management(user, role):
    """车位管理页面"""
    st.title("🚗 车位管理")
    
    s = SessionLocal()
    try:
        t1, t2, t3, t4 = st.tabs(["车位列表", "新增车位", "车位类型管理", "批量导入"])
        
        parking_types = get_parking_types(s)
        
        with t1:
            st.markdown("### 📋 车位列表")
            parking_spaces = s.query(ParkingSpace).filter(ParkingSpace.is_deleted.is_(False)).limit(100).all()
            if parking_spaces:
                st.dataframe(pd.DataFrame([{"车位号": p.space_number, "类型": p.space_type, "状态": p.status,
                    "业主": p.owner_name or "", "月车位费": f"¥{p.fee_monthly:.2f}", "余额": f"¥{p.balance:.2f}"}
                    for p in parking_spaces]), use_container_width=True)
            else:
                st.info("暂无车位记录")
        
        with t2:
            st.markdown("### ➕ 新增车位")
            with st.form("add_parking"):
                space_number = st.text_input("车位号", placeholder="如：A1-01")
                space_type = st.selectbox("车位类型", parking_types)
                owner_name = st.text_input("业主姓名")
                owner_phone = st.text_input("业主电话")
                status = st.selectbox("使用状态", ["闲置", "已售", "业主自用"])
                fee_monthly = st.number_input("月车位费", min_value=0.0)
                
                if st.form_submit_button("添加车位", type="primary"):
                    if not space_number:
                        st.error("请填写车位号")
                    else:
                        try:
                            with transaction_scope() as (s_trx, audit_buffer):
                                parking = ParkingSpace(space_number=space_number, space_type=space_type,
                                    owner_name=owner_name, owner_phone=owner_phone, status=status, fee_monthly=fee_monthly)
                                s_trx.add(parking)
                                AuditService.log_deferred(s_trx, audit_buffer, user, "新增车位", space_number, {"类型": space_type})
                            st.success("✅ 车位添加成功！")
                            time.sleep(1)
                            st.rerun()
                        except Exception as e:
                            st.error(f"添加失败: {e}")
        
        with t3:
            if role not in ['管理员', '项目财务']:
                st.warning("⚠️ 仅管理员和项目财务可管理车位类型")
            else:
                st.markdown("### 🏷️ 车位类型管理")
                st.info(f"当前车位类型: {', '.join(parking_types)}")
                
                with st.form("add_parking_type"):
                    new_type = st.text_input("新增车位类型", placeholder="如：子母车位、机械车位")
                    if st.form_submit_button("添加类型", type="primary"):
                        if not new_type:
                            st.error("请输入类型名称")
                        elif new_type in parking_types:
                            st.error("该类型已存在")
                        else:
                            try:
                                with transaction_scope() as (s_trx, audit_buffer):
                                    s_trx.add(ParkingType(name=new_type))
                                    AuditService.log_deferred(s_trx, audit_buffer, user, "新增车位类型", new_type, {})
                                st.success(f"✅ 车位类型 '{new_type}' 添加成功！")
                                time.sleep(1)
                                st.rerun()
                            except Exception as e:
                                st.error(f"添加失败: {e}")
        
        with t4:
            if role not in ['管理员', '项目财务']:
                st.warning("⚠️ 仅管理员和项目财务可批量导入")
            else:
                st.markdown("### 📥 批量导入车位")
                
                # 动态生成模板CSV
                template_csv = """车位号,车位类型,业主姓名,业主电话,使用状态,月车位费,历史欠费,欠费周期起,欠费周期终,预缴金额
A1-01,地下车位,张三,13800138001,已售,150,300,2025-10,2025-11,0
A1-02,地面车位,李四,13800138002,业主自用,100,0,,,200
B2-01,车库,王五,13800138003,已售,200,0,,,0
C3-01,子母车位,赵六,13800138004,已售,250,500,2025-09,2025-10,100"""
                st.download_button("📄 下载导入模板", template_csv.encode('utf-8-sig'), file_name="车位批量导入模板.csv", mime="text/csv")
                
                st.markdown("""
                **模板字段说明：**
                - 车位号（必填）、车位类型、业主姓名、业主电话、使用状态
                - 月车位费、历史欠费、欠费周期起、欠费周期终、预缴金额
                """)
                
                uploaded = st.file_uploader("上传CSV文件", type=['csv'], key="parking_import")
                if uploaded:
                    try:
                        df = pd.read_csv(uploaded)
                        st.dataframe(df.head(10), use_container_width=True)
                        st.info(f"共 {len(df)} 条记录")
                        
                        if st.button("🚀 确认导入", type="primary"):
                            success, fail = 0, 0
                            with transaction_scope() as (s_trx, audit_buffer):
                                for _, row in df.iterrows():
                                    try:
                                        space_num = str(row.get('车位号', '')).strip()
                                        if not space_num:
                                            fail += 1
                                            continue
                                        
                                        # 检查是否已存在
                                        existing = s_trx.query(ParkingSpace).filter(ParkingSpace.space_number == space_num).first()
                                        if existing:
                                            fail += 1
                                            continue
                                        
                                        fee_monthly = float(row.get('月车位费', 0) or 0)
                                        prepaid = float(row.get('预缴金额', 0) or 0)
                                        arrears = float(row.get('历史欠费', 0) or 0)
                                        
                                        parking = ParkingSpace(
                                            space_number=space_num,
                                            space_type=str(row.get('车位类型', '地下车位') or '地下车位'),
                                            owner_name=str(row.get('业主姓名', '') or ''),
                                            owner_phone=str(row.get('业主电话', '') or ''),
                                            status=str(row.get('使用状态', '闲置') or '闲置'),
                                            fee_monthly=fee_monthly,
                                            balance=prepaid
                                        )
                                        s_trx.add(parking)
                                        s_trx.flush()
                                        
                                        # 如果有历史欠费，创建账单
                                        if arrears > 0:
                                            period_start = str(row.get('欠费周期起', '') or '')
                                            period_end = str(row.get('欠费周期终', '') or '')
                                            period = f"{period_start}~{period_end}" if period_start else ""
                                            bill = Bill(
                                                room_id=parking.id,
                                                fee_type="车位费",
                                                period=period,
                                                amount_due=arrears,
                                                amount_paid=0,
                                                status="未缴"
                                            )
                                            s_trx.add(bill)
                                        
                                        success += 1
                                    except Exception:
                                        fail += 1
                                
                                AuditService.log_deferred(s_trx, audit_buffer, user, "批量导入车位", f"成功{success}条", {"失败": fail})
                            
                            st.success(f"✅ 导入完成！成功 {success} 条，失败 {fail} 条")
                            time.sleep(1)
                            st.rerun()
                    except Exception as e:
                        st.error(f"文件解析失败: {e}")
    finally:
        s.close()

def page_utility_meter_management(user, role):
    """水电表管理页面"""
    st.title("📊 水电表管理")
    
    s = SessionLocal()
    try:
        t1, t2 = st.tabs(["表计列表", "新增表计"])
        
        with t1:
            meters = s.query(UtilityMeter).filter(UtilityMeter.is_deleted.is_(False)).limit(100).all()
            if meters:
                st.dataframe(pd.DataFrame([{"表号": m.meter_number, "表类型": m.meter_type,
                    "单价": f"¥{m.unit_price:.2f}", "状态": m.status} for m in meters]), use_container_width=True)
            else:
                st.info("暂无水电表记录")
        
        with t2:
            with st.form("add_meter"):
                meter_number = st.text_input("表号")
                meter_type = st.selectbox("表类型", ["水表", "电表"])
                unit_price = st.number_input("单价", min_value=0.0, value=3.5 if meter_type == "电表" else 4.5)
                
                if st.form_submit_button("添加表计", type="primary"):
                    if not meter_number:
                        st.error("请填写表号")
                    else:
                        try:
                            with transaction_scope() as (s_trx, audit_buffer):
                                meter = UtilityMeter(meter_number=meter_number, meter_type=meter_type, unit_price=unit_price)
                                s_trx.add(meter)
                                AuditService.log_deferred(s_trx, audit_buffer, user, "新增表计", meter_number, {"表类型": meter_type})
                            st.success("✅ 表计添加成功！")
                            time.sleep(1)
                            st.rerun()
                        except Exception as e:
                            st.error(f"添加失败: {e}")
    finally:
        s.close()

def page_utility_reading(user, role):
    """水电抄表页面"""
    st.title("💧⚡ 水电抄表")
    
    s = SessionLocal()
    try:
        t1, t2 = st.tabs(["抄表录入", "历史记录"])
        
        with t1:
            meter_type = st.selectbox("表类型", ["水表", "电表"])
            meters = s.query(UtilityMeter).filter(UtilityMeter.meter_type == meter_type, UtilityMeter.status == '正常', UtilityMeter.is_deleted.is_(False)).all()
            
            if meters:
                reading_date = st.date_input("抄表日期", value=datetime.date.today())
                period = st.text_input("账期", value=reading_date.strftime("%Y-%m"))
                
                reading_data = []
                for m in meters:
                    last_reading = s.query(UtilityReading).filter(UtilityReading.meter_id == m.id).order_by(desc(UtilityReading.reading_date)).first()
                    prev_reading = last_reading.current_reading if last_reading else 0.0
                    reading_data.append({"表号": m.meter_number, "上次读数": prev_reading, "本次读数": 0.0, "单价": m.unit_price})
                
                df = pd.DataFrame(reading_data)
                edited_df = st.data_editor(df, column_config={
                    "表号": st.column_config.TextColumn("表号", disabled=True),
                    "上次读数": st.column_config.NumberColumn("上次读数", disabled=True),
                    "本次读数": st.column_config.NumberColumn("本次读数", min_value=0.0),
                    "单价": st.column_config.NumberColumn("单价", disabled=True)
                }, hide_index=True, use_container_width=True)
                
                if st.button("🚀 确认录入", type="primary"):
                    try:
                        with transaction_scope() as (s_trx, audit_buffer):
                            count = 0
                            for idx, row in edited_df.iterrows():
                                current = float(row['本次读数'])
                                previous = float(row['上次读数'])
                                if current > previous:
                                    meter = s_trx.query(UtilityMeter).filter(UtilityMeter.meter_number == row['表号']).first()
                                    if meter:
                                        usage = current - previous
                                        amount = usage * float(row['单价'])
                                        reading = UtilityReading(meter_id=meter.id, reading_date=reading_date,
                                            previous_reading=previous, current_reading=current, usage=usage,
                                            unit_price=float(row['单价']), amount=amount, period=period, operator=user)
                                        s_trx.add(reading)
                                        count += 1
                            AuditService.log_deferred(s_trx, audit_buffer, user, "抄表录入", period, {"表类型": meter_type, "表数": count})
                        st.success(f"✅ 成功录入 {count} 个表的读数")
                        time.sleep(1)
                        st.rerun()
                    except Exception as e:
                        st.error(f"录入失败: {e}")
            else:
                st.warning(f"暂无{meter_type}记录")
        
        with t2:
            readings = s.query(UtilityReading, UtilityMeter).join(UtilityMeter, UtilityReading.meter_id == UtilityMeter.id).order_by(desc(UtilityReading.reading_date)).limit(200).all()
            if readings:
                st.dataframe(pd.DataFrame([{"抄表日期": r.reading_date.strftime("%Y-%m-%d"), "表类型": m.meter_type,
                    "表号": m.meter_number, "上次读数": r.previous_reading, "本次读数": r.current_reading,
                    "用量": r.usage, "金额": f"¥{r.amount:.2f}"} for r, m in readings]), use_container_width=True)
            else:
                st.info("暂无抄表记录")
    finally:
        s.close()
