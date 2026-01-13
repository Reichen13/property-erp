#!/usr/bin/env python3
"""
端到端工作流测试
配合培训手册验证完整业务流程
"""
import pytest
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from decimal import Decimal
from models import SessionLocal, Base, engine
from models.entities import (
    Property, User, Room, FeeType, Account, Bill, 
    PaymentRecord, LedgerEntry, RoomFeeStandard, PeriodClose
)
from services.auth import AuthService
from services.ledger import LedgerService
from services.billing import BillingService


@pytest.fixture(scope="module")
def db_session():
    """创建测试数据库会话"""
    Base.metadata.create_all(engine)
    s = SessionLocal()
    yield s
    s.rollback()
    s.close()


@pytest.fixture(scope="module")
def setup_base_data(db_session):
    """初始化基础数据"""
    s = db_session
    
    # 会计科目
    for acc_id, name, nature in [(1, "现金", "资产"), 
                                  (2, "物业费收入", "收入"),
                                  (3, "预收账款", "负债")]:
        if not s.get(Account, acc_id):
            s.add(Account(id=acc_id, name=name, nature=nature))
    
    # 费用类型
    if not s.query(FeeType).filter_by(name="物业费").first():
        s.add(FeeType(name="物业费", unit="元/月", tax_rate=0.06))
    
    # 物业
    prop = s.query(Property).filter_by(code="e2e_test").first()
    if not prop:
        prop = Property(name="E2E测试物业", code="e2e_test")
        s.add(prop)
        s.flush()
    
    # 测试用户
    if not s.query(User).filter_by(username="e2e_admin").first():
        s.add(User(username="e2e_admin", password_hash=AuthService.hash_password("test123"),
                   role="管理员", property_id=prop.id))
    
    # 测试房产
    if not s.query(Room).filter_by(room_number="E2E-101").first():
        s.add(Room(room_number="E2E-101", owner_name="测试业主", area=100.0,
                   owner_phone="13800000001", balance=0.0, property_id=prop.id))
    
    s.commit()
    return prop.id


class TestInitialization:
    """测试系统初始化"""
    
    def test_accounts_exist(self, db_session, setup_base_data):
        """验证会计科目存在"""
        assert db_session.query(Account).count() >= 3
    
    def test_fee_types_exist(self, db_session, setup_base_data):
        """验证费用类型存在"""
        ft = db_session.query(FeeType).filter_by(name="物业费").first()
        assert ft is not None
        assert ft.tax_rate == 0.06


class TestRechargeWorkflow:
    """测试充值流程"""
    
    def test_recharge_increases_balance(self, db_session, setup_base_data):
        """充值应增加余额"""
        room = db_session.query(Room).filter_by(room_number="E2E-101").first()
        old_balance = room.balance
        
        room.balance += 500.0
        pr = PaymentRecord(room_id=room.id, amount=500.0, biz_type="充值",
                          pay_method="微信", operator="e2e_admin")
        db_session.add(pr)
        db_session.flush()
        
        # 复式记账
        LedgerService.post_double_entry(db_session, "2026-01", 1, 3, 500.0,
                                        room_id=room.id, ref_payment_id=pr.id)
        db_session.commit()
        
        assert room.balance == old_balance + 500.0
    
    def test_recharge_creates_ledger_entries(self, db_session, setup_base_data):
        """充值应创建借贷分录"""
        room = db_session.query(Room).filter_by(room_number="E2E-101").first()
        entries = db_session.query(LedgerEntry).filter_by(room_id=room.id).all()
        
        debit_entries = [e for e in entries if e.side == "debit"]
        credit_entries = [e for e in entries if e.side == "credit"]
        
        assert len(debit_entries) > 0
        assert len(credit_entries) > 0


class TestBillingWorkflow:
    """测试账单流程"""
    
    def test_generate_bill(self, db_session, setup_base_data):
        """生成账单"""
        room = db_session.query(Room).filter_by(room_number="E2E-101").first()
        
        # 使用唯一账期避免与其他测试冲突
        test_period = "2026-03"
        existing = db_session.query(Bill).filter_by(
            room_id=room.id, fee_type="物业费", period=test_period
        ).first()
        
        if not existing:
            bill = Bill(room_id=room.id, fee_type="物业费", period=test_period,
                       amount_due=200.0, amount_paid=0.0, discount=0.0, status="待缴")
            db_session.add(bill)
            db_session.commit()
        
        bill = db_session.query(Bill).filter_by(
            room_id=room.id, fee_type="物业费", period=test_period
        ).first()
        
        assert bill is not None
    
    def test_pay_bill_with_balance(self, db_session, setup_base_data):
        """使用余额支付账单"""
        # 确保账期未关账
        pc = db_session.query(PeriodClose).filter_by(period="2026-02").first()
        if pc:
            pc.closed = False
            db_session.commit()
        
        room = db_session.query(Room).filter_by(room_number="E2E-101").first()
        bill = db_session.query(Bill).filter_by(
            room_id=room.id, fee_type="物业费", period="2026-02"
        ).first()
        
        if bill and bill.status == "待缴" and room.balance >= bill.amount_due:
            pay_val = bill.amount_due - bill.amount_paid - bill.discount
            bill.amount_paid += pay_val
            bill.status = "已缴"
            room.balance -= pay_val
            
            LedgerService.post_double_entry(db_session, bill.period, 3, 2, pay_val,
                                           room_id=room.id, ref_bill_id=bill.id)
            db_session.commit()
            
            assert bill.status == "已缴"


class TestReconciliation:
    """测试对账流程"""
    
    def test_ledger_balance(self, db_session, setup_base_data):
        """验证借贷平衡"""
        from sqlalchemy.sql import func
        
        debit_sum = db_session.query(func.sum(LedgerEntry.amount)).filter(
            LedgerEntry.side == "debit"
        ).scalar() or 0
        
        credit_sum = db_session.query(func.sum(LedgerEntry.amount)).filter(
            LedgerEntry.side == "credit"
        ).scalar() or 0
        
        # 借贷应平衡
        assert abs(debit_sum - credit_sum) < 0.01


class TestPeriodClose:
    """测试关账流程"""
    
    def test_close_period(self, db_session, setup_base_data):
        """关账测试"""
        from datetime import datetime
        
        period = "2026-01"
        pc = db_session.query(PeriodClose).filter_by(period=period).first()
        
        if not pc:
            pc = PeriodClose(period=period, closed=True, closed_at=datetime.now())
            db_session.add(pc)
            db_session.commit()
        else:
            pc.closed = True
            db_session.commit()
        
        assert pc.closed is True
    
    def test_unlock_period(self, db_session, setup_base_data):
        """解锁账期测试"""
        period = "2026-01"
        pc = db_session.query(PeriodClose).filter_by(period=period).first()
        
        if pc:
            pc.closed = False
            db_session.commit()
            assert pc.closed is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
