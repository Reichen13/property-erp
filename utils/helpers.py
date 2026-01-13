"""通用工具函数"""
from decimal import Decimal


def to_decimal(val) -> Decimal:
    if val is None:
        return Decimal('0.00')
    return Decimal(str(val))


def format_money(val) -> str:
    return f"¥{to_decimal(val):,.2f}"


def mask_sensitive_data(val, role: str) -> str:
    """脱敏函数：非管理员掩盖手机号"""
    if role == '管理员':
        return val
    s = str(val)
    if len(s) == 11 and s.isdigit():
        return s[:3] + "****" + s[7:]
    return s
