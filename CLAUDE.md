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
| v1.2 | Data model + Python CLI tools | ✅ Current |
| v1.3 | Internal web app (FastAPI + React) | Planning |

## Architecture

### Three-Layer Structure

1. **Content Layer**: 8 stages × 107 task nodes with standardized process mapping
2. **Database Layer**: SQLite with 7 tables (WAL mode, single writer)
3. **CLI Tools**: Python scripts for query, import, export operations

### Database Schema (SQLite)

Database path: `data/innogreen_pmo.db`

**7 Tables**:
- `stage_map` — 8 stages with standardized naming, ownership, critical path flags
- `task_detail` — 107 tasks with `task_code` (e.g., "2.1.3"), dependencies, owners
- `task_dependency` — Many-to-many task dependency relationships
- `pitfall_guide` — Compliance pitfalls (wrong/right action pairs)
- `stage_pitfall_ref` — Many-to-many stage-pitfall relationships
- `project_profile` — Company records with `project_code` (ENT-xx)
- `project_progress` — Per-company, per-task progress tracking

**Key design decisions**:
- `task_code` preserves Excel hierarchical numbering (e.g., 1.3.1 = stage 1, task 3, subtask 1)
- JSON columns (`team_json`, `materials_json`, `utility_json`) for flexible structured data
- `critical_path` uses emoji: 🔴 (critical), 🟡 (important), 🟢 (normal)
- Status values: `待开始` / `进行中` / `已完成` / `已跳过` / `卡点`

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

### Python Dependencies

```bash
# Install dependencies
npm install   # installs adm-zip (for zip operations)

# Python dependencies (openpyxl for Excel import)
pip install openpyxl
```

## Directory Structure

```
innogreen-pmo/
├── CLAUDE.md                    # This file
├── README.md                    # (if exists)
├── development_plan_v1.0.md     # Project specification
├── development_plan_v1.3_web_app.md  # Web app roadmap
├── 工作阶段划分.xlsx             # Source Excel (5 sheets)
│
├── data/
│   ├── innogreen_pmo.db         # SQLite database (auto-created)
│   ├── innogreen_pmo.db-wal     # WAL mode Write-Ahead Log
│   ├── innogreen_pmo.db-shm     # WAL mode shared memory
│   ├── test.db                  # Test database
│   └── backups/                 # Auto-backups from init_db.py
│
├── sql/
│   ├── schema.sql               # 7 table definitions
│   ├── indexes.sql              # Index definitions
│   ├── triggers.sql             # Auto-update triggers
│   ├── seed.sql                 # 8 stages + 107 tasks + dependencies
│   └── sample_data.sql          # 3 sample projects + pitfalls
│
└── scripts/
    ├── init_db.py               # Database initialization (idempotent)
    ├── import_excel.py          # Excel → DB import
    └── verify_phase_a.py        # Data verification checks
```

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
