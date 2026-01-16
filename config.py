"""配置管理模块"""
import os
import logging
from dataclasses import dataclass

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('erp.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)

def get_logger(name: str) -> logging.Logger:
    """获取模块日志器"""
    return logging.getLogger(name)

@dataclass
class Config:
    # 应用配置
    APP_NAME: str = os.getenv('ERP_APP_NAME', '物业费用管理系统')
    DEFAULT_ADMIN_USER: str = os.getenv('ERP_ADMIN_USER', 'admin')
    DEFAULT_ADMIN_PASS: str = os.getenv('ERP_ADMIN_PASS', 'admin123')
    
    # 数据库配置
    MASTER_DB_PATH: str = os.getenv('ERP_MASTER_DB', 'master.db')
    PROPERTY_DB_DIR: str = os.getenv('ERP_DB_DIR', 'property_dbs')
    DB_PATH: str = os.getenv('ERP_DB_PATH', '../property_erp_1.7.1.db')
    
    # 安全配置
    LOGIN_MAX_FAIL: int = int(os.getenv('ERP_LOGIN_MAX_FAIL', '5'))
    LOCK_MINUTES: int = int(os.getenv('ERP_LOCK_MINUTES', '15'))
    SESSION_HOURS: int = int(os.getenv('ERP_SESSION_HOURS', '8'))
    
    # 分页配置
    PAGE_SIZE: int = int(os.getenv('ERP_PAGE_SIZE', '50'))
    
    # 审计配置
    WORM_LOG_PATH: str = os.getenv('ERP_WORM_LOG', 'worm_audit.log')
    
    # 连接池配置
    POOL_SIZE: int = int(os.getenv('ERP_POOL_SIZE', '5'))
    MAX_OVERFLOW: int = int(os.getenv('ERP_MAX_OVERFLOW', '10'))
    POOL_TIMEOUT: int = int(os.getenv('ERP_POOL_TIMEOUT', '30'))
    
    def get_property_db_path(self, property_code: str) -> str:
        """获取物业专属数据库路径"""
        os.makedirs(self.PROPERTY_DB_DIR, exist_ok=True)
        return os.path.join(self.PROPERTY_DB_DIR, f"{property_code}.db")

config = Config()
