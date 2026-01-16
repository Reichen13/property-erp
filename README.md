# 物业费用管理系统 (Property ERP)

一个基于 Streamlit 的物业费用管理系统，支持多物业管理、账单生成、收费核销、财务报表等功能。

## 功能特性

### 核心业务
- **运营驾驶舱** - 实时数据概览和关键指标展示
- **收银台** - 钱包充值、账单缴费、收据打印
- **财务管理** - 账单生成、减免申请、发票管理
- **数据中心** - 账单查询、收款记录、数据导出
- **资源档案** - 房产档案管理、批量导入、入伙登记

### 车位与水电
- **车位管理** - 车位档案、车位费账单
- **水电表管理** - 表具档案、抄表记录
- **水电抄表** - 抄表录入、费用计算

### 数据与审计
- **收费核对** - 账单与收款核对
- **三方核对** - 账单、收款、分录三方核对
- **财务检查** - 数据完整性检查
- **审计查询** - 操作日志查询
- **变更历史** - 数据变更追踪

### 报表与备份
- **收款对账** - 按支付方式统计
- **欠费追踪** - 欠费排行、催缴管理
- **财务报表** - 利润表、账期对比
- **运营收缴率** - 按入伙周期统计收缴率
- **数据备份** - 自动/手动备份

## 技术栈

- **前端框架**: Streamlit
- **后端语言**: Python 3.10+
- **数据库**: SQLite + SQLAlchemy ORM
- **认证**: Session Token + Cookie

## 快速开始

### 环境要求
- Python 3.10 或更高版本
- pip 包管理器

### 安装步骤

1. 克隆仓库
```bash
git clone https://github.com/Reichen13/property-erp.git
cd property-erp
```

2. 安装依赖
```bash
pip install -r requirements.txt
```

3. 运行应用
```bash
streamlit run app.py --server.port 8501
```

4. 访问系统
```
http://localhost:8501
```

### 默认账号
- 用户名: `admin`
- 密码: `admin123`

## 项目结构

```
erp_modular/
├── app.py                 # 主入口
├── config.py              # 配置文件
├── models/                # 数据模型
│   ├── base.py           # 数据库基类
│   └── entities.py       # 实体定义
├── pages/                 # 页面模块
│   ├── dashboard.py      # 运营驾驶舱
│   ├── cashier.py        # 收银台
│   ├── billing.py        # 财务管理
│   ├── query.py          # 数据中心
│   ├── resources.py      # 资源档案
│   └── ...
├── services/              # 业务服务
│   ├── auth.py           # 认证服务
│   ├── audit.py          # 审计服务
│   ├── billing.py        # 账单服务
│   └── ledger.py         # 分录服务
├── utils/                 # 工具函数
├── templates/             # 导入模板
├── docs/                  # 文档
└── tests/                 # 测试用例
```

## 数据模型

主要实体包括：
- `Room` - 房产档案
- `Bill` - 账单
- `PaymentRecord` - 收款记录
- `ServiceContract` - 服务合同
- `ParkingSpace` - 车位
- `UtilityMeter` - 水电表
- `AuditLog` - 审计日志

## 部署

### 使用 systemd 部署

1. 复制服务文件
```bash
sudo cp property-erp.service /etc/systemd/system/
```

2. 启动服务
```bash
sudo systemctl daemon-reload
sudo systemctl enable property-erp
sudo systemctl start property-erp
```

3. 查看状态
```bash
sudo systemctl status property-erp
```

## 许可证

MIT License

## 贡献

欢迎提交 Issue 和 Pull Request。
