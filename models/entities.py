"""数据库实体模型"""
import datetime
import uuid
from sqlalchemy import (
    Column, Integer, String, Float, DateTime, ForeignKey, Text, Boolean
)
from sqlalchemy.orm import relationship
from .base import Base


class Property(Base):
    __tablename__ = 'properties'
    id = Column(Integer, primary_key=True)
    name = Column(String(100), unique=True, nullable=False)
    code = Column(String(50), unique=True, nullable=False)
    address = Column(String(200))
    is_deleted = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.datetime.now)


class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    username = Column(String(50), unique=True, nullable=False)
    password_hash = Column(String(200), nullable=False)
    role = Column(String(20), nullable=False)
    property_id = Column(Integer, ForeignKey('properties.id'), nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.now)
    property = relationship("Property")


class Room(Base):
    __tablename__ = 'rooms'
    id = Column(Integer, primary_key=True)
    property_id = Column(Integer, ForeignKey('properties.id'), nullable=False, default=1)
    room_number = Column(String(50), nullable=False)
    owner_name = Column(String(50))
    area = Column(Float, default=0.0)
    contact_info = Column(String(50))
    status = Column(String(20), default='已入住')
    balance = Column(Float, default=0.0)
    standard_fee = Column(Float, default=0.0)
    is_deleted = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.datetime.now)
    owner_phone = Column(String(30))
    fee1_name = Column(String(50))
    fee1_std = Column(Float, default=0.0)
    fee2_name = Column(String(50))
    fee2_std = Column(Float, default=0.0)
    fee3_name = Column(String(50))
    fee3_std = Column(Float, default=0.0)
    
    bills = relationship("Bill", back_populates="room")
    payments = relationship("PaymentRecord", back_populates="room")
    property = relationship("Property")


class FeeType(Base):
    __tablename__ = 'fee_types'
    id = Column(Integer, primary_key=True)
    name = Column(String(50), unique=True, nullable=False)
    tax_rate = Column(Float, default=0.0)


class RoomFeeStandard(Base):
    __tablename__ = 'room_fee_standards'
    id = Column(Integer, primary_key=True)
    room_id = Column(Integer, ForeignKey('rooms.id'), nullable=False)
    fee_name = Column(String(50), nullable=False)
    std_amount = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.datetime.now)


class Account(Base):
    __tablename__ = 'accounts'
    id = Column(Integer, primary_key=True)
    name = Column(String(50), unique=True, nullable=False)
    nature = Column(String(20), nullable=False)
    is_active = Column(Boolean, default=True)


class LedgerEntry(Base):
    __tablename__ = 'ledger_entries'
    id = Column(Integer, primary_key=True)
    room_id = Column(Integer, ForeignKey('rooms.id'), nullable=True)
    account_id = Column(Integer, ForeignKey('accounts.id'), nullable=False)
    amount = Column(Float, nullable=False)
    period = Column(String(7), nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.now)
    ref_bill_id = Column(Integer, ForeignKey('bills.id'), nullable=True)
    ref_payment_id = Column(Integer, ForeignKey('payment_records.id'), nullable=True)
    details = Column(Text)
    direction = Column(Integer, nullable=False, default=1)
    side = Column(String(20), nullable=True)


class PeriodClose(Base):
    __tablename__ = 'period_close'
    id = Column(Integer, primary_key=True)
    period = Column(String(7), unique=True, nullable=False)
    closed = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.datetime.now)
    closed_at = Column(DateTime, nullable=True)
    remark = Column(Text)


class Bill(Base):
    __tablename__ = 'bills'
    id = Column(Integer, primary_key=True)
    room_id = Column(Integer, ForeignKey('rooms.id'))
    fee_type = Column(String(50))
    period = Column(String(50))
    accounting_period = Column(String(7), nullable=True)  # 会计归属期 YYYY-MM
    amount_due = Column(Float, default=0.0)
    amount_paid = Column(Float, default=0.0)
    discount = Column(Float, default=0.0)
    status = Column(String(20), default='未缴')
    created_at = Column(DateTime, default=datetime.datetime.now)
    operator = Column(String(50))
    remark = Column(String(200))
    origin_id = Column(Integer, nullable=True)
    batch_id = Column(String(36), nullable=True)
    parking_space_id = Column(Integer, ForeignKey('parking_spaces.id'), nullable=True)
    
    room = relationship("Room", back_populates="bills")
    parking_space = relationship("ParkingSpace", back_populates="bills")


class PaymentRecord(Base):
    __tablename__ = 'payment_records'
    id = Column(Integer, primary_key=True)
    room_id = Column(Integer, ForeignKey('rooms.id'))
    amount = Column(Float, nullable=False)
    biz_type = Column(String(20))
    pay_method = Column(String(20))
    created_at = Column(DateTime, default=datetime.datetime.now)
    operator = Column(String(50))
    remark = Column(String(200))
    original_payment_id = Column(Integer, nullable=True)
    trace_id = Column(String(36), nullable=True)
    
    room = relationship("Room", back_populates="payments")


class AuditLog(Base):
    __tablename__ = 'audit_logs'
    id = Column(Integer, primary_key=True)
    user = Column(String(50))
    action = Column(String(50))
    target = Column(String(100))
    details = Column(Text)
    ip_addr = Column(String(20))
    trace_id = Column(String(36), default=lambda: str(uuid.uuid4()), unique=True)
    created_at = Column(DateTime, default=datetime.datetime.now)
    worm_hash = Column(String(64), nullable=True)


class LoginFail(Base):
    __tablename__ = 'login_fail'
    id = Column(Integer, primary_key=True)
    username = Column(String(50), unique=True)
    fail_count = Column(Integer, default=0)
    locked_until = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, default=datetime.datetime.now)


class Invoice(Base):
    __tablename__ = 'invoices'
    id = Column(Integer, primary_key=True)
    bill_id = Column(Integer, ForeignKey('bills.id'), nullable=False)
    invoice_no = Column(String(50), unique=True, nullable=False)
    title = Column(String(100), nullable=False)
    tax_rate = Column(Float, default=0.0)
    amount_excl_tax = Column(Float, nullable=False)
    tax_amount = Column(Float, nullable=False)
    amount_incl_tax = Column(Float, nullable=False)
    status = Column(String(20), default='已开具')
    created_at = Column(DateTime, default=datetime.datetime.now)


class DiscountRequest(Base):
    __tablename__ = 'discount_requests'
    id = Column(Integer, primary_key=True)
    bill_id = Column(Integer, ForeignKey('bills.id'), nullable=False)
    requested_by = Column(String(50), nullable=False)
    amount = Column(Float, nullable=False)
    reason = Column(String(200))
    status = Column(String(20), default='待审核')
    created_at = Column(DateTime, default=datetime.datetime.now)
    approved_by = Column(String(50), nullable=True)
    approved_at = Column(DateTime, nullable=True)
    remark = Column(String(200), nullable=True)


class AdjustmentEntry(Base):
    __tablename__ = 'adjustment_entries'
    id = Column(Integer, primary_key=True)
    bill_id = Column(Integer, ForeignKey('bills.id'), nullable=False)
    amount = Column(Float, nullable=False)
    reason = Column(String(200))
    approved_by = Column(String(50))
    approved_at = Column(DateTime, default=datetime.datetime.now)


class ParkingType(Base):
    __tablename__ = 'parking_types'
    id = Column(Integer, primary_key=True)
    name = Column(String(50), unique=True, nullable=False)
    is_deleted = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.datetime.now)


class ParkingSpace(Base):
    __tablename__ = 'parking_spaces'
    id = Column(Integer, primary_key=True)
    space_number = Column(String(20), unique=True, nullable=False)
    area = Column(Float, default=0.0)
    space_type = Column(String(20), default='地下车位')
    room_id = Column(Integer, ForeignKey('rooms.id'), nullable=True)
    owner_name = Column(String(50))
    owner_phone = Column(String(30))
    status = Column(String(20), default='闲置')
    balance = Column(Float, default=0.0)
    fee_monthly = Column(Float, default=0.0)
    management_fee = Column(Float, default=0.0)
    is_deleted = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.datetime.now)
    remark = Column(String(200))
    
    room = relationship("Room")
    bills = relationship("Bill", back_populates="parking_space")


class UtilityMeter(Base):
    __tablename__ = 'utility_meters'
    id = Column(Integer, primary_key=True)
    meter_number = Column(String(50), unique=True, nullable=False)
    meter_type = Column(String(10), nullable=False)
    room_id = Column(Integer, ForeignKey('rooms.id'), nullable=True)
    parking_space_id = Column(Integer, ForeignKey('parking_spaces.id'), nullable=True)
    unit_price = Column(Float, default=0.0)
    status = Column(String(20), default='正常')
    is_deleted = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.datetime.now)
    remark = Column(String(200))
    
    room = relationship("Room")
    parking_space = relationship("ParkingSpace")
    readings = relationship("UtilityReading", back_populates="meter")


class UtilityReading(Base):
    __tablename__ = 'utility_readings'
    id = Column(Integer, primary_key=True)
    meter_id = Column(Integer, ForeignKey('utility_meters.id'), nullable=False)
    reading_date = Column(DateTime, default=datetime.datetime.now)
    previous_reading = Column(Float, default=0.0)
    current_reading = Column(Float, default=0.0)
    usage = Column(Float, default=0.0)
    unit_price = Column(Float, default=0.0)
    amount = Column(Float, default=0.0)
    period = Column(String(7))
    operator = Column(String(50))
    remark = Column(String(200))
    created_at = Column(DateTime, default=datetime.datetime.now)
    
    meter = relationship("UtilityMeter", back_populates="readings")


class ServiceContract(Base):
    __tablename__ = 'service_contracts'
    id = Column(Integer, primary_key=True)
    room_id = Column(Integer, ForeignKey('rooms.id'), nullable=False)
    contract_no = Column(String(50), unique=True, nullable=False)
    start_date = Column(DateTime, nullable=False)
    end_date = Column(DateTime)
    sign_date = Column(DateTime)
    property_fee_per_sqm = Column(Float, default=0.0)
    elevator_fee = Column(Float, default=0.0)
    status = Column(String(20), default='生效中')
    remark = Column(Text)
    created_by = Column(String(50))
    created_at = Column(DateTime, default=datetime.datetime.now)
    
    room = relationship("Room")


class DataChangeHistory(Base):
    __tablename__ = 'data_change_history'
    id = Column(Integer, primary_key=True)
    table_name = Column(String(50), nullable=False)
    record_id = Column(Integer, nullable=False)
    field_name = Column(String(50), nullable=False)
    old_value = Column(Text)
    new_value = Column(Text)
    changed_by = Column(String(50), nullable=False)
    changed_at = Column(DateTime, default=datetime.datetime.now)
    reason = Column(String(200))


class SessionToken(Base):
    __tablename__ = 'session_tokens'
    id = Column(Integer, primary_key=True)
    token = Column(String(128), unique=True, nullable=False, index=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.now)
