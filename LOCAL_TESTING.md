# AQC-N 本地测试系统

这套本地测试系统用于上线前验收，独立于线上容器和线上数据库。

## 启动

```bash
./scripts/local-test-up.sh
./scripts/local-test-frontend.sh
```

打开：

```text
http://127.0.0.1:5173
```

默认测试账号：

```text
账号：La
密码：以 `.env.local-test` 中的 `ADMIN_PASSWORD` 为准
```

## 快速自检

后端启动后可以跑一次冒烟测试：

```bash
./scripts/local-test-smoke.sh
```

这个脚本会检查本地 API 健康状态，并用测试账号调用本地登录接口。

## 停止和重置

停止测试系统，保留测试数据库：

```bash
./scripts/local-test-down.sh
```

停止并清空测试数据库：

```bash
./scripts/local-test-down.sh --reset
```

## 环境隔离

- 本地测试 API：`http://127.0.0.1:18080/api`
- 本地测试前端：`http://127.0.0.1:5173`
- 本地测试 MySQL：`127.0.0.1:13307`
- Docker compose 项目名：`aqc-local-test`
- 容器：`aqc-n-local-test-api`、`aqc-n-local-test-db`
- 数据卷：`aqc-local-test_aqc_local_test_mysql_data`

本地测试登录只在前端启动时设置 `VITE_LOCAL_TEST_LOGIN=true` 才显示。生产环境仍使用统一登录，后端生产配置保持 `ENABLE_LOCAL_LOGIN=false`。

## 上线前流程

1. `./scripts/local-test-up.sh`
2. `./scripts/local-test-frontend.sh`
3. 登录本地测试系统，复测本次改动涉及的页面和移动端页面。
4. `./scripts/local-test-smoke.sh`
5. 在 `client` 目录执行 `npm run build`。
6. 确认本地测试和构建都通过后，再部署到服务器。
