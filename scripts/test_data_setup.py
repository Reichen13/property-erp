#!/usr/bin/env python3
"""测试数据初始化脚本 - 验证业务逻辑"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime
from models import SessionLocal, Base, engine
from models.entities import Property, User, Room, FeeType, Account, Bill, PaymentRecord, LedgerEntry
from services.auth import AuthService
from sqlalchemy.sql import func


def init_accounts(s):
    """初始化会计科目"""
    accounts = [(1, "现金", "asset"), (2, "物业费收入", "revenue"), (3, "预收账款", "liability")]
    for acc_id, name, nature in accounts:
        if not s.get(Account, acc_id):
            s.add(Account(id=acc_id, name=name, nature=nature))
    s.commit()
    print("✅ 会计科目初始化完成")


def init_fee_types(s):
    """初始化费用类型"""
    if not s.query(FeeType).filter_by(name="物业费").first():
        s.add(FeeType(name="物业费", tax_rate=0.06))
    s.commit()
    print("✅ 费用类型初始化完成")


def init_property_and_admin(s):
    """初始化物业和管理员"""
    prop = s.query(Property).filter_by(code="test").first()
    if not prop:
        prop = Property(name="测试物业", code="test")
        s.add(prop)
        s.flush()
    if not s.query(User).filter_by(username="admin").first():
        s.add(User(username="admin", password_hash=AuthService.hash_password("admin123"), role="管理员", property_id=prop.id))
    s.commit()
    print("✅ 物业和用户初始化完成")
    return prop.id


def init_test_room(s, property_id):
    """初始化测试房产"""
    room = s.query(Room).filter_by(room_number="TEST-001").first()
    if not room:
        room = Room(room_number="TEST-001", owner_name="测试业主", area=100.0, balance=0.0, property_id=property_id)
        s.add(room)
        s.commit()
    print(f"✅ 测试房产初始化完成: {room.room_number}")
    return room


def simulate_recharge(s, room, amount):
    """模拟充值：增加余额 + 创建收款记录 + 分录"""
    room.balance += amount
    pr = PaymentRecord(room_id=room.id, amount=amount, biz_type="充值", pay_method="微信", operator="admin")
    s.add(pr)
    s.flush()
    period = datetime.now().strftime("%Y-%m")
    # 借方=现金(1)，贷方=预收账款(3)
    s.add(LedgerEntry(period=period, account_id=1, amount=amount, direction=1, side="debit", room_id=room.id, ref_payment_id=pr.id))
    s.add(LedgerEntry(period=period, account_id=3, amount=amount, direction=-1, side="credit", room_id=room.id, ref_payment_id=pr.id))
    s.commit()
    print(f"✅ 充值 {amount} 元，余额: {room.balance} 元")


def generate_bill(s, room, amount, period):
    """生成账单"""
    bill = Bill(room_id=room.id, fee_type="物业费", period=period, amount_due=amount, amount_paid=0.0, discount=0.0, status="待缴")
    s.add(bill)
    s.commit()
    print(f"✅ 生成账单: {amount} 元，账期: {period}")
    return bill


def simulate_payment(s, room, bill):
    """模拟余额抵扣核销：扣减余额 + 分录（不创建新收款记录）"""
    pay_val = bill.amount_due - bill.amount_paid - bill.discount
    bill.amount_paid += pay_val
    bill.status = "已缴"
    room.balance -= pay_val
    # 借方=预收账款(3)，贷方=物业费收入(2)
    s.add(LedgerEntry(period=bill.period, account_id=3, amount=pay_val, direction=1, side="debit", room_id=room.id, ref_bill_id=bill.id))
    s.add(LedgerEntry(period=bill.period, account_id=2, amount=pay_val, direction=-1, side="credit", room_id=room.id, ref_bill_id=bill.id))
    s.commit()
    print(f"✅ 核销账单 {pay_val} 元，余额: {room.balance} 元")


def verify_reconciliation(s):
    """验证三方核对"""
    print("\n" + "=" * 50)
    print("🔍 三方核对验证")
    print("=" * 50)
    
    # 1. 房产余额总和
    total_room_balance = s.query(func.sum(Room.balance)).filter(Room.is_deleted == False).scalar() or 0.0
    
    # 2. 预收账款科目余额（贷方为正，借方为负）
    ledger_balance = s.query(func.sum(LedgerEntry.amount * LedgerEntry.direction * -1)).filter(LedgerEntry.account_id == 3).scalar() or 0.0
    
    # 3. 收款记录总额（仅充值）
    total_recharge = s.query(func.sum(PaymentRecord.amount)).filter(PaymentRecord.biz_type == "充值").scalar() or 0.0
    
    # 4. 账单已缴总额
    total_paid = s.query(func.sum(Bill.amount_paid)).scalar() or 0.0
    
    print(f"房产余额总和:     {total_room_balance:.2f} 元")
    print(f"预收账款科目余额: {ledger_balance:.2f} 元")
    print(f"充值总额:         {total_recharge:.2f} 元")
    print(f"账单已缴总额:     {total_paid:.2f} 元")
    print(f"预期余额(充值-已缴): {total_recharge - total_paid:.2f} 元")
    
    diff = abs(total_room_balance - ledger_balance)
    if diff < 0.01:
        print("\n✅ 三方核对通过！房产余额 = 预收账款科目余额")
        return True
    else:
        print(f"\n❌ 三方核对失败！差异: {diff:.2f} 元")
        return False


def main():
    print("=" * 50)
    print("物业ERP系统 - 业务逻辑测试")
    print("=" * 50)
    
    Base.metadata.create_all(engine)
    s = SessionLocal()
    
    try:
        init_accounts(s)
        init_fee_types(s)
        property_id = init_property_and_admin(s)
        room = init_test_room(s, property_id)
        
        print("\n--- 业务流程测试 ---")
        # 1. 充值1500元
        simulate_recharge(s, room, 1500.0)
        
        # 2. 生成200元账单
        bill = generate_bill(s, room, 200.0, "2026-01")
        
        # 3. 余额抵扣核销
        simulate_payment(s, room, bill)
        
        # 4. 验证三方核对
        success = verify_reconciliation(s)
        
        print("\n" + "=" * 50)
        if success:
            print("✅ 所有测试通过！")
        else:
            print("❌ 测试失败，请检查业务逻辑")
        print("=" * 50)
        print("\n测试账号: admin / admin123")
        
    finally:
        s.close()


if __name__ == "__main__":
    main()
