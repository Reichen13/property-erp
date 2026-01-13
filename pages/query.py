"""数据中心页面"""
import streamlit as st
import pandas as pd
from sqlalchemy.sql import desc
from models import SessionLocal, Bill, PaymentRecord, Room
from config import config


def page_query(user, role):
    st.title("🔍 数据中心")
    s = SessionLocal()
    try:
        t1, t2, t3 = st.tabs(["🧾 账单明细", "💹 资金流水", "📤 数据导出"])
        
        with t1:
            page = st.number_input("页码", min_value=1, value=1)
            offset = (page - 1) * config.PAGE_SIZE
            res = s.query(Bill).join(Room).filter(not Room.is_deleted).offset(offset).limit(config.PAGE_SIZE).all()
            st.dataframe(pd.DataFrame([{
                "房号": b.room.room_number, "科目": b.fee_type, "账期": b.period,
                "应收": float(b.amount_due), "减免": float(b.discount),
                "实收": float(b.amount_paid), "状态": b.status
            } for b in res]), use_container_width=True)
        
        with t2:
            res = s.query(PaymentRecord).join(Room).filter(not Room.is_deleted).order_by(desc(PaymentRecord.created_at)).limit(500).all()
            st.dataframe(pd.DataFrame([{
                "时间": r.created_at.strftime("%Y-%m-%d %H:%M"), "房号": r.room.room_number,
                "类型": r.biz_type, "金额": float(r.amount), "方式": r.pay_method, "操作人": r.operator
            } for r in res]), use_container_width=True)
        
        with t3:
            st.subheader("📤 数据导出")
            c1, c2 = st.columns(2)
            if c1.button("导出账单CSV"):
                res = s.query(Bill).limit(5000).all()
                df = pd.DataFrame([{
                    "房号": b.room_id, "科目": b.fee_type, "账期": b.period,
                    "应收": b.amount_due, "减免": b.discount, "实收": b.amount_paid, "状态": b.status
                } for b in res])
                p = "export_bills.csv"
                df.to_csv(p, index=False, encoding='utf-8-sig')
                with open(p, 'rb') as f:
                    st.download_button("下载账单CSV", f, p)
            if c2.button("导出流水CSV"):
                res = s.query(PaymentRecord).limit(5000).all()
                df = pd.DataFrame([{
                    "房号": r.room_id, "类型": r.biz_type, "金额": r.amount,
                    "方式": r.pay_method, "时间": r.created_at.strftime('%Y-%m-%d %H:%M'), "操作人": r.operator
                } for r in res])
                p = "export_payments.csv"
                df.to_csv(p, index=False, encoding='utf-8-sig')
                with open(p, 'rb') as f:
                    st.download_button("下载流水CSV", f, p)
    finally:
        s.close()
