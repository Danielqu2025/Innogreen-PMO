# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Innogreen PMO (项目管理办公室) is a digital foundation for the **Shanghai International Chemical New Materials Innovation Center (INNOGREEN)**. It serves 17+ tenant companies by providing standardized process guidance, project tracking, and compliance knowledge for chemical material R&D and pilot-scale manufacturing.

**Center Mission**: Innovation-driven development targeting advanced materials, integrated circuits, biomanufacturing, circular economy, and clean energy sectors.

**Key Concept**: Transform from "landlord + property management" to "partner-style accompaniment" through structured project governance.

**Center Layout**:
- Phase 1: ~58,000 m² (infrastructure and services)
- Phase 2: ~42,000 m² (high-standard pilot R&D facilities)
- F6d-1 plot: ~29,000 m² (Class A production/warehouse)
- F6a-3 plot: ~36,000 m² (Class A production/warehouse)

**Notable Tenants**: LANXESS, Röhm, Invista, Henkel, Air Liquide, plus 12+ domestic companies and research institutes.

## Project Status

This is a **v1.0 planning-stage project**. Implementation follows the phased plan in [development_plan_v1.0.md](development_plan_v1.0.md).

## Architecture

### Three-Layer Structure

1. **Content Layer** (内容层): 18 stages × 92 task nodes with standardized process mapping
2. **Database Layer** (DB 层): SQLite with 7 tables (stages, tasks, pitfalls, projects, progress, dependencies, refs)
3. **CLI Tools** (CLI 工具集): 10 shell scripts for query/entry/update/export operations

### Database Schema (SQLite)

Located at `data/innogreen_pmo.db`:

**7 Tables** (restructured from 4):
- `stage_map` — 18 stages with standardized naming, ownership, critical path flags
- `task_detail` — 92+ substeps with dependencies, owners, pitfall references
- `pitfall_guide` — Compliance pitfalls (12-field structure)
- `project_profile` — Company records (17+ tenant firms + future)
- `project_progress` — **NEW**: Track each company's progress on each task
- `task_dependency` — **NEW**: Many-to-many task dependency relationships
- `stage_pitfall_ref` — **NEW**: Many-to-many stage-pitfall relationships

**Key improvements from v1.1**:
- Fixed comma-separated relationship fields → proper junction tables
- Added progress tracking capability
- Proper indexes on foreign keys and frequently queried fields
- Data type corrections (DECIMAL for money, DATE for dates)
- Triggers for automatic updated_at timestamps

### Excel Integration

- `excel/工作阶段划分_v2.xlsx` — 5-sheet master file:
  - Sheet1: Main stage map (18 records)
  - Sheet2: Task-substep detail (92+ records)
  - Sheet3: Pitfall guide (20+ structured cards)
  - Sheet4: Project profile template
  - Sheet5: Task dependency relationships

## Development Workflow

### Build and Setup

```bash
# Initialize database (create tables + seed data)
./scripts/init_db.sh

# Import from Excel to CSV to DB
./scripts/migrate_excel_to_db.sh
```

### CLI Tools

Located in `scripts/`:

**10 commands** (v1.2 expanded from 8):

```bash
# Query commands (5)
./query_stages.sh [--critical 🔴|🟡|🟢]           # Stage overview
./query_projects.sh [--status] [--stage]            # Company progress
./query_pitfalls.sh --stage <name> [--impact]       # Pitfall cards
./query_critical_path.sh --project-id <id>          # Critical path (Mermaid)
./query_dependencies.sh --task-id <id>              # Task dependency tree

# Entry commands (2)
./add_project.sh [--company] [--type] [--building]  # Interactive or param-based
./add_pitfall.sh --stage --wrong --right [...]       # Add pitfall card

# Update commands (1)
./update_progress.sh --project-id --task-id --status [--blocker-note]

# Export commands (2)
./export_dashboard.sh --output <file> [--format]    # Excel/Markdown
./export_excel_sync.sh --output <file>              # DB → Excel sync
```

**Output formats**:
- Query commands: Markdown tables or JSON (`--json` flag)
- Mermaid diagrams for critical paths
- Excel multi-sheet for dashboards

**Error handling**: Unified error codes (ERR_INVALID_PARAM, ERR_NOT_FOUND, etc.)

### Testing

```bash
# Run all tests
./scripts/test.sh

# Run specific test
./scripts/test.sh test_query_stages
```

## Directory Structure

```
innogreen-pmo/
├── README.md                           # Quick start guide
├── development_plan_v1.0.md            # Project specification (v1.2)
├── CHANGELOG.md                        # Change log
├── data/
│   ├── innogreen_pmo.db               # SQLite database (generated at runtime)
│   ├── innogreen_pmo.backup.db        # Backup file
│   └── csv/                           # CSV intermediate files
│       ├── stages.csv
│       ├── tasks.csv
│       ├── pitfalls.csv
│       └── projects.csv
├── reference/                          # Background documents
│   ├── 创新中心简介20260227.docx
│   ├── 创新中心科创项目全生命周期流程图-20251230.pdf
│   ├── 全生命周期流程图(2).png
│   └── 工作阶段划分.xlsx
├── excel/
│   ├── 工作阶段划分_v2.xlsx            # 5-sheet upgraded version
│   └── 工作阶段划分_v1.xlsx            # Original version archive
├── sql/
│   ├── schema.sql                      # 7 table definitions
│   ├── seed.sql                        # Initial data
│   ├── indexes.sql                     # Index definitions
│   ├── triggers.sql                    # Auto-update triggers
│   └── queries.sql                     # Common query templates
├── scripts/
│   ├── init_db.sh                      # One-click initialization
│   ├── backup_db.sh                    # Database backup
│   ├── query_*.sh                      # Query commands (5)
│   ├── add_*.sh                        # Entry commands (2)
│   ├── update_progress.sh              # Progress update
│   └── export_*.sh                     # Export commands (2)
├── lib/
│   ├── db_utils.sh                     # Database utility functions
│   ├── validate.sh                     # Validation functions
│   └── format.sh                       # Format output functions
├── tests/
│   ├── test_schema.sh                  # Schema tests
│   ├── test_cli.sh                     # CLI tests
│   └── test_data/                      # Test data
└── docs/
    ├── 阶段地图说明.md
    ├── 避坑指南编写指南.md
    ├── 日常使用手册.md
    ├── CLI命令参考.md
    └── 数据库设计文档.md
```

## Key Design Decisions

### v1 Scope (In Scope)
- Content layer: 18-stage process map with 92 task nodes + pitfalls
- SQLite database with 7 tables (single writer, no server needed)
- 10 CLI tools (shell + sqlite3 + jq)
- Excel v2 with 5 sheets

### v1 Scope (Out of Scope)
- ❌ Web application / GUI (deferred to v3)
- ❌ Feishu bot notifications (deferred to v3)
- ❌ Multi-user permissions / auth (deferred to v3)
- ❌ Real-time collaboration

### Language Convention

- **Project language**: Mixed — planning docs in Chinese, code in English
- **Variable names**: English (e.g., `stage_id`, `pitfall_guide`)
- **Comments**: Chinese for business logic explanations preferred
- **CLI output**: Chinese (user-facing messages to Daniel's team)

### Acceptance Criteria

V1 is complete when Daniel's team can:
1. Query via SQL: "How many of 17 companies are in '装修施工' stage? Which ones are blocked and on what task?"
2. Enter a new company profile via CLI and verify it in both DB and Excel export
3. Query pitfalls for any stage and verify all 12 required fields are present
4. Export a progress dashboard showing all companies' current status, progress %, and blockers
5. View critical path for any project as a Mermaid flowchart

## Reference Documents

- [development_plan_v1.0.md](development_plan_v1.0.md) — Complete project specification v1.2 (Chinese)
- 工作阶段划分.xlsx — Source 18-stage process map with 92 task nodes
- 创新中心简介20260227.docx — Center introduction and 17+ tenant companies
- 创新中心科创项目全生命周期流程图-20251230.pdf — Full lifecycle workflow diagram
- Proxxima.md — Reference: ExxonMobil project schedule (100 tasks, 377 days), English terminology reference only
