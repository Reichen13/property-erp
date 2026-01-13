"""事务管理模块"""
from contextlib import contextmanager
from models import SessionLocal
from services.audit import append_worm_log


@contextmanager
def transaction_scope():
    """事务上下文管理器，确保原子性操作"""
    s = SessionLocal()
    audit_buffer = []
    try:
        yield s, audit_buffer
        s.commit()
        # 事务成功后写入WORM日志
        for payload in audit_buffer:
            try:
                append_worm_log(payload)
            except Exception as e:
                print(f"WORM write failed: {e}")
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()
