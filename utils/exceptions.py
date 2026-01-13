"""自定义异常类"""


class ERPException(Exception):
    """ERP系统基础异常"""
    pass


class AuthenticationError(ERPException):
    """认证错误"""
    pass


class AuthorizationError(ERPException):
    """授权错误"""
    pass


class ValidationError(ERPException):
    """数据验证错误"""
    pass


class PeriodClosedError(ERPException):
    """账期已关闭错误"""
    pass


class InsufficientBalanceError(ERPException):
    """余额不足错误"""
    pass


class DatabaseError(ERPException):
    """数据库操作错误"""
    pass


class ConfigurationError(ERPException):
    """配置错误"""
    pass
