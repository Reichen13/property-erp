"""分录服务模块 - 修复借贷平衡问题"""
import json
from typing import Optional
from models import SessionLocal, LedgerEntry, PeriodClose, Account
from config import get_logger
from utils.exceptions import PeriodClosedError, ValidationError

logger = get_logger(__name__)


class LedgerService:
    @staticmethod
    def is_period_closed(period: str, s=None) -> bool:
        if s is None:
            s = SessionLocal()
            try:
                pc = s.query(PeriodClose).filter_by(period=period).first()
                return bool(pc and pc.closed)
            finally:
                s.close()
        pc = s.query(PeriodClose).filter_by(period=period).first()
        return bool(pc and pc.closed)

    @staticmethod
    def post_double_entry(s, period: str, debit_account_id: int, credit_account_id: int,
                          amount: float, room_id: int = None, ref_bill_id: int = None,
                          ref_payment_id: int = None, details: dict = None):
        """
        复式记账：同时生成借方和贷方分录，确保借贷平衡
        debit_account_id: 借方科目
        credit_account_id: 贷方科目
        amount: 金额（正数）
        """
        if LedgerService.is_period_closed(period, s):
            logger.warning(f"尝试在已关账期 {period} 记账")
            raise PeriodClosedError(f"账期 {period} 已关账")
        if amount <= 0:
            logger.warning(f"无效金额: {amount}")
            raise ValidationError("金额必须大于0")
        
        detail_str = json.dumps(details or {}, ensure_ascii=False)
        
        # 借方分录 (direction=1)
        s.add(LedgerEntry(
            room_id=room_id, account_id=debit_account_id, amount=amount,
            period=period, ref_bill_id=ref_bill_id, ref_payment_id=ref_payment_id,
            details=detail_str, direction=1, side='debit'
        ))
        
        # 贷方分录 (direction=-1)
        s.add(LedgerEntry(
            room_id=room_id, account_id=credit_account_id, amount=amount,
            period=period, ref_bill_id=ref_bill_id, ref_payment_id=ref_payment_id,
            details=detail_str, direction=-1, side='credit'
        ))
        logger.info(f"复式记账: 借方={debit_account_id}, 贷方={credit_account_id}, 金额={amount}, 账期={period}")

    @staticmethod
    def post_single(s, room_id: Optional[int], account_id: int, amount: float,
                    period: str, ref_bill_id: int = None, ref_payment_id: int = None,
                    details: dict = None, direction: int = None, side: str = None):
        """单边分录（兼容旧逻辑）"""
        if LedgerService.is_period_closed(period, s):
            logger.warning(f"尝试在已关账期 {period} 记账")
            raise PeriodClosedError(f"账期 {period} 已关账")
        if direction is None:
            acc = s.query(Account).get(int(account_id)) if account_id else None
            nature = (acc.nature if acc else '').lower()
            base_dir = 1 if nature == 'asset' else -1
            direction = base_dir if amount >= 0 else -base_dir
            side = nature or side
        
        s.add(LedgerEntry(
            room_id=room_id, account_id=account_id, amount=float(amount),
            period=period, ref_bill_id=ref_bill_id, ref_payment_id=ref_payment_id,
            details=json.dumps(details or {}, ensure_ascii=False),
            direction=int(direction), side=side
        ))
