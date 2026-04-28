# AQC-N (Backend First)

AQC-N 是基于 AQC-O 重做的后端优先版本：

- 使用 `FastAPI + MySQL + Docker`
- 接入 `account-symuse` 统一账号（票据换取）
- 本地维护 `AQC` 独立用户集（`aqc_*` 表）
- 提供 AQC 独立分组系统
- 身份字段与老项目保持兼容（`vip` / `vip_level` / `user_rule_id`）
- 新版 Web 控制台（响应式，TradingView 风欢迎页）
- AQC-O 历史后台接口占位（278 条）

## 快速开始

```bash
cp .env.example .env
docker compose up -d --build
```

健康检查：

- `GET /api/health`
- Web 入口：`http://127.0.0.1:${WEB_PORT:-8080}`

## 关键接口

账号接入（account-symuse）：

- `POST /api/auth/symuse/state`
- `POST /api/auth/symuse/exchange`
- `POST /api/auth/refresh`
- `POST /api/auth/logout`
- `GET /api/auth/check`
- `GET /api/auth/sessions`
- `DELETE /api/auth/sessions/{session_id}`
- `POST /api/auth/sessions/revoke-others`

用户与身份（AQC 独立用户集）：

- `GET /api/users/me`
- `PUT /api/users/me/identity`
- `GET /api/users/me/groups`

销售模块（录入 + 展示）：

- `POST /api/sales/records`
- `GET /api/sales/records`
- `DELETE /api/sales/records/{record_id}`
- `GET /api/sales/summary?period=day|week|month|ytd`

账户后台（AQC 专属）：

- `GET /api/admin/users`
- `POST /api/admin/users`
- `PUT /api/admin/users/{user_id}`
- `POST /api/admin/users/{user_id}/roles`
- `GET /api/admin/roles`
- `POST /api/admin/roles`
- `PUT /api/admin/roles/{role_id}`
- `GET /api/admin/permissions`
- `POST /api/admin/import/aqc-o`

分组系统（AQC 独立）：

- `GET /api/groups`
- `POST /api/groups`
- `PUT /api/groups/{group_id}`
- `GET /api/groups/{group_id}/members`
- `POST /api/groups/{group_id}/members`
- `DELETE /api/groups/{group_id}/members/{user_id}`

老项目兼容接口（最小）：

- `POST /api/legacy/user/getUserId`
- `POST /api/legacy/user/getIdentityArr`

AQC-O 历史接口占位：

- 已自动挂载 278 条旧路径（如 `/api/goods/getGoodsList`）
- 返回统一占位响应，包含 `controllerAction` 映射，便于后续逐项替换真实逻辑

## AQC-O 账号迁移

导入旧后台账号（`admin_users/admin_roles/admin_permissions`）：

- 默认源文件：容器内 `/legacy-data/whaqc_data.sql`（可通过 `AQCO_SQL_PATH` 调整）
- 接口：`POST /api/admin/import/aqc-o`
- 可传入自定义路径：`{ "sqlPath": "/path/to/whaqc_data.sql" }`

迁移后支持：

- 旧后台账户密码（`$2y$` bcrypt）校验兼容
- 旧角色与权限关系映射到 AQC-N
- AQC 账号仅能由管理员添加/迁移，不支持用户自助注册

## account-symuse 对接说明

你需要在 `account-symuse` 里创建受信客户端（建议 `client_id=aqc`），并把 AQC 前端回调地址加入白名单。

AQC-N 后端会调用：

- `POST {SYMUSE_API_BASE}/auth/tickets/exchange`

环境变量：

- `SYMUSE_API_BASE`
- `SYMUSE_CLIENT_ID`
- `SYMUSE_CLIENT_SECRET`
- `SYMUSE_AUTH_PAGE`
- `SYMUSE_STATE_EXPIRE_SECONDS`
- `SYMUSE_STATE_REQUIRED`
- `SYMUSE_STATE_IP_STRICT`
- `ENABLE_LOCAL_LOGIN`（默认 `false`，AQC-N 线上建议禁用本地登录）

## 身份兼容策略

AQC 用户表保留老项目核心身份字段：

- `vip`（身份）
  - `0=用户`
  - `1=推广员`
  - `2=平台管理员`
  - `3=服务商`
  - `4=VIP用户`
- `vip_level`（推广员等级）
- `user_rule_id`（等级规则）

## 小程序侧（后续接入要点）

当前后端已完成 SSO、用户集与分组底座。下一步你只需提供：

- 小程序回调页方案（如何接收 `code/state`）
- 小程序网络域名白名单（`request` 合法域名）
- 用户资料同步策略（头像/昵称/手机号覆盖规则）
