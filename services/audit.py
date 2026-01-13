"""审计服务模块"""
import json
import hashlib
import datetime
import uuid
from typing import Optional
from config import config, get_logger
from models import SessionLocal, AuditLog, DataChangeHistory

logger = get_logger(__name__)


def append_worm_log(entry: dict) -> str:
    """写入WORM审计日志"""
    payload = json.dumps(entry, ensure_ascii=False)
    digest = hashlib.sha256(payload.encode()).hexdigest()
    try:
        with open(config.WORM_LOG_PATH, 'a', encoding='utf-8') as f:
            f.write(payload + "\n")
    except IOError as e:
        logger.error(f"WORM日志写入失败: {e}")
        raise
    return digest


class AuditService:
    @staticmethod
    def log(user: str, action: str, target: str, details="", 
            ip_addr: Optional[str] = None, trace_id: Optional[str] = None):
        """记录审计日志"""
        s = SessionLocal()
        try:
            entry = {
                "user": user, "action": action, "target": str(target),
                "details": details if isinstance(details, str) else json.dumps(details, ensure_ascii=False),
                "ip": ip_addr or "", "trace": trace_id or str(uuid.uuid4()),
                "ts": datetime.datetime.now().isoformat()
            }
            worm_hash = append_worm_log(entry)
            s.add(AuditLog(
                user=user, action=action, target=str(target),
                details=entry["details"], ip_addr=entry["ip"],
                trace_id=entry["trace"], worm_hash=worm_hash
            ))
            s.commit()
            logger.debug(f"审计日志: {action} -> {target}")
        except Exception as e:
            logger.error(f"审计日志写入失败: {e}")
        finally:
            s.close()

    @staticmethod
    def log_deferred(s, audit_buffer: list, user: str, action: str, 
                     target: str, details="", ip_addr: Optional[str] = None,
                     trace_id: Optional[str] = None):
        """延迟记录审计日志（用于事务）"""
        entry = {
            "user": user, "action": action, "target": str(target),
            "details": details if isinstance(details, str) else json.dumps(details, ensure_ascii=False),
            "ip": ip_addr or "", "trace": trace_id or str(uuid.uuid4()),
            "ts": datetime.datetime.now().isoformat()
        }
        worm_hash = hashlib.sha256(json.dumps(entry, ensure_ascii=False).encode()).hexdigest()
        s.add(AuditLog(
            user=user, action=action, target=str(target),
            details=entry["details"], ip_addr=entry["ip"],
            trace_id=entry["trace"], worm_hash=worm_hash
        ))
        audit_buffer.append(entry)

    @staticmethod
    def log_data_change(s, table_name: str, record_id: int, field_name: str,
                        old_value, new_value, changed_by: str, reason: str = ""):
        """记录数据变更历史"""
        if str(old_value) != str(new_value):
            s.add(DataChangeHistory(
                table_name=table_name, record_id=record_id, field_name=field_name,
                old_value=str(old_value) if old_value is not None else "",
                new_value=str(new_value) if new_value is not None else "",
                changed_by=changed_by, reason=reason
            ))
