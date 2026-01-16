"""运营收缴率看板"""
import streamlit as st
import pandas as pd
import datetime
from decimal import Decimal
from models.base import SessionLocal
from models.entities import Room, Bill, ServiceContract
from sqlalchemy import func, and_, or_
from utils.helpers import format_money, to_decimal


def page_operation_collection_rate(user, role):
    """运营收缴率看板"""
    st.title("📊 运营收缴率看板")
    
    if role not in ['管理员', '集团财务', '项目财务', '运营经理']:
        st.error("⛔️ 权限不足")
        return
    
    s = SessionLocal()
    try:
        # 筛选条件
        st.markdown("### 🔍 筛选条件")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            # 是否启用入伙日期筛选
            use_date_filter = st.checkbox("启用入伙日期筛选", value=False)
            if use_date_filter:
                start_date = st.date_input("入伙开始日期", value=datetime.datetime.now().replace(month=1, day=1))
                end_date = st.date_input("入伙结束日期", value=datetime.datetime.now())
            else:
                start_date = None
                end_date = None
        
        with col2:
            # 统计截止日期
            stat_date = st.date_input("统计截止日期", value=datetime.datetime.now())
        
        with col3:
            # 房号筛选
            room_filter = st.text_input("房号筛选(可选)", placeholder="输入房号关键词")
        
        # 默认自动加载数据
        # 查询所有房产
        rooms_query = s.query(Room).filter(Room.is_deleted == False)
        if room_filter:
            rooms_query = rooms_query.filter(Room.room_number.like(f"%{room_filter}%"))
        
        all_rooms = rooms_query.all()
        
        if not all_rooms:
            st.warning("未找到房产数据")
            return
        
        # 计算每户的收缴率
        data_list = []
        for room in all_rooms:
            # 尝试获取服务合同
            contract = s.query(ServiceContract).filter(
                ServiceContract.room_id == room.id
            ).first()
            
            # 确定入伙日期和周期
            if contract:
                move_in_date = contract.start_date
                cycle_end = contract.end_date or datetime.datetime.now()
                date_source = "合同"
            else:
                # 无合同：使用最早账单的账期作为入伙日期
                earliest_bill = s.query(Bill).filter(
                    Bill.room_id == room.id,
                    Bill.status != '作废'
                ).order_by(
                    func.coalesce(Bill.accounting_period, Bill.period)
                ).first()
                
                if not earliest_bill:
                    continue  # 没有账单数据，跳过
                
                period_str = earliest_bill.accounting_period or earliest_bill.period
                if not period_str:
                    continue
                try:
                    move_in_date = datetime.datetime.strptime(period_str[:7] + "-01", "%Y-%m-%d")
                except:
                    continue
                
                cycle_end = datetime.datetime.now()
                date_source = "账单"
            
            # 如果启用了入伙日期筛选，则过滤
            if use_date_filter and start_date and end_date:
                if move_in_date.date() < start_date or move_in_date.date() > end_date:
                    continue
            
            # 查询周期内的所有账单（截止到统计日期）
            stat_period = stat_date.strftime("%Y-%m")
            bills = s.query(Bill).filter(
                Bill.room_id == room.id,
                Bill.status != '作废',
                or_(
                    Bill.accounting_period.between(
                        move_in_date.strftime("%Y-%m"),
                        stat_period
                    ),
                    and_(
                        Bill.accounting_period.is_(None),
                        Bill.period.between(
                            move_in_date.strftime("%Y-%m"),
                            stat_period
                        )
                    )
                )
            ).all()
            
            if not bills:
                continue
            
            # 计算应收、已缴、减免
            total_due = sum([to_decimal(b.amount_due or 0) for b in bills])
            total_paid = sum([to_decimal(b.amount_paid or 0) for b in bills])
            total_discount = sum([to_decimal(b.discount or 0) for b in bills])
            
            # 收缴率 = (已缴 + 减免) / 应收
            collection_rate = 0.0
            if total_due > 0:
                collection_rate = float((total_paid + total_discount) / total_due * 100)
            
            data_list.append({
                "房号": room.room_number,
                "业主": room.owner_name or "",
                "入伙日期": move_in_date.strftime("%Y-%m-%d"),
                "数据来源": date_source,
                "统计截止": stat_period,
                "应收金额": float(total_due),
                "已缴金额": float(total_paid),
                "减免金额": float(total_discount),
                "未缴金额": float(total_due - total_paid - total_discount),
                "收缴率(%)": round(collection_rate, 2)
            })
        
        # 显示统计结果
        st.markdown("### 📈 收缴率统计")
        
        if not data_list:
            st.warning("没有符合条件的数据")
            return
        
        df = pd.DataFrame(data_list)
        
        # 汇总统计
        col1, col2, col3, col4 = st.columns(4)
        total_due_sum = df["应收金额"].sum()
        total_paid_sum = df["已缴金额"].sum()
        total_discount_sum = df["减免金额"].sum()
        avg_rate = (total_paid_sum + total_discount_sum) / total_due_sum * 100 if total_due_sum > 0 else 0
        
        col1.metric("总应收", format_money(total_due_sum))
        col2.metric("总已缴", format_money(total_paid_sum))
        col3.metric("总减免", format_money(total_discount_sum))
        col4.metric("整体收缴率", f"{avg_rate:.2f}%")
        
        # 显示明细表
        st.dataframe(df, use_container_width=True, height=400)
        
        st.info("💡 数据来源：'合同'=服务合同入伙日期，'账单'=最早账单账期")
        
        # 导出功能
        csv = df.to_csv(index=False, encoding='utf-8-sig')
        st.download_button(
            label="📥 导出为CSV",
            data=csv,
            file_name=f"运营收缴率_{datetime.datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv"
        )
        
        # 统计说明
        with st.expander("📋 统计说明"):
            st.markdown("""
            **入伙日期确定规则：**
            1. 优先使用服务合同中的入伙日期
            2. 如果没有服务合同，则使用该房产最早账单的账期
            
            **收缴率计算公式：**
            - 收缴率 = (已缴金额 + 减免金额) / 应收金额 × 100%
            - 应收金额 = 从入伙日期到统计截止日期期间所有账单的应收金额之和
            """)
    
    finally:
        s.close()
