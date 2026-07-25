# Innogreen IAM Portal

统一身份认证门户（IdP），为 **PMO / qcc / sh_eia** 提供集中账号、按应用授权与 SSO 会话。

## 设计要点

- **身份唯一真源**：`portal.db` 的 `users` 表
- **按应用授权**：`app_memberships(user_id, app_code, role)`；无有效 membership = 无权进入该应用
- **共享 Session Cookie**：与各应用共用 `SESSION_SECRET`（默认 cookie 名 `innogreen_session`）；各应用调 `GET /api/auth/verify-session?app=PMO|qcc|sh_eia` 解析本应用角色
- **统一壳层**：顶栏（品牌 + 返回门户 / 账号管理 / 退出）与侧栏跨端样式一致；应用卡片同页跳转（不新开标签）

### 角色约定

| 范围 | 角色 |
|------|------|
| Portal 自身 | `admin` / `viewer`（仅管门户后台与授权） |
| PMO / qcc / sh_eia | `admin` / `operator` / `viewer` |

- 历史 qcc / sh_eia 的 `user` ≡ **`operator`**（写权限）
- **`viewer`**：可登录进入应用，业务写操作返回 403（与 PMO 只读语义对齐）

### 响应式壳层（四端共用）

| 断点 | 行为 |
|------|------|
| `>960px` | 桌面：固定侧栏 + 顶栏图标+文字 |
| `≤960px` | 平板/手机：侧栏改为汉堡抽屉 |
| `≤720px` | 手机：顶栏只显示图标（文案仍可读屏） |

样式源文件（改完请四端同步）：

- `portal/static/shell-top-actions.css`
- `portal/static/shell-sidebar.css`
- （副本）`web/frontend/src/layout/`、`qcc/static/`、`sh_eia/app/static/`

## 技术栈

- FastAPI + Session Cookie（Starlette `SessionMiddleware`）
- SQLite（`data/portal.db`，本地文件，不入库）

## 启动

```bash
cd portal
copy .env.example .env   # Windows
# 编辑 .env：SESSION_SECRET 必须与各应用 *_SESSION_SECRET 相同
pip install -r requirements.txt
uvicorn main:app --reload --host 127.0.0.1 --port 8001
```

- 门户首页：http://127.0.0.1:8001/
- 登录 / 注册：`/login` `/register`
- 账号与授权（Portal admin）：`/admin`
- API 文档：http://127.0.0.1:8001/docs

本机同域试用（Portal + PMO + qcc 一条入口）：见 [deploy/SSO.md](../deploy/SSO.md) 与 `python scripts/local_sso_proxy.py`（默认 `http://127.0.0.1:8788/`）。

## 环境变量

```
SESSION_SECRET=...                         # 必填，与 PMO/qcc/sh_eia 共用
SESSION_COOKIE_NAME=innogreen_session
HTTPS_ONLY=false                           # 生产 HTTPS 反代后 true
PORTAL_DB_PATH=./data/portal.db
PORTAL_BOOTSTRAP_ADMIN_USERNAME=admin
PORTAL_BOOTSTRAP_ADMIN_PASSWORD=...
TRUSTED_APPS=PMO,qcc,sh_eia
CORS_ORIGINS=http://127.0.0.1:8788,http://127.0.0.1:5173,http://127.0.0.1:8765,http://127.0.0.1:8080,http://127.0.0.1:8001
PORTAL_BASE_URL=http://127.0.0.1:8001
# 同域路径部署时覆盖种子应用入口（可选）
PMO_PUBLIC_URL=http://127.0.0.1:8788/pmo/
QCC_PUBLIC_URL=http://127.0.0.1:8788/qcc/
SH_EIA_PUBLIC_URL=http://127.0.0.1:8080/
```

## 用户合并（PMO + qcc + sh_eia → Portal）

```bash
# 预览
python scripts/merge_users_to_portal.py --dry-run

# 执行（可按需指定源库）
python scripts/merge_users_to_portal.py ^
  --pmo-db data/innogreen_pmo.db ^
  --qcc-db D:\Claude\qcc\data\qualifications.db ^
  --sh-eia-db D:\github\Scrapling\examples\sh_eia\data\auth.db
```

规则摘要：

- 同名以 username 去重；已存在于 Portal 的只补 membership
- qcc 未审批、sh_eia 非 `active` 不授予对应应用授权
- 源角色 `user` 写入 membership 时归一为 `operator`

生产合并清单见 [deploy/SSO.md](../deploy/SSO.md)。

## API

### 认证

- `POST /api/auth/login` — 登录（写 session cookie）
- `POST /api/auth/logout` — 登出
- `POST /api/auth/register` — 注册（默认无任何应用授权，需管理员授予）
- `GET /api/auth/me` — 当前用户 + memberships
- `GET /api/auth/verify-session?app=PMO|qcc|sh_eia` — 跨应用验会话；返回 `{valid, user, app_code, role}`

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

## 与各应用的集成

### PMO（已完成）

1. `web/.env`：`PMO_PORTAL_BASE_URL`（及可选 `PMO_PORTAL_WEB_URL`）
2. `PMO_SESSION_SECRET` == Portal `SESSION_SECRET`
3. 登录代理到 Portal；鉴权 `verify-session?app=PMO`
4. 留空 `PMO_PORTAL_BASE_URL` 时回退本地 users（pytest / 单机兜底）

### qcc（已完成）

1. qcc `.env`：`QCC_PORTAL_BASE_URL` / `QCC_PORTAL_WEB_URL` / `QCC_SESSION_SECRET`
2. 鉴权 `verify-session?app=qcc`；角色 `admin|operator|viewer`
3. 留空则回退本地 JWT + `is_approved`
4. SSO 下本地用户审批/改密禁用，改在 Portal 授权

### sh_eia（已完成）

1. sh_eia `.env`：`SH_EIA_PORTAL_BASE_URL` / `SH_EIA_PORTAL_WEB_URL` / `SH_EIA_SESSION_SECRET`
2. 同域前缀可选：`SH_EIA_PUBLIC_BASE=/eia`
3. 鉴权 `verify-session?app=sh_eia`
4. 留空则回退本地 JWT + 审批制

## 同域路径部署

见 [deploy/SSO.md](../deploy/SSO.md) 与 [deploy/nginx.innogreen-sso.conf](../deploy/nginx.innogreen-sso.conf)。

- Cookie 名默认 `innogreen_session`；生产设 `HTTPS_ONLY=true`
- `/` → Portal，`/pmo/` → PMO，`/qcc/` → qcc，`/eia/` → sh_eia
