#!/usr/bin/env python3
"""自动备份脚本 - 可通过cron定时执行"""
import os
import shutil
import datetime
import glob

# 配置
DB_PATH = "/home/ubuntu/erp/property_erp_1.7.1.db"
BACKUP_DIR = "/home/ubuntu/erp/erp_modular/backups"
MAX_BACKUPS = 30  # 保留最近30个备份

def backup():
    """执行数据库备份"""
    os.makedirs(BACKUP_DIR, exist_ok=True)
    
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_name = f"property_erp_{timestamp}.db"
    backup_path = os.path.join(BACKUP_DIR, backup_name)
    
    # 复制数据库文件
    shutil.copy2(DB_PATH, backup_path)
    print(f"备份成功: {backup_path}")
    
    # 清理旧备份
    backups = sorted(glob.glob(os.path.join(BACKUP_DIR, "property_erp_*.db")))
    if len(backups) > MAX_BACKUPS:
        for old in backups[:-MAX_BACKUPS]:
            os.remove(old)
            print(f"删除旧备份: {old}")
    
    return backup_path

if __name__ == "__main__":
    backup()
