"""认证服务模块"""
import datetime
import secrets
import bcrypt
from typing import Optional
from config import config, get_logger
from models import SessionLocal, User, LoginFail, SessionToken

logger = get_logger(__name__)


class AuthService:
    @staticmethod
    def hash_password(password: str) -> str:
        return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

    @staticmethod
    def check_password(plain: str, hashed: str) -> bool:
        try:
            return bcrypt.checkpw(plain.encode(), hashed.encode())
        except Exception as e:
            logger.error(f"密码校验失败: {e}")
            return False

    @staticmethod
    def is_locked(username: str) -> bool:
        s = SessionLocal()
        try:
            rec = s.query(LoginFail).filter_by(username=username).first()
            if not rec or not rec.locked_until:
                return False
            return datetime.datetime.now() < rec.locked_until
        finally:
            s.close()

    @staticmethod
    def record_fail(username: str):
        s = SessionLocal()
        try:
            rec = s.query(LoginFail).filter_by(username=username).first()
            now = datetime.datetime.now()
            if not rec:
                rec = LoginFail(username=username, fail_count=1, updated_at=now)
                s.add(rec)
            else:
                if rec.locked_until and now < rec.locked_until:
                    pass
                else:
                    rec.fail_count += 1
                    rec.updated_at = now
                    if rec.fail_count >= config.LOGIN_MAX_FAIL:
                        rec.locked_until = now + datetime.timedelta(minutes=config.LOCK_MINUTES)
                        logger.warning(f"账号 {username} 已锁定 {config.LOCK_MINUTES} 分钟")
            s.commit()
            logger.info(f"登录失败记录: {username}, 次数: {rec.fail_count}")
        finally:
            s.close()

    @staticmethod
    def clear_fail(username: str):
        s = SessionLocal()
        try:
            rec = s.query(LoginFail).filter_by(username=username).first()
            if rec:
                rec.fail_count = 0
                rec.locked_until = None
                s.commit()
        finally:
            s.close()

    @staticmethod
    def create_session(s, user_id: int, hours: int = 8) -> str:
        token = secrets.token_urlsafe(32)
        expires = datetime.datetime.now() + datetime.timedelta(hours=hours)
        s.add(SessionToken(token=token, user_id=user_id, expires_at=expires))
        s.commit()
        logger.info(f"创建会话: user_id={user_id}, 有效期={hours}小时")
        return token

    @staticmethod
    def validate_token(s, token: str) -> Optional[User]:
        if not token:
            return None
        rec = s.query(SessionToken).filter_by(token=token).first()
        if not rec:
            return None
        if rec.expires_at < datetime.datetime.now():
            s.delete(rec)
            s.commit()
            return None
        return s.query(User).get(rec.user_id)

    @staticmethod
    def clear_token(s, token: str = None, user_id: int = None):
        q = s.query(SessionToken)
        if token:
            q = q.filter_by(token=token)
        elif user_id:
            q = q.filter_by(user_id=user_id)
        for r in q.all():
            s.delete(r)
        s.commit()
