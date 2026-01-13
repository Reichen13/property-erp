"""数据库基础配置"""
from sqlalchemy import create_engine, event
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.pool import QueuePool
from config import config

Base = declarative_base()

# 数据库引擎缓存
_engines = {}
_session_factories = {}

def _setup_engine(db_path: str):
    """创建并配置数据库引擎"""
    eng = create_engine(
        f'sqlite:///{db_path}',
        connect_args={'check_same_thread': False},
        poolclass=QueuePool,
        pool_size=config.POOL_SIZE,
        max_overflow=config.MAX_OVERFLOW,
        pool_timeout=config.POOL_TIMEOUT
    )
    @event.listens_for(eng, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.close()
    return eng

def get_engine(property_code: str = None):
    """获取物业数据库引擎"""
    if property_code:
        db_path = config.get_property_db_path(property_code)
    else:
        db_path = config.DB_PATH
    if db_path not in _engines:
        _engines[db_path] = _setup_engine(db_path)
    return _engines[db_path]

def get_session_factory(property_code: str = None):
    """获取物业数据库会话工厂"""
    if property_code:
        db_path = config.get_property_db_path(property_code)
    else:
        db_path = config.DB_PATH
    if db_path not in _session_factories:
        eng = get_engine(property_code)
        _session_factories[db_path] = sessionmaker(autocommit=False, autoflush=False, bind=eng)
    return _session_factories[db_path]

def init_property_db(property_code: str):
    """初始化物业数据库表结构"""
    eng = get_engine(property_code)
    Base.metadata.create_all(eng)

# 默认引擎和会话（兼容旧代码）
engine = get_engine()
SessionLocal = get_session_factory()
