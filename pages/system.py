"""系统管理相关页面"""
import streamlit as st
import pandas as pd
import datetime
import time
import os
import shutil
import bcrypt
from models.base import SessionLocal, engine
from models.entities import Room, Bill, PaymentRecord, LedgerEntry, AuditLog, User, Account, DataChangeHistory, DiscountRequest, Invoice, PeriodClose, RoomFeeStandard
from sqlalchemy.sql import desc
from sqlalchemy import text
from config import Config
from services.audit import AuditService

def page_backup_management(user, role):
    """数据备份管理"""
    st.title("💾 数据备份管理")
    if role not in ['管理员']:
        st.error("⛔️ 权限不足")
        return
    
    st.markdown("### 📦 手动备份")
    if st.button("🚀 立即备份", type="primary"):
        try:
            backup_dir = "backups"
            os.makedirs(backup_dir, exist_ok=True)
            backup_filename = f"property_erp_backup_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
            backup_path = os.path.join(backup_dir, backup_filename)
            shutil.copy2(Config.DB_PATH, backup_path)
            file_size = os.path.getsize(backup_path) / 1024 / 1024
            st.success(f"✅ 备份成功！文件: {backup_filename}, 大小: {file_size:.2f} MB")
            AuditService.log(user, "数据备份", "手动备份", {"文件": backup_filename})
        except Exception as e:
            st.error(f"备份失败: {e}")
    
    st.markdown("---")
    st.markdown("### ⏰ 自动备份配置")
    
    # 检查cron任务是否已配置
    import subprocess
    try:
        result = subprocess.run(['crontab', '-l'], capture_output=True, text=True)
        cron_exists = 'auto_backup.py' in result.stdout
    except:
        cron_exists = False
    
    if cron_exists:
        st.success("✅ 自动备份已启用（每天凌晨2点执行）")
        if st.button("🛑 停用自动备份"):
            try:
                # 移除cron任务
                result = subprocess.run(['crontab', '-l'], capture_output=True, text=True)
                lines = [l for l in result.stdout.split('\n') if 'auto_backup.py' not in l]
                subprocess.run(['crontab', '-'], input='\n'.join(lines), text=True)
                st.success("✅ 自动备份已停用")
                AuditService.log(user, "停用自动备份", "系统配置", {})
                time.sleep(1)
                st.rerun()
            except Exception as e:
                st.error(f"停用失败: {e}")
    else:
        st.warning("⚠️ 自动备份未启用")
        if st.button("🚀 启用自动备份（每天凌晨2点）"):
            try:
                # 添加cron任务
                script_path = os.path.join(os.getcwd(), 'erp_modular/scripts/auto_backup.py')
                cron_line = f"0 2 * * * cd {os.getcwd()} && /usr/bin/python3 {script_path} >> /tmp/backup.log 2>&1"
                
                result = subprocess.run(['crontab', '-l'], capture_output=True, text=True)
                existing_cron = result.stdout if result.returncode == 0 else ""
                new_cron = existing_cron.rstrip() + '\n' + cron_line + '\n'
                
                subprocess.run(['crontab', '-'], input=new_cron, text=True, check=True)
                st.success("✅ 自动备份已启用！每天凌晨2点自动执行")
                AuditService.log(user, "启用自动备份", "系统配置", {"schedule": "每天凌晨2点"})
                time.sleep(1)
                st.rerun()
            except Exception as e:
                st.error(f"启用失败: {e}")
    
    st.markdown("---")
    st.markdown("### 📋 现有备份")
    backup_dir = "backups"
    if os.path.exists(backup_dir):
        backups = [f for f in os.listdir(backup_dir) if f.endswith('.db')]
        if backups:
            st.dataframe(pd.DataFrame([{"文件名": f, "大小(MB)": f"{os.path.getsize(os.path.join(backup_dir, f))/1024/1024:.2f}"} for f in backups]), use_container_width=True)

def page_system_monitor(user, role):
    """系统监控面板"""
    st.title("📊 系统监控")
    if role not in ['管理员']:
        st.error("⛔️ 权限不足")
        return
    
    s = SessionLocal()
    try:
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("房产数量", s.query(Room).filter(Room.is_deleted.is_(False)).count())
        col2.metric("账单数量", s.query(Bill).count())
        col3.metric("收款记录", s.query(PaymentRecord).count())
        col4.metric("审计日志", s.query(AuditLog).count())
        
        st.markdown("### 📝 最近操作 (Top 20)")
        recent_logs = s.query(AuditLog).order_by(desc(AuditLog.created_at)).limit(20).all()
        if recent_logs:
            st.dataframe(pd.DataFrame([{"时间": log.created_at.strftime("%Y-%m-%d %H:%M:%S"), "用户": log.user, "操作": log.action, "目标": log.target} for log in recent_logs]), use_container_width=True)
    finally:
        s.close()

def page_permission_management(user, role):
    """权限管理"""
    st.title("🔐 权限管理")
    if role not in ['管理员']:
        st.error("⛔️ 权限不足")
        return
    
    st.markdown("### 🎭 角色权限说明")
    st.dataframe(pd.DataFrame([
        {"角色": "管理员", "权限": "所有功能", "说明": "系统管理员，拥有全部权限"},
        {"角色": "集团财务", "权限": "报表查询、财务核对、数据导出、审计查询", "说明": "集团财务人员，只读为主"},
        {"角色": "项目财务", "权限": "收银台、财务管理、收费核对、账单生成、欠费查询、资源档案", "说明": "项目财务+收银"},
        {"角色": "审批员", "权限": "运营驾驶舱(查看)、减免审批、调账审批", "说明": "减免审批人员"}
    ]), use_container_width=True, hide_index=True)

def page_system_init(user, role):
    """系统初始化"""
    st.title("🔧 系统初始化")
    if role not in ['管理员']:
        st.error("⛔️ 权限不足")
        return
    
    st.info("💡 **提示**：房产档案、账单、费用台账的导入已整合到【核心业务 → 资源档案管理 → 批量导入】功能中，支持一次性导入所有数据。")
    
    st.divider()
    st.markdown("### 1️⃣ 创建数据库索引")
    if st.button("创建索引"):
        try:
            indexes = [
                "CREATE INDEX IF NOT EXISTS idx_room_number ON rooms(room_number)",
                "CREATE INDEX IF NOT EXISTS idx_bill_room_id ON bills(room_id)",
                "CREATE INDEX IF NOT EXISTS idx_bill_period ON bills(period)",
                "CREATE INDEX IF NOT EXISTS idx_payment_room_id ON payment_records(room_id)",
            ]
            with engine.connect() as conn:
                for idx_sql in indexes:
                    conn.execute(text(idx_sql))
                conn.commit()
            st.success("✅ 数据库索引创建成功")
            AuditService.log(user, "创建数据库索引", "系统初始化", {})
        except Exception as e:
            st.error(f"创建索引失败: {e}")
    
    st.markdown("### 2️⃣ 检查账户科目")
    s = SessionLocal()
    try:
        accounts = s.query(Account).all()
        if accounts:
            st.success(f"✅ 已有 {len(accounts)} 个账户科目")
        else:
            st.warning("⚠️ 未找到账户科目")
    finally:
        s.close()

def page_clear_test_data(user, role):
    """清除测试数据"""
    st.title("🗑️ 清除测试数据")
    if role not in ['管理员']:
        st.error("⛔️ 权限不足")
        return
    
    st.warning("⚠️ 此功能将清除所有业务数据，但保留系统配置和管理员账号。请谨慎操作！")
    
    s = SessionLocal()
    try:
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("房产数量", s.query(Room).filter(Room.is_deleted.is_(False)).count())
        col2.metric("账单数量", s.query(Bill).count())
        col3.metric("收款记录", s.query(PaymentRecord).count())
        col4.metric("财务分录", s.query(LedgerEntry).count())
        
        confirm_text = st.text_input("请输入 '我确认清除所有测试数据' 以继续")
        if confirm_text == "我确认清除所有测试数据":
            if st.button("🗑️ 开始清除测试数据", type="primary"):
                try:
                    s.query(DataChangeHistory).delete()
                    s.query(DiscountRequest).delete()
                    s.query(Invoice).delete()
                    s.query(PeriodClose).delete()
                    s.query(LedgerEntry).delete()
                    s.query(PaymentRecord).delete()
                    s.query(Bill).delete()
                    s.query(RoomFeeStandard).delete()
                    s.query(Room).delete()
                    s.commit()
                    AuditService.log(user, "清除测试数据", "全部", {})
                    st.success("✅ 测试数据清除成功！")
                    time.sleep(2)
                    st.rerun()
                except Exception as e:
                    s.rollback()
                    st.error(f"❌ 清除失败: {e}")
    finally:
        s.close()

def page_change_password(user, role):
    """修改密码"""
    st.title("🔐 修改密码")
    
    s = SessionLocal()
    try:
        current_user = s.query(User).filter(User.username == user).first()
        if not current_user:
            st.error("❌ 未找到当前用户信息")
            return
        
        st.info(f"**用户名**: {current_user.username} | **角色**: {current_user.role}")
        
        with st.form("change_password_form"):
            old_password = st.text_input("当前密码", type="password")
            new_password = st.text_input("新密码", type="password")
            confirm_password = st.text_input("确认新密码", type="password")
            
            if st.form_submit_button("💾 保存新密码", type="primary"):
                if not old_password or not new_password or not confirm_password:
                    st.error("❌ 请填写所有密码字段")
                    return
                if len(new_password) < 6:
                    st.error("❌ 新密码至少需要6位字符")
                    return
                if new_password != confirm_password:
                    st.error("❌ 两次输入的新密码不一致")
                    return
                
                try:
                    if not bcrypt.checkpw(old_password.encode(), current_user.password_hash.encode()):
                        st.error("❌ 当前密码不正确")
                        return
                except Exception:
                    st.error("❌ 密码验证失败")
                    return
                
                try:
                    new_password_hash = bcrypt.hashpw(new_password.encode(), bcrypt.gensalt()).decode()
                    current_user.password_hash = new_password_hash
                    s.commit()
                    AuditService.log(user, "修改密码", f"用户 {user}", {"result": "Success"})
                    st.success("✅ 密码修改成功！请使用新密码重新登录")
                except Exception as e:
                    st.error(f"❌ 密码修改失败: {e}")
                    s.rollback()
    finally:
        s.close()
