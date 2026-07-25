# Innogreen IAM Portal

统一身份认证门户，为 PMO、qcc 及未来应用提供集中的用户管理和 SSO 会话。

## 设计要点

- **身份唯一真源**：`portal.db` 的 `users` 表
- **按应用授权**：`app_memberships(user_id, app_code, role)`；无有效 membership = 无权进入该应用
- **共享 Session Cookie**：与 PMO 共用 `SESSION_SECRET`，各应用调 `GET /api/auth/verify-session?app=PMO|qcc` 解析本应用角色

角色约定：

| 范围 | 角色 |
|------|------|
| Portal 自身 | `admin` / `viewer`（管用户与授权） |
| PMO / qcc / sh_eia | `admin` / `operator` / `viewer`（历史 qcc/sh_eia 的 `user` ≡ `operator`） |

## 技术栈

- FastAPI + Session Cookie（Starlette `SessionMiddleware`）
- SQLite（`data/portal.db`）

## 启动

```bash
cd portal
copy .env.example .env   # Windows
# 编辑 .env：设置 SESSION_SECRET（与 PMO 的 PMO_SESSION_SECRET 相同）
pip install -r requirements.txt
uvicorn main:app --reload --host 127.0.0.1 --port 8001
```

- 门户首页：http://127.0.0.1:8001/
- 登录：http://127.0.0.1:8001/login
- API 文档：http://127.0.0.1:8001/docs

## 环境变量

```
SESSION_SECRET=...                         # 必填，与 PMO 共用
PORTAL_DB_PATH=./data/portal.db
PORTAL_BOOTSTRAP_ADMIN_USERNAME=admin
PORTAL_BOOTSTRAP_ADMIN_PASSWORD=...
TRUSTED_APPS=PMO,qcc
CORS_ORIGINS=http://localhost:5173,http://localhost:8765,http://localhost:8001
PORTAL_BASE_URL=http://localhost:8001
```

## 用户合并（PMO + qcc → Portal）

```bash
# 预览
python scripts/merge_users_to_portal.py --dry-run

# 执行
python scripts/merge_users_to_portal.py

# 指定源库
python scripts/merge_users_to_portal.py ^
  --pmo-db data/innogreen_pmo.db ^
  --qcc-db D:\Claude\qcc\data\qualifications.db
```

同名用户以 username 去重；已存在于 Portal 的只补 membership。qcc 未审批用户不授予 qcc 授权。

## API

### 认证

- `POST /api/auth/login` — 登录（写 session cookie）
- `POST /api/auth/logout` — 登出
- `POST /api/auth/register` — 注册（默认无任何应用授权，需管理员授予）
- `GET /api/auth/me` — 当前用户 + memberships
- `GET /api/auth/verify-session?app=PMO` — 跨应用验会话；返回 `{valid, user, app_code, role}`

### 用户与授权（Portal admin）

- `GET/POST /api/auth/users`
- `PATCH/DELETE /api/auth/users/{id}`
- `GET /api/auth/users/{id}/memberships`
- `PUT /api/auth/users/{id}/memberships` — body: `{app_code, role, is_active}`
- `DELETE /api/auth/users/{id}/memberships/{app_code}`

### 应用

- `GET /api/apps` — 全部已注册应用（公开目录）
- `GET /api/apps/mine` — 当前用户有权访问的应用
- `POST /api/apps` / `DELETE /api/apps/{id}` — 管理员

## 与 PMO 的集成（已完成）

1. PMO `web/.env` 设置 `PMO_PORTAL_BASE_URL`（及可选 `PMO_PORTAL_WEB_URL`）
2. `PMO_SESSION_SECRET` 与 Portal `SESSION_SECRET` 相同（跨应用 cookie 互信）
3. PMO 登录代理到 Portal；鉴权调 `GET /api/auth/verify-session?app=PMO`
4. 留空 `PMO_PORTAL_BASE_URL` 时 PMO 回退本地 users（pytest / 单机兜底）

## 与 qcc 的集成（已完成）

1. qcc `.env` 设置 `QCC_PORTAL_BASE_URL`（及可选 `QCC_PORTAL_WEB_URL`）
2. `QCC_SESSION_SECRET` 与 Portal `SESSION_SECRET` 相同
3. qcc 登录代理到 Portal；鉴权调 `GET /api/auth/verify-session?app=qcc`
4. 留空 `QCC_PORTAL_BASE_URL` 时回退本地 JWT + `is_approved`
5. SSO 下本地用户审批/改密禁用，改在 Portal `app_memberships` 授权

## 与 sh_eia 的集成（已完成）

1. sh_eia `.env` 设置 `SH_EIA_PORTAL_BASE_URL`（及可选 `SH_EIA_PORTAL_WEB_URL`）
2. `SH_EIA_SESSION_SECRET` 与 Portal `SESSION_SECRET` 相同
3. sh_eia 登录代理到 Portal；鉴权调 `GET /api/auth/verify-session?app=sh_eia`
4. 同域路径：`SH_EIA_PUBLIC_BASE=/eia`
5. 留空 `SH_EIA_PORTAL_BASE_URL` 时回退本地 JWT + 审批制
6. SSO 下本地用户审批/改密禁用，改在 Portal `app_memberships` 授权

## 同域路径部署（P3）

见 [deploy/SSO.md](../deploy/SSO.md) 与 [deploy/nginx.innogreen-sso.conf](../deploy/nginx.innogreen-sso.conf)。

- Cookie 名默认 `innogreen_session`；生产设 `HTTPS_ONLY=true`
- `/` → Portal，`/pmo/` → PMO，`/qcc/` → qcc，`/eia/` → sh_eia
