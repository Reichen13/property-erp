"""核心服务单元测试"""
import pytest
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.exceptions import PeriodClosedError, ValidationError


class TestLedgerService:
    """分录服务测试"""
    
    def test_post_double_entry_creates_two_entries(self):
        """测试复式记账生成两条分录"""
        from models.base import SessionLocal, Base, engine
        from models.entities import LedgerEntry, PeriodClose
        from services.ledger import LedgerService
        
        Base.metadata.create_all(engine)
        s = SessionLocal()
        try:
            # 清理测试数据
            s.query(LedgerEntry).delete()
            s.query(PeriodClose).delete()
            s.commit()
            
            # 执行复式记账
            LedgerService.post_double_entry(s, "2026-01", 1, 2, 100.0, room_id=1)
            s.commit()
            
            # 验证生成两条分录
            entries = s.query(LedgerEntry).filter_by(period="2026-01").all()
            assert len(entries) == 2
            
            # 验证借贷方向
            debit = [e for e in entries if e.direction == 1]
            credit = [e for e in entries if e.direction == -1]
            assert len(debit) == 1
            assert len(credit) == 1
            assert debit[0].amount == credit[0].amount == 100.0
        finally:
            s.close()
    
    def test_post_double_entry_rejects_zero_amount(self):
        """测试复式记账拒绝零金额"""
        from models.base import SessionLocal
        from services.ledger import LedgerService
        
        s = SessionLocal()
        try:
            with pytest.raises(ValidationError):
                LedgerService.post_double_entry(s, "2026-01", 1, 2, 0)
        finally:
            s.close()
    
    def test_post_double_entry_rejects_closed_period(self):
        """测试复式记账拒绝已关账期"""
        from models.base import SessionLocal
        from models.entities import PeriodClose
        from services.ledger import LedgerService
        
        s = SessionLocal()
        try:
            # 创建已关账期
            s.query(PeriodClose).filter_by(period="2026-02").delete()
            s.add(PeriodClose(period="2026-02", closed=True))
            s.commit()
            
            with pytest.raises(PeriodClosedError):
                LedgerService.post_double_entry(s, "2026-02", 1, 2, 100.0)
        finally:
            s.close()


class TestAuthService:
    """认证服务测试"""
    
    def test_hash_password_returns_different_hash(self):
        """测试密码哈希每次不同"""
        from services.auth import AuthService
        
        h1 = AuthService.hash_password("test123")
        h2 = AuthService.hash_password("test123")
        assert h1 != h2  # bcrypt每次生成不同盐值
    
    def test_check_password_validates_correctly(self):
        """测试密码校验"""
        from services.auth import AuthService
        
        hashed = AuthService.hash_password("mypassword")
        assert AuthService.check_password("mypassword", hashed)
        assert not AuthService.check_password("wrongpassword", hashed)


class TestAuditService:
    """审计服务测试"""
    
    def test_log_creates_audit_entry(self):
        """测试审计日志创建"""
        from models.base import SessionLocal, Base, engine
        from models.entities import AuditLog
        from services.audit import AuditService
        
        Base.metadata.create_all(engine)
        s = SessionLocal()
        try:
            initial_count = s.query(AuditLog).count()
            s.close()
            
            AuditService.log("test_user", "test_action", "test_target")
            
            s = SessionLocal()
            new_count = s.query(AuditLog).count()
            assert new_count == initial_count + 1
        finally:
            s.close()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
