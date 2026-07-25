# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Innogreen PMO (项目管理办公室) is a digital foundation for the **Shanghai International Chemical New Materials Innovation Center (INNOGREEN)**. It serves 17+ tenant companies by providing standardized process guidance, project tracking, and compliance knowledge for chemical material R&D and pilot-scale manufacturing.

**Center Mission**: Innovation-driven development targeting advanced materials, integrated circuits, biomanufacturing, circular economy, and clean energy sectors.

**Key Concept**: Transform from "landlord + property management" to "partner-style accompaniment" through structured project governance.

**Notable Tenants**: LANXESS, Röhm, Invista, Henkel, Air Liquide, plus 12+ domestic companies and research institutes.

## Project Roadmap

| Version | Focus | Status |
|---------|-------|--------|
| v1.2 | Data model + Python CLI tools | Done |
| v1.3 | Internal web app (FastAPI + React) | Phase C3 Done — read + write + audit + multi-user session auth |
| v1.4 | Tenant-facing portal (`/tenant/*`) | Planned (placeholder route only) |

> Phase timeline within v1.3: **A** data foundation → **B** read-only API/UI → **C** write operations (projects / progress / pitfalls) + audit log → **C3** pitfall authoring + **auth** multi-user login. Backend reports `version="1.3.0-phase-c3"`.

## Architecture

### Three-Layer Structure

1. **Content Layer**: 8 stages × 108 task nodes with standardized process mapping
2. **Database Layer**: SQLite with 8 tables (WAL mode, single writer) + `audit_log`
3. **Web App (Phase C)**: FastAPI backend (`/api/ops`) + React/Ant Design frontend; Python CLI scripts for batch import/export

### Database Schema (SQLite)

Database path: `data/innogreen_pmo.db`

**8 Tables** (7 core + 1 audit, defined in [sql/schema.sql](sql/schema.sql) + [sql/audit_log.sql](sql/audit_log.sql)):
- `stage_map` — 8 stages with standardized naming, ownership, critical path flags
- `task_detail` — 108+ tasks with `task_code` (e.g., "2.1.3"), dependencies, owners; `is_active` for soft-delete
- `task_dependency` — Many-to-many task dependency relationships
- `pitfall_guide` — Compliance pitfalls (wrong/right action pairs)
- `stage_pitfall_ref` — Many-to-many stage-pitfall relationships
- `project_profile` — Company records with `project_code` (ENT-xx)
- `project_progress` — Per-company, per-task progress tracking
- `audit_log` — (Phase C) append-only write-operation log: actor / action / resource / payload(JSON) / ip_address / user_agent / created_at
- `users` — (Phase C auth) username / password_hash(bcrypt) / display_name / role(admin|operator|viewer) / is_active(soft-delete) / timestamps

**Key design decisions**:
- `task_code` preserves Excel hierarchical numbering (e.g., 1.3.1 = stage 1, task 3, subtask 1)
- JSON columns (`team_json`, `materials_json`, `utility_json`) for flexible structured data
- `critical_path` uses emoji: 🔴 (critical), 🟡 (important), 🟢 (normal)
- Status values: `待开始` / `进行中` / `已完成` / `已跳过` / `卡点`
- `progress_percent` and `project_status` are **not edited directly** — the backend recomputes them on each progress write (`services/progress_service.py`); `project_status` auto-flips to `卡点` when any task is blocked.
- ORM (`web/backend/models.py`) intentionally omits the DB-level `created_at`/`updated_at` columns — `updated_at` is maintained by [sql/triggers.sql](sql/triggers.sql), not by SQLAlchemy.

## Development Commands

### Database Operations

```bash
# Initialize database (idempotent - backs up existing DB first)
python scripts/init_db.py

# Initialize with Excel import
python scripts/init_db.py --excel 工作阶段划分.xlsx

# Import data from Excel separately
python scripts/import_excel.py --db data/innogreen_pmo.db --excel 工作阶段划分.xlsx
```

### Database Verification

```bash
# Run verification checks
python scripts/verify_phase_a.py
```

### Web (Phase C — read + write + multi-user auth)

```bash
# Backend
cd web
copy .env.example .env        # Windows (Linux/macOS: cp)
# Edit .env: set PMO_SESSION_SECRET (required) and PMO_BOOTSTRAP_ADMIN_USERNAME/PASSWORD (optional)
cd backend
pip install -r ../requirements.txt
uvicorn main:app --reload --host 127.0.0.1 --port 8000

# Frontend
cd web/frontend
npm install
npm run lint                  # type check + lint (CI also runs this)
npm run dev
```

- UI: http://127.0.0.1:5173 — login with a username/password (admin created by `PMO_BOOTSTRAP_ADMIN_*` on first start, or via the in-app user management page).
- Vite dev server proxies `/api` and `/health` → `http://127.0.0.1:8000`
- API docs: http://127.0.0.1:8000/docs (disable in prod via `PMO_ENABLE_DOCS=false`).
- Session cookie is SameSite=Lax (same-origin only). See the "生产部署" section in [web/README.md](web/README.md).

### Tests & backup (CI runs these)

```bash
# API tests (isolated DB at data/test_api.db, never touches dev DB)
pip install -r web/requirements.txt
pytest tests/ -v
pytest tests/test_api/test_auth.py::test_login -v       # run single test
pytest tests/ -k test_login -v                          # run tests matching pattern

# Backup the dev DB to data/backups/ (Online Backup API, transaction-consistent snapshot)
python scripts/backup_db.py
python scripts/backup_db.py --db-path data/innogreen_pmo.db
```

CI (`.github/workflows/ci.yml`) runs `pytest tests/` on Python 3.12 and `npm run lint && npm run build` (oxlint + `tsc`/vite) on Node 20. There are no frontend unit tests.

## Directory Structure

```
innogreen-pmo/
├── CLAUDE.md                    # This file
├── development_plan_v1.0.md     # Project specification
├── development_plan_v1.3_web_app.md  # Web app roadmap
├── pytest.ini                   # pytest: testpaths=tests, pythonpath=web/backend
├── 工作阶段划分.xlsx             # Source Excel (5 sheets)
│
├── data/
│   ├── innogreen_pmo.db         # SQLite database (auto-created)
│   ├── innogreen_pmo.db-wal     # WAL mode Write-Ahead Log
│   ├── innogreen_pmo.db-shm     # WAL mode shared memory
│   ├── test_api.db              # API test database (rebuilt each pytest run)
│   └── backups/                 # Auto-backups from init_db.py / backup_db.py
│
├── sql/
│   ├── schema.sql               # 7 core table definitions
│   ├── audit_log.sql            # audit_log table (Phase C)
│   ├── users.sql               # users table (Phase C auth)
│   ├── indexes.sql              # Index definitions
│   ├── triggers.sql             # Auto-update updated_at triggers
│   ├── seed.sql                 # 8 stages + 108 tasks + dependencies
│   └── sample_data.sql          # 3 sample projects + pitfalls
│
├── scripts/
│   ├── init_db.py               # Database initialization (idempotent)
│   ├── import_excel.py          # Excel → DB import
│   ├── backup_db.py             # Backup DB to data/backups/
│   └── verify_phase_a.py        # Data verification checks
│
├── tests/                       # pytest API tests (TestClient)
│   ├── conftest.py              # session-scoped app, isolated test_api.db
│   └── test_api/                # auth / health / projects / progress / pitfalls
│
├── .github/workflows/ci.yml     # CI: pytest (py3.12) + npm build (node20)
│
└── deploy/                      # Production: systemd units, nginx, backup timer
│
└── web/                         # Phase C web app
    ├── README.md                # Phase C runbook (routes, env, tests, backup)
    ├── .env.example             # PMO_SESSION_SECRET / bootstrap admin / CORS
    ├── requirements.txt
    ├── backend/                 # FastAPI
    │   ├── main.py              # app entry + SessionMiddleware + lifespan bootstrap
    │   ├── config.py            # pydantic-settings: session secret, bootstrap admin, CORS guard
    │   ├── database.py          # engine + WAL/foreign_keys/busy_timeout pragmas
    │   ├── deps.py              # get_current_user / require_role / CurrentUser/WriteUser/AdminUser
    │   ├── security.py          # bcrypt hash_password / verify_password
    │   ├── models.py            # SQLAlchemy ORM (users + audit_log)
    │   ├── schemas.py           # pydantic read/write/auth schemas
    │   ├── routers/ops.py      # /api/ops (read+write) + /api/tenant stub
    │   ├── routers/auth.py      # /api/auth: login/logout/register/me + user CRUD/delete
    │   └── services/            # audit, critical_path, dashboard, journal,
                                # progress_service, project_service, pitfall_service,
                                # task_service, import_service, export_service, db_transfer
    └── frontend/                # React 19 + Ant Design 6 + react-router 7
        └── src/
            ├── App.tsx          # routes + AuthProvider
            ├── api/client.ts    # axios + withCredentials + TS types
            ├── auth/
            │   ├── AuthContext.tsx  # user/loading/login/logout
            │   └── RequireAuth.tsx
            ├── layout/AppLayout.tsx  # role tag, admin menu, logout
            └── pages/           # Login, Register, Dashboard, Project/List/Form/Detail/TaskUpdate,
                                # Stage/List/Detail, Pitfall/List/Form/Detail, UserManagement, TaskCatalog,
                                # DataImport, DataExport, TenantPlaceholder
```

**Backend services** (`web/backend/services/`): audit, critical_path, dashboard, journal, progress_service, project_service, pitfall_service, task_service, import_service, export_service, db_transfer, **qcc_service**

## Web App Architecture (Phase C)

**UI 风格**：与 qcc 系统保持一致的蓝色主题（#2563eb）、深蓝渐变侧边栏、卡片式布局。

**Auth model**: username/password + bcrypt + Starlette `SessionMiddleware` (itsdangerous signed cookie, SameSite=Lax). Three roles: `admin` (full + user mgmt), `operator` (read + Phase C write), `viewer` (registered users, read-only). `/api/auth/register` allows self-registration (default `viewer` role). `audit_log.actor = username`; `ip_address`/`user_agent` filled on writes. `/api/tenant/*` is a v1.4 placeholder (501).

> ⚠️ **Security critical**: Backend **must** bind to `127.0.0.1` only — `PMO_SESSION_SECRET` is the signing key; if leaked, attackers can forge admin sessions. Set `PMO_HTTPS_ONLY=true` behind HTTPS proxy and `PMO_CORS_ORIGINS` to actual frontend origin (not `*`). See [web/README.md](web/README.md) §4 for full deployment hardening.

**Read endpoints** (`GET`): stages, tasks, dependencies, projects (+ filters), progress, critical-path, blockers, dashboard summary, pitfalls.

**Write endpoints** (Phase C, all audited via `services/audit.py`):
- `POST /api/ops/projects`, `PATCH /api/ops/projects/{id}` — create/edit company profile
- `PUT /api/ops/projects/{id}/tasks/{task_id}` — upsert task progress (recomputes `progress_percent` + syncs `project_status`)
- `GET/POST /api/ops/projects/{id}/journal` · `.../tasks/{task_id}/journal` — L3 weekly journal timeline
- `POST /api/ops/pitfalls` — author a pitfall + link to a stage
- `POST/PATCH /api/ops/tasks`, `POST .../activate|deactivate` — **admin** task catalog (soft-delete via `is_active`; insert auto-renumbers sibling `task_code`)

There are **no hard DELETE endpoints** by design (traceability; tasks use deactivate). `/api/tenant/*` returns 501 until v1.4.

## qcc 企业资质库集成（方案一）

PMO 后端通过 SQLite `ATTACH DATABASE` 附加 qcc 数据库（`qualifications.db`），只读联查工商信息和资质证照。

**配置**：
```bash
# web/.env
PMO_QCC_DB_PATH=/opt/qcc/data/qualifications.db
```

**API 端点**：
- `GET /api/ops/qcc/status` — 查询 qcc 连接状态
- `GET /api/ops/qcc/companies/lookup?credit_code=xxx` — 按信用代码/名称查企业详情
- `GET /api/ops/qcc/companies/expiring?days=30` — 列出即将到期的资质

**前端**：企业详情页显示「企业详情」按钮，点击弹出抽屉展示工商信息 + 资质证照表；进度表的「第三方单位」列也可点击查看。

## Portal（统一身份认证）

`portal/` 是独立的 IAM Portal（IdP），为 PMO、qcc、sh_eia 及未来应用提供统一身份与按应用授权的 SSO。

**模型**：
- `users`：身份唯一真源（Portal 角色仅 `admin`/`viewer`）
- `app_memberships`：用户 × 应用 → 角色（PMO/qcc/sh_eia 统一为 admin/operator/viewer；历史 user ≡ operator）
- 无有效 membership = 无权进入该应用

**启动**：
```bash
cd portal
copy .env.example .env   # Windows
# 编辑 .env：SESSION_SECRET 必须与 PMO 的 PMO_SESSION_SECRET 相同
pip install -r requirements.txt
uvicorn main:app --reload --host 127.0.0.1 --port 8001
```

**核心端点**：
- `POST /api/auth/login` — 登录（写 session cookie）
- `GET /api/auth/verify-session?app=PMO|qcc|sh_eia` — 跨应用验会话，返回本应用角色
- `GET /api/apps/mine` — 当前用户有权访问的应用
- `PUT /api/auth/users/{id}/memberships` — 授予/更新应用角色（admin）

**用户合并**：
```bash
python scripts/merge_users_to_portal.py --dry-run
python scripts/merge_users_to_portal.py \
  --sh-eia-db D:/github/Scrapling/examples/sh_eia/data/auth.db
```

**PMO 接入（SSO）**：在 `web/.env` 设置：
```
PMO_PORTAL_BASE_URL=http://127.0.0.1:8001
PMO_PORTAL_WEB_URL=http://127.0.0.1:8001
PMO_SESSION_SECRET=<与 Portal SESSION_SECRET 相同>
```
登录会代理到 Portal；`get_current_user` 调 `verify-session?app=PMO`。留空 `PMO_PORTAL_BASE_URL` 则回退本地 users（pytest 默认）。

**qcc 接入（SSO）**：在 `D:\Claude\qcc\.env` 设置：
```
QCC_PORTAL_BASE_URL=http://127.0.0.1:8001
QCC_PORTAL_WEB_URL=http://127.0.0.1:8001
QCC_SESSION_SECRET=<与 Portal SESSION_SECRET 相同>
```
鉴权调 `verify-session?app=qcc`；留空则回退本地 JWT + `is_approved`。

**sh_eia 接入（SSO）**：在 `D:\github\Scrapling\examples\sh_eia\.env` 设置：
```
SH_EIA_PORTAL_BASE_URL=http://127.0.0.1:8001
SH_EIA_PORTAL_WEB_URL=http://127.0.0.1:8001
SH_EIA_SESSION_SECRET=<与 Portal SESSION_SECRET 相同>
SH_EIA_PUBLIC_BASE=/eia
```
鉴权调 `verify-session?app=sh_eia`；留空则回退本地 JWT + 审批制。

详见 [portal/README.md](portal/README.md)。同域路径（含 `/eia/`）+ HTTPS cookie 见 [deploy/SSO.md](deploy/SSO.md)。

**统一壳层 / 响应式**：四端共用 `shell-top-actions.css` + `shell-sidebar.css`。`≤960` 侧栏汉堡抽屉，`≤720` 顶栏仅图标；Portal 应用卡同页跳转。改样式请四端同步。

## Language Convention

- **Project language**: Mixed — planning docs in Chinese, code in English
- **Variable names**: English (e.g., `stage_id`, `pitfall_guide`)
- **Comments**: Chinese for business logic explanations preferred
- **CLI output**: Chinese (user-facing messages)
- **Database values**: Chinese for status/owner fields (e.g., `客户主导`, `已完成`)

## Reference Documents

- [development_plan_v1.0.md](development_plan_v1.0.md) — Complete project specification
- 工作阶段划分.xlsx — Source 8-stage process map with 108 task nodes
- [development_plan_v1.3_web_app.md](development_plan_v1.3_web_app.md) — Web app roadmap
