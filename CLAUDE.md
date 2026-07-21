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
| v1.3 | Internal web app (FastAPI + React) | Phase C3 Done — read + write + audit + multi-user auth |
| v1.4 | Tenant-facing portal (`/tenant/*`) | Planned (placeholder route only) |

> Phase timeline within v1.3: **A** data foundation → **B** read-only API/UI → **C** write operations (projects / progress / pitfalls) + audit log → **C3** pitfall authoring + **auth** multi-user login. Backend reports `version="1.3.0-phase-c3"`.

## Architecture

### Three-Layer Structure

1. **Content Layer**: 8 stages × 107 task nodes with standardized process mapping
2. **Database Layer**: SQLite with 8 tables (WAL mode, single writer) + `audit_log`
3. **Web App (Phase C)**: FastAPI backend (`/api/ops`) + React/Ant Design frontend; Python CLI scripts for batch import/export

### Database Schema (SQLite)

Database path: `data/innogreen_pmo.db`

**8 Tables** (7 core + 1 audit, defined in [sql/schema.sql](sql/schema.sql) + [sql/audit_log.sql](sql/audit_log.sql)):
- `stage_map` — 8 stages with standardized naming, ownership, critical path flags
- `task_detail` — 107 tasks with `task_code` (e.g., "2.1.3"), dependencies, owners
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
npm run dev
```

- UI: http://127.0.0.1:5173 — login with a username/password (admin created by `PMO_BOOTSTRAP_ADMIN_*` on first start, or via the in-app user management page).
- API docs: http://127.0.0.1:8000/docs (disable in prod via `PMO_ENABLE_DOCS=false`).
- Vite dev server proxies `/api` and `/health` → `http://127.0.0.1:8000`. Session cookie is SameSite=Lax (same-origin only). See the "生产部署" section in [web/README.md](web/README.md).

### Tests & backup (CI runs these)

```bash
# API tests (isolated DB at data/test_api.db, never touches dev DB)
pip install -r web/requirements.txt
pytest tests/ -v

# Backup the dev DB to data/backups/ (Online Backup API, transaction-consistent snapshot)
python scripts/backup_db.py
python scripts/backup_db.py --db-path data/innogreen_pmo.db
```

CI (`.github/workflows/ci.yml`) runs `pytest tests/` on Python 3.12 and `npm run lint && npm run build` (oxlint + `tsc`/vite) on Node 20. There are no frontend unit tests.

### Python Dependencies

```bash
pip install openpyxl
pip install -r web/requirements.txt
```

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
│   ├── seed.sql                 # 8 stages + 107 tasks + dependencies
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
    │   ├── routers/auth.py      # /api/auth: login/logout/me + user management
    │   └── services/            # audit, critical_path, project_service, progress_service, pitfall_service
    └── frontend/                # React 19 + Ant Design 6 + react-router 7
        └── src/
            ├── App.tsx          # routes + AuthProvider
            ├── api/client.ts    # axios + withCredentials + TS types
            ├── auth/
            │   ├── AuthContext.tsx  # user/loading/login/logout
            │   └── RequireAuth.tsx
            ├── layout/AppLayout.tsx  # role tag, admin menu, logout
            └── pages/           # Dashboard, Project/List/Form/Detail/TaskUpdate,
                                # Stage/List/Detail, Pitfall/List/Form/Detail, UserManagement, Login
```

## Web App Architecture (Phase C)

**Auth model**: username/password + bcrypt + Starlette `SessionMiddleware` (itsdangerous signed cookie, SameSite=Lax). Three roles: `admin` (full + user mgmt), `operator` (read + Phase C write), `viewer` (read-only). `audit_log.actor = username`; `ip_address`/`user_agent` filled on writes. `/api/tenant/*` is a v1.4 placeholder (501).

**Read endpoints** (`GET`): stages, tasks, dependencies, projects (+ filters), progress, critical-path, blockers, dashboard summary, pitfalls.

**Write endpoints** (Phase C, all audited via `services/audit.py`):
- `POST /api/ops/projects`, `PATCH /api/ops/projects/{id}` — create/edit company profile
- `PUT /api/ops/projects/{id}/tasks/{task_id}` — upsert task progress (recomputes `progress_percent` + syncs `project_status`)
- `POST /api/ops/pitfalls` — author a pitfall + link to a stage

There are **no DELETE endpoints** by design (traceability). `/api/tenant/*` returns 501 until v1.4.

## Language Convention

- **Project language**: Mixed — planning docs in Chinese, code in English
- **Variable names**: English (e.g., `stage_id`, `pitfall_guide`)
- **Comments**: Chinese for business logic explanations preferred
- **CLI output**: Chinese (user-facing messages)
- **Database values**: Chinese for status/owner fields (e.g., `客户主导`, `已完成`)

## Reference Documents

- [development_plan_v1.0.md](development_plan_v1.0.md) — Complete project specification
- 工作阶段划分.xlsx — Source 8-stage process map with 107 task nodes
- [development_plan_v1.3_web_app.md](development_plan_v1.3_web_app.md) — Web app roadmap
