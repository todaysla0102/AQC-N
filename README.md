<p align="center">
  <img src="./aqc-logo.svg" alt="AQC-N" width="180" />
</p>

<h1 align="center">AQC-N 控制台</h1>

<p align="center">
  面向零售运营的新一代业务管理平台。
</p>

## 项目简介

AQC-N 是基于原 AQC-O 业务体系重构的现代化控制台，覆盖门店经营、商品库存、销售录入、工单流转、统计报表、账号权限和历史数据迁移等核心场景。项目以统一账号登录和 AQC 独立业务数据为基础，在保留旧系统关键身份字段与接口兼容能力的同时，提供更清晰的 Web 控制台、模块化后端 API 和可重复的 Docker 部署流程。

当前版本已经从早期的“后端优先”雏形演进为完整的前后端一体项目：前端基于 Vue 3 构建响应式控制台，后端基于 FastAPI 提供业务 API、权限校验、数据导入、报表调度和旧系统兼容层。

## 核心功能

- 统一登录：接入 `account-symuse`，支持票据换取、会话刷新、退出登录、会话管理和本地测试登录。
- 仪表盘：展示销售趋势、经营概览、个人统计和业务快捷入口。
- 销售管理：支持销售录入、扫码/检索商品、销售记录查询、销售汇总和客户/商品维度检索。
- 商品管理：维护商品档案、分类属性、库存索引和旧商品数据导入。
- 店铺/仓库管理：维护门店、仓库、分组和经营相关基础资料。
- 工单管理：支持库存类工单创建、商品批量选择、审批流转、销售关联和全链路追溯。
- 订单管理：提供订单数据查询、维护和后续扩展入口。
- 目标与排班：覆盖门店目标、店铺排班和经营计划管理。
- 报表中心：提供多维经营报表、定时报表任务和报表结果查看。
- 日志中心：沉淀操作日志、系统日志和排障信息。
- 账号权限：维护 AQC 独立用户、角色、权限、分组与旧系统身份兼容字段。
- 历史兼容：保留 AQC-O 旧接口占位和导入工具，方便逐步迁移历史业务。

## 技术栈

| 层级 | 技术 |
| --- | --- |
| 前端 | Vue 3、Vue Router、Pinia、Element Plus、ECharts、ZXing、Vite |
| 后端 | FastAPI、SQLAlchemy、PyMySQL、Pydantic、Passlib、Uvicorn |
| 数据库 | MySQL 8 |
| 部署 | Docker、Docker Compose、Nginx |
| 运维 | systemd、logrotate、本地测试脚本、Docker 清理脚本 |

## 项目结构

```text
AQC-N/
├── backend/
│   ├── fastapi/          # FastAPI 后端服务、业务路由、数据模型和导入工具
│   └── mysql/            # MySQL 配置
├── client/               # Vue 3 控制台前端
├── ops/                  # 运维脚本、systemd 和 logrotate 配置
├── scripts/              # 本地测试、前端启动和冒烟测试脚本
├── docker-compose.yml    # 生产/部署编排
└── docker-compose.local-test.yml
```

## 快速开始

复制环境变量示例并按实际环境修改密钥、数据库、统一登录和第三方接口配置：

```bash
cp .env.example .env
docker compose up -d --build
```

启动后访问：

- 控制台：`http://127.0.0.1:${WEB_PORT:-8080}`
- API 健康检查：`http://127.0.0.1:${WEB_PORT:-8080}/api/health`

## 本地测试

本地测试环境与线上容器和数据库隔离，适合上线前验收：

```bash
./scripts/local-test-up.sh
./scripts/local-test-frontend.sh
```

打开：

```text
http://127.0.0.1:5173
```

运行冒烟测试：

```bash
./scripts/local-test-smoke.sh
```

停止本地测试环境：

```bash
./scripts/local-test-down.sh
```

重置本地测试数据库：

```bash
./scripts/local-test-down.sh --reset
```

## 关键配置

`.env.example` 中包含运行所需配置项，正式部署前至少需要检查：

- `SECRET_KEY`
- `MYSQL_ROOT_PASSWORD`
- `DB_NAME` / `DB_USER` / `DB_PASSWORD`
- `ADMIN_USERNAME` / `ADMIN_EMAIL` / `ADMIN_PASSWORD`
- `SYMUSE_API_BASE`
- `SYMUSE_CLIENT_ID`
- `SYMUSE_CLIENT_SECRET`
- `SYMUSE_AUTH_PAGE`
- `CORS_ORIGINS`
- `AQC_ORDER_UPLOAD_*`

生产环境建议保持：

```text
ENABLE_LOCAL_LOGIN=false
```

## account-symuse 对接

AQC-N 通过 `account-symuse` 完成统一账号登录。需要在统一账号系统中创建受信客户端，并配置 AQC 控制台回调地址白名单。

后端会调用：

```text
POST {SYMUSE_API_BASE}/auth/tickets/exchange
```

本地测试环境可通过 `.env.local-test.example` 生成 `.env.local-test`，并关闭外部账号同步。

## AQC-O 迁移与兼容

项目保留旧系统迁移所需的关键能力：

- 兼容旧用户身份字段：`vip`、`vip_level`、`user_rule_id`
- 支持旧后台账号、角色、权限关系导入
- 支持 `$2y$` bcrypt 密码校验兼容
- 自动挂载旧接口占位，便于逐步替换真实业务逻辑
- 支持通过 `AQCO_SQL_PATH` 指定旧 SQL 数据源

默认容器内旧数据路径：

```text
/legacy-data/whaqc_data.sql
```

## 常用命令

前端构建：

```bash
cd client
npm run build
```

后端语法检查：

```bash
python3 -m compileall -q backend/fastapi/app backend/fastapi/run.py
```

本地 API 冒烟测试：

```bash
./scripts/local-test-smoke.sh
```

## 发布说明

仓库已排除本地密钥、真实环境变量、SQLite 测试库、构建产物、临时迁移脚本、历史上传素材和本地工作日志。部署时请通过服务器侧 `.env` 或密钥管理系统注入真实配置，不要将生产密钥提交到仓库。
