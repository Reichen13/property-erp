"""账单服务模块"""
from decimal import Decimal
from typing import List
from sqlalchemy.sql import func
from models import SessionLocal, Room, Bill


def to_decimal(val) -> Decimal:
    if val is None:
        return Decimal('0.00')
    return Decimal(str(val))


def format_money(val) -> str:
    return f"¥{to_decimal(val):,.2f}"


class BillingService:
    @staticmethod
    def get_room_fee_std(room: Room, fee_name: str) -> float:
        """获取房间指定费用项目的标准金额"""
        if not fee_name:
            return 0.0
        for attr_name, attr_std in [('fee1_name', 'fee1_std'), ('fee2_name', 'fee2_std'), ('fee3_name', 'fee3_std')]:
            if getattr(room, attr_name, None) == fee_name:
                return float(getattr(room, attr_std, 0.0) or 0.0)
        return 0.0

    @staticmethod
    def get_room_all_fee_items(room: Room) -> List[tuple]:
        """获取房间所有费用项目"""
        items = []
        for name_attr, std_attr in [('fee1_name', 'fee1_std'), ('fee2_name', 'fee2_std'), ('fee3_name', 'fee3_std')]:
            name = getattr(room, name_attr, None)
            std = getattr(room, std_attr, 0.0)
            if name:
                items.append((name, float(std or 0.0)))
        return items

    @staticmethod
    def generate_bills_for_period(s, period: str, fee_type: str, operator: str,
                                  gen_all: bool = True, unit_price: float = None) -> dict:
        """批量生成账单"""
        from .ledger import LedgerService
        if LedgerService.is_period_closed(period, s):
            raise Exception("该账期已关账")
        
        count = 0
        total_amt = 0.0
        skipped = 0
        
        rooms = s.query(Room).filter(Room.status != '空置', not Room.is_deleted).all()
        
        for r in rooms:
            if unit_price is not None:
                # 按单价 x 面积
                amt = float(r.area or 0.0) * unit_price
                if amt > 0:
                    exists = s.query(Bill).filter_by(room_id=r.id, fee_type=fee_type, period=period).first()
                    if exists:
                        skipped += 1
                    else:
                        s.add(Bill(room_id=r.id, fee_type=fee_type, period=period, amount_due=amt, operator=operator))
                        count += 1
                        total_amt += amt
            elif gen_all:
                # 按档案预设金额生成所有费用项目
                for fname, famt in BillingService.get_room_all_fee_items(r):
                    if famt > 0:
                        exists = s.query(Bill).filter(
                            Bill.room_id == r.id,
                            func.trim(Bill.fee_type) == fname.strip(),
                            func.trim(Bill.period) == period.strip()
                        ).first()
                        if exists:
                            skipped += 1
                        else:
                            s.add(Bill(room_id=r.id, fee_type=fname.strip(), period=period.strip(), amount_due=famt, operator=operator))
                            count += 1
                            total_amt += famt
            else:
                # 按档案预设金额生成指定费用类型
                amt = BillingService.get_room_fee_std(r, fee_type)
                if amt > 0:
                    exists = s.query(Bill).filter_by(room_id=r.id, fee_type=fee_type, period=period).first()
                    if exists:
                        skipped += 1
                    else:
                        s.add(Bill(room_id=r.id, fee_type=fee_type, period=period, amount_due=amt, operator=operator))
                        count += 1
                        total_amt += amt
        
        return {"count": count, "total": total_amt, "skipped": skipped}

    @staticmethod
    def calculate_arrears(room_id: int, s=None) -> Decimal:
        """计算房间欠费"""
        close_session = False
        if s is None:
            s = SessionLocal()
            close_session = True
        try:
            result = s.query(
                func.sum(Bill.amount_due - Bill.amount_paid - Bill.discount)
            ).filter(
                Bill.room_id == room_id,
                Bill.status != '已缴',
                Bill.status != '作废'
            ).scalar()
            return to_decimal(result)
        finally:
            if close_session:
                s.close()
