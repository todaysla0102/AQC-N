# AQC-N FastAPI Backend

## 本地运行

```bash
cd backend/fastapi
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp ../../.env.example ../../.env
python run.py
```

默认监听 `0.0.0.0:8000`。

## 核心能力

- `account-symuse` 票据换取登录
- `state` 回调校验（防重放，一次性消费）
- AQC 独立用户集（`aqc_users`）
- AQC 独立身份表（`aqc_user_identity`）
- AQC 独立分组（`aqc_groups` + `aqc_group_members`）
- 登录态会话管理（会话列表、刷新、下线）
- 老接口最小兼容（`/api/legacy/user/*`）
- AQC-O 历史接口占位（278 条，便于逐项迁移）

## 认证相关接口

- `POST /api/auth/local-login`
- `POST /api/auth/symuse/state`
- `POST /api/auth/symuse/exchange`
- `POST /api/auth/refresh`
- `POST /api/auth/logout`
- `GET /api/auth/check`
- `GET /api/auth/sessions`
- `DELETE /api/auth/sessions/{session_id}`
- `POST /api/auth/sessions/revoke-others`
