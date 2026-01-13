#!/usr/bin/env python3
"""
测试数据初始化脚本
配合培训手册使用，创建完整的测试环境
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime
from models import SessionLocal, Base, engine
from models.entities import (
    Property, User, Room, FeeType, Account, Bill, 
    PaymentRecord, LedgerEntry, RoomFeeStandard
)
from services.auth import AuthService


def init_accounts(s):
    """初始化会计科目"""
    accounts = [
        (1, "现金", "资产"),
        (2, "物业费收入", "收入"),
        (3, "预收账款", "负债"),
    ]
    for acc_id, name, nature in accounts:
        if not s.get(Account, acc_id):
            s.add(Account(id=acc_id, name=name, nature=nature))
    s.commit()
    print("✅ 会计科目初始化完成")


def init_fee_types(s):
    """初始化费用类型"""
    fee_types = [
        FeeType(name="物业费", unit="元/月", tax_rate=0.06),
        FeeType(name="停车费", unit="元/月", tax_rate=0.06),
        FeeType(name="水费", unit="元/吨", tax_rate=0.03),
        FeeType(name="电费", unit="元/度", tax_rate=0.03),
    ]
    for ft in fee_types:
        if not s.query(FeeType).filter_by(name=ft.name).first():
            s.add(ft)
    s.commit()
    print("✅ 费用类型初始化完成")


def init_property_and_admin(s):
    """初始化物业和管理员"""
    prop = s.query(Property).filter_by(code="test").first()
    if not prop:
        prop = Property(name="测试物业", code="test")
        s.add(prop)
        s.flush()
    
    # 创建测试用户
    users = [
        ("admin", "admin123", "管理员"),
        ("finance", "finance123", "财务"),
        ("cashier", "cashier123", "收银员"),
    ]
    for username, password, role in users:
        if not s.query(User).filter_by(username=username).first():
            s.add(User(
                username=username,
                password_hash=AuthService.hash_password(password),
                role=role,
                property_id=prop.id
            ))
    s.commit()
    print("✅ 物业和用户初始化完成")
    return prop.id


def init_rooms(s, property_id):
    """初始化房产档案"""
    rooms_data = [
        ("1-101", "张三", 89.5, "13800001001"),
        ("1-102", "李四", 120.0, "13800001002"),
        ("1-201", "王五", 89.5, "13800001003"),
        ("1-202", "赵六", 120.0, "13800001004"),
        ("2-101", "钱七", 95.0, "13800001005"),
        ("2-102", "孙八", 110.0, "13800001006"),
    ]
    
    for room_number, owner, area, phone in rooms_data:
        if not s.query(Room).filter_by(room_number=room_number).first():
            s.add(Room(
                room_number=room_number,
                owner_name=owner,
                area=area,
                owner_phone=phone,
                balance=0.0,
                property_id=property_id
            ))
    s.commit()
    print(f"✅ 房产档案初始化完成 ({len(rooms_data)} 条)")


def init_fee_standards(s):
    """初始化收费标准"""
    rooms = s.query(Room).all()
    fee_types = s.query(FeeType).all()
    
    standards = {
        "物业费": lambda r: r.area * 2.0,  # 2元/㎡
        "停车费": lambda r: 150.0,  # 固定150元
    }
    
    count = 0
    for room in rooms:
        for ft in fee_types:
            if ft.name in standards:
                existing = s.query(RoomFeeStandard).filter_by(
                    room_id=room.id, fee_name=ft.name
                ).first()
                if not existing:
                    s.add(RoomFeeStandard(
                        room_id=room.id,
                        fee_name=ft.name,
                        std_amount=standards[ft.name](room)
                    ))
                    count += 1
    s.commit()
    print(f"✅ 收费标准初始化完成 ({count} 条)")


def generate_test_bills(s, period="2026-01"):
    """生成测试账单"""
    rooms = s.query(Room).all()
    standards = {}
    for rfs in s.query(RoomFeeStandard).all():
        if rfs.room_id not in standards:
            standards[rfs.room_id] = {}
        standards[rfs.room_id][rfs.fee_name] = rfs.std_amount
    
    count = 0
    for room in rooms:
        room_standards = standards.get(room.id, {})
        for fee_type, amount in room_standards.items():
            existing = s.query(Bill).filter_by(
                room_id=room.id, fee_type=fee_type, period=period
            ).first()
            if not existing:
                s.add(Bill(
                    room_id=room.id,
                    fee_type=fee_type,
                    period=period,
                    amount_due=amount,
                    amount_paid=0.0,
                    discount=0.0,
                    status="待缴"
                ))
                count += 1
    s.commit()
    print(f"✅ 测试账单生成完成 ({count} 条，账期: {period})")


def simulate_recharge(s, room_number, amount, operator="admin"):
    """模拟充值操作"""
    room = s.query(Room).filter_by(room_number=room_number).first()
    if not room:
        print(f"❌ 房号 {room_number} 不存在")
        return
    
    room.balance += amount
    pr = PaymentRecord(
        room_id=room.id,
        amount=amount,
        biz_type="充值",
        pay_method="微信",
        operator=operator
    )
    s.add(pr)
    s.flush()
    
    period = datetime.now().strftime("%Y-%m")
    # 复式记账
    s.add(LedgerEntry(period=period, account_id=1, amount=amount, direction=1, 
                      side="debit", room_id=room.id, ref_payment_id=pr.id))
    s.add(LedgerEntry(period=period, account_id=3, amount=amount, direction=-1, 
                      side="credit", room_id=room.id, ref_payment_id=pr.id))
    s.commit()
    print(f"✅ 充值成功: {room_number} +{amount}元，余额: {room.balance}元")


def simulate_payment(s, room_number, operator="admin"):
    """模拟缴费操作（使用余额抵扣所有待缴账单）"""
    room = s.query(Room).filter_by(room_number=room_number).first()
    if not room:
        print(f"❌ 房号 {room_number} 不存在")
        return
    
    bills = s.query(Bill).filter(
        Bill.room_id == room.id, 
        Bill.status.in_(["待缴", "部分已缴"])
    ).all()
    
    if not bills:
        print(f"ℹ️ {room_number} 无待缴账单")
        return
    
    total = sum(b.amount_due - b.amount_paid - b.discount for b in bills)
    if room.balance < total:
        print(f"❌ 余额不足: 需要{total}元，余额{room.balance}元")
        return
    
    for bill in bills:
        pay_val = bill.amount_due - bill.amount_paid - bill.discount
        bill.amount_paid += pay_val
        bill.status = "已缴"
        # 复式记账
        s.add(LedgerEntry(period=bill.period, account_id=3, amount=pay_val, 
                          direction=1, side="debit", room_id=room.id, ref_bill_id=bill.id))
        s.add(LedgerEntry(period=bill.period, account_id=2, amount=pay_val, 
                          direction=-1, side="credit", room_id=room.id, ref_bill_id=bill.id))
    
    room.balance -= total
    s.add(PaymentRecord(room_id=room.id, amount=total, biz_type="缴费", 
                        pay_method="余额抵扣", operator=operator))
    s.commit()
    print(f"✅ 缴费成功: {room_number} 支付{total}元，剩余余额: {room.balance}元")


def main():
    """主函数"""
    print("=" * 50)
    print("物业ERP系统 - 测试数据初始化")
    print("=" * 50)
    
    Base.metadata.create_all(engine)
    s = SessionLocal()
    
    try:
        # 基础数据初始化
        init_accounts(s)
        init_fee_types(s)
        property_id = init_property_and_admin(s)
        init_rooms(s, property_id)
        init_fee_standards(s)
        
        # 生成测试账单
        generate_test_bills(s, "2026-01")
        
        # 模拟业务操作
        print("\n--- 模拟业务操作 ---")
        simulate_recharge(s, "1-101", 500.0)
        simulate_recharge(s, "1-102", 1000.0)
        simulate_payment(s, "1-101")
        
        print("\n" + "=" * 50)
        print("✅ 测试数据初始化完成！")
        print("=" * 50)
        print("\n测试账号：")
        print("  管理员: admin / admin123")
        print("  财务:   finance / finance123")
        print("  收银员: cashier / cashier123")
        
    finally:
        s.close()


if __name__ == "__main__":
    main()
