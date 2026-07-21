# Innogreen PMO Web 应用方案 v1.3（修订稿）

> 修订日期：2026-07-21  
> 状态：**Daniel 决策已确认**（含前端：React + Ant Design）  
> 前置文档：development_plan_v1.0.md（正文版本为 **v1.2 CLI/数据底座**）  
> 修订原因：原 v1.3 过早扩大用户范围、缺少验收/安全/部署；本修订稿收敛范围并补齐工程缺口。
>
> **勘误（2026-07-21，实现已落地）**：鉴权已从文中规划的 Bearer `PMO_API_TOKEN` 演进为
> **会话 cookie + bcrypt + 三角色（admin/operator/viewer）+ 用户表**。下文 §5 仍保留历史
> Token 叙述作决策背景；以 `web/README.md`、`web/.env.example` 与代码为准。Phase C3 已完成。

---

## 〇、版本路线（统一口径）

| 版本 | 定位 | 交付物 | 用户 |
|------|------|--------|------|
| **v1.2** | 数据 + CLI 底座 | 7 表 SQLite、Excel v2、查询/导入 CLI | Daniel 团队（技术侧） |
| **v1.3**（本文） | **内网运营端**（企业就绪骨架） | FastAPI + 前端 Dashboard | Daniel 团队；企业端 **不上线** |
| **v1.4** | 企业只读门户 | 租户登录、仅见本企业 | 企业项目对接人 |
| **v1.5+** | 协同增强 | 飞书提醒、完整 RBAC、Docker 部署 | 全员 |

**近期**：团队内部使用。  
**远期**：开放企业端。  
**开发策略（Q1）**：**按「将来有企业端」的逻辑分层设计**，v1.3 **不实现**企业登录与租户上线。详见 §1.4。

**依赖**：v1.3 开发前，完成「阶段/任务/依赖可查询 + ≥2 家**脱敏真实案例**进度」。无样例数据则不做 Dashboard。

> 说明：development_plan_v1.0.md 文件名历史遗留，正文以 v1.2 为准。

---

## 一、升级决策（修订）

### 1.1 为什么做 Web

| 维度 | v1.2 CLI | v1.3 Web（修订） |
|------|----------|------------------|
| 日常查看 | 需终端 + 命令记忆 | 浏览器打开即可 |
| 移动办公 | 弱 | 响应式只读可用 |
| 学习曲线 | 需 SQL/Shell | 运营同学可自助 |
| 用户范围 | Daniel 团队 | **近期仅团队；架构预留企业端** |
| 写入方式 | CLI 为主 | Web 受控写入（必鉴权）+ CLI 批量 |

### 1.2 决策结论

1. **做 Web**：近期运营看板；远期企业门户 —— **同构设计、分期上线**。  
2. **保留 CLI**：批量导入、依赖校验、Excel 同步、自动化脚本。  
3. **单写者原则**：业务写入优先走 FastAPI；CLI 与 API 禁止并发写同一 SQLite。  
4. **写入必鉴权**（Q2）：Bearer Token / 单口令。  
5. **样例数据**（Q4）：真实案例流程，**名称脱敏为编号**（如 ENT-01）。  
6. **部署**（Q5）：先本机启动；Docker 后续再做。

### 1.3 明确不做（v1.3 上线范围）

- 企业客户真实登录 / 对外租户门户  
- 飞书机器人推送  
- 实时协作、WebSocket  
- 公网默认暴露、完整 RBAC / SSO  
- Docker 生产部署（不阻塞本机）  
- 现在就迁 PostgreSQL（20–50 家内网通常仍够用）

### 1.4 「按企业端逻辑开发」——做什么 / 不做什么（答 Q1）

**可以，且建议这样做。**「企业就绪」落在**边界与数据**，而不是现在做完整多租户产品。

| 现在就做（企业就绪骨架） | 现在不做（避免过度设计） |
|--------------------------|--------------------------|
| API 分命名空间：/api/ops/*（运营）与预留 /api/tenant/*（企业） | 真实企业账号、邀请、重置密码 |
| project_profile 增加稳定对外编号 project_code（脱敏展示） | 每企业独立数据库 |
| tenant 侧查询必须带本企业 project_id 过滤 | 10+ 角色的复杂 RBAC |
| 角色枚举预留：ops_admin / ops_viewer / tenant_viewer（v1.3 只用 ops_*） | JWT 刷新、SSO、飞书扫码 |
| 定义两套 response schema：OpsProject vs TenantProject（字段白名单） | 为「上千家」做分库分表 |
| 前端路由预留 /ops/* 与 /tenant/*；v1.3 只实现 /ops | 两套独立前端仓库 |

**原则**：v1.3 只上线运营端；企业端是空壳路由 + schema + 按 project 过滤约定。v1.4 主要加登录并启用 /api/tenant，不重写进度模型。

**规模（5 → 20–50 家）**：瓶颈不在框架性能，而在权限是否按 project 隔离。按上表即可覆盖远期只读门户。

---

## 二、前置条件（Phase A 完成标准）

> **更新：2026-07-21 Phase A 已通过 ✅**

| # | 条件 | 验证方式 | 实际结果 |
|---|------|----------|----------|
| A1 | schema.sql 可一键建库（7 表 + 索引 + 触发器） | init_db 成功 | ✅ 7表创建成功 |
| A2 | 8 阶段 + 100+ 任务已导入 | COUNT 返回 8 / 107 | ✅ 阶段8/任务107 |
| A3 | 核心任务依赖已导入且方向校验通过 | 无自环 | ✅ 69条依赖，0自环，父子方向已修 |
| A4 | ≥2 家脱敏企业（ENT-01）+ 进度（含 ≥1 卡点） | 界面不出现真名 | ✅ 3家，2卡点 |
| A5 | 避坑结构就绪；内容 ≥4 条试点 | 列表不报错 | ✅ 4条避坑 |
| A6 | Windows 可运行（Python CLI） | 本机查询跑通 | ✅ 通过 |

**Phase A 已通过，可以开始 Web 开发。**

**脱敏约定（Q4）**：
- 对外展示统一用编号（ENT-01…）；真名对照表**不进 Git**。
- 对照文件：`data/private/name_map.local.csv`（需创建并加入 .gitignore）。
- 进度/阶段/卡点保持真实业务语义，只抹去可识别主体。

**数据说明**：
- **8阶段**：0.初步意向 → 1.项目准入 → 2.前期审批 → 3.公用工程合同 → 4.施工审批 → 5.施工验收 → 6.试生产三同时 → 7.正式投用
- **107任务**：采用层级编号（task_code 字段），如 `2.2.1` = 阶段2 > 一级任务2 > 二级任务1
- **69依赖**：基于业务逻辑；父子任务为「子步骤链 + 父任务闭环」，禁止子依赖父

---

## 三、技术栈

| 层级 | 技术 | 选择理由 |
|------|------|----------|
| 后端 | FastAPI + Uvicorn | OpenAPI、与 Python 导入同语言 |
| ORM | SQLAlchemy 2.0 | 映射现有 7 表 |
| 校验 | Pydantic v2 | Ops / Tenant 两套 schema |
| 数据库 | SQLite + WAL | 50 家内网只读足够 |
| 前端 | **React 18 + Vite + React Router** | Q3 已确认 |
| UI | **Ant Design 5**（默认） | 运营表格/表单成熟；不与 MUI 混用 |
| 数据请求 | Axios（可选 TanStack Query） | 列表请求 |
| 鉴权 | Bearer Token | Q2 已确认 |

**运行时（Windows）**：Python 3.11+、Node 20+；**本机双进程启动**（Q5），Docker 后置。

### 3.1 前端选型结论（Q3）

**已确认：React + Ant Design。**

| 项 | 决定 |
|----|------|
| 框架 | React 18 + TypeScript（推荐）+ Vite |
| 路由 | React Router 6 |
| UI | Ant Design 5（antd + @ant-design/icons） |
| 备选 | 维护人更熟 MUI 时可整栈改用；**禁止** antd 与 MUI 混用 |
| 企业端 | 同仓 /tenant/* 路由，v1.4 启用 |

Vue / Vuetify 方案作废；脚手架一律按 React。

---

## 四、系统架构

```
┌──────────────────────────────────────────────┐
│           浏览器（内网：PC / 手机）              │
└──────────────────────┬───────────────────────┘
                       │ HTTPS 或内网 HTTP
                       │ Authorization: Bearer <token>
                       ▼
┌──────────────────────────────────────────────┐
│         FastAPI（唯一业务写入口）                │
│  /api/ops/*     运营端（v1.3 实现）             │
│  /api/tenant/*  企业端（v1.3 预留空壳/401）     │
│  /health  /docs（可关）                         │
└──────────────────────┬───────────────────────┘
                       │ SQLAlchemy · WAL
                       ▼
┌──────────────────────────────────────────────┐
│         SQLite: data/innogreen_pmo.db          │
│         备份: data/backups/YYYYMMDD_*.db       │
└──────────────────────────────────────────────┘
          ▲
          │ 批量导入 / Excel 同步（停写或短维护窗）
┌─────────┴─────────┐
│  CLI / Python 脚本  │
└───────────────────┘
```

### 4.1 SQLite 运维约定

| 项 | 约定 |
|----|------|
| 日志模式 | `PRAGMA journal_mode=WAL;`（init 时设置） |
| 备份 | 每日或每次批量导入前复制到 `data/backups/` |
| 并发写 | 禁止 CLI 与 API 同时写；导入时停 API 或只读模式 |
| 锁超时 | `busy_timeout=5000` |
| 迁移 | v1.3 不改表结构；若改，必须同步更新 `schema.sql` 与 v1.2 文档 |

---

## 五、安全与访问控制（最小可行）

### 5.1 部署边界

- 默认绑定内网地址（如 `127.0.0.1` 或园区内网 IP），**不默认 `0.0.0.0` 公网**。  
- 生产关闭或保护 `/docs`、`/redoc`（环境变量 `ENABLE_DOCS=false`）。

### 5.2 鉴权

| 操作 | 要求 |
|------|------|
| GET 只读 | 可选：同一 Bearer Token（建议开启，防误扫） |
| POST/PUT/PATCH/DELETE | **必须** Bearer Token（`PMO_API_TOKEN`） |
| 前端 | 启动时读本地配置或登录页单口令，写入 `localStorage`（内网可接受） |

**Bearer Token 规范**：

| 项 | 规范 |
|----|------|
| 格式 | 32+ 字符字符串（UUID4 或随机十六进制） |
| 示例 | `a1b2c3d4-e5f6-7890-abcd-ef1234567890` |
| 生成方式 | `python -c "import secrets; print(secrets.token_hex(32))"` |
| 存储 | `.env` 文件，**不提交到 Git** |
| 轮换 | 通过修改 `.env` 中的 `PMO_API_TOKEN`，重启 API 生效 |

v1.3 **不做**：用户表、角色、JWT 刷新、SSO。这些归 v1.4。

### 5.3 审计（轻量）

写入接口记录：`who`（token 别名即可）、`action`、`project_id`、`task_id`、`at`。  
可用简单表 `audit_log`，或先写 JSONL 文件 `data/audit.log`。推荐一张小表，便于看板展示「最近变更」。

---

## 六、API 设计

### 6.1 端点一览

| 资源 | 方法 | 路径 | 鉴权 | 说明 |
|------|------|------|------|------|
| 健康 | GET | `/health` | 无 | 探活 |
| 阶段 | GET | `/api/ops/stages` | 读 | 列表，含任务数 |
| 阶段 | GET | `/api/ops/stages/{id}` | 读 | 详情 |
| 阶段 | GET | `/api/ops/stages/{id}/tasks` | 读 | 阶段下任务 |
| 任务 | GET | `/api/ops/tasks` | 读 | 可筛 `stage_id` |
| 任务 | GET | `/api/ops/tasks/{id}` | 读 | 详情 |
| 任务 | GET | `/api/ops/tasks/{id}/dependencies` | 读 | 前驱/后继 |
| 企业 | GET | `/api/ops/projects` | 读 | 筛 status / stage / building；展示 `project_code` |
| 企业 | GET | `/api/ops/projects/{id}` | 读 | 详情 + 汇总进度 |
| 企业 | POST | `/api/ops/projects` | 写 | 新增（必填含 `project_code`） |
| 企业 | PATCH | `/api/ops/projects/{id}` | 写 | 部分更新 |
| 进度 | GET | `/api/ops/projects/{id}/progress` | 读 | 该企业全部任务进度 |
| 进度 | PUT | `/api/ops/projects/{id}/tasks/{task_id}` | 写 | **按项目+任务 upsert** |
| 关键路径 | GET | `/api/ops/projects/{id}/critical-path` | 读 | 节点+边 |
| 卡点 | GET | `/api/ops/progress/blockers` | 读 | 全局卡点列表 |
| 避坑 | GET | `/api/ops/pitfalls` | 读 | 筛 stage / impact / q |
| 避坑 | GET | `/api/ops/pitfalls/{id}` | 读 | 详情 |
| 避坑 | POST | `/api/ops/pitfalls` | 写 | 新增（运营录入） |
| 仪表盘 | GET | `/api/ops/dashboard/summary` | 读 | 统计 + 卡点摘要 |
| 企业端（预留） | GET | `/api/tenant/me/project` 等 | — | v1.3 返回 501 或空实现 |

兼容说明：若需短路径，可用路由 alias；**对外文档以 `/api/ops` 为准**。  
**废弃**：`PUT /api/progress/{id}`。

### 6.2 进度更新契约

```http
PUT /api/ops/projects/{project_id}/tasks/{task_id}
Authorization: Bearer <token>
Content-Type: application/json

{
  "status": "卡点",
  "blocker_note": "安评报告等待专家评审",
  "assigned_to": "张三"
}
```

服务端行为：

- upsert `project_progress`  
- `status=已完成` → 写 `completed_at`  
- `status=卡点` → 同步 `project_profile.project_status=卡点`  
- 重新计算并回写 `progress_percent`（按该企业已完成任务数 / 适用任务数）  
- 写审计日志  

### 6.3 响应示例

```json
{
  "project_id": 1,
  "project_code": "ENT-01",
  "company_name": "ENT-01",
  "short_name": "ENT-01",
  "business_type": "研发",
  "current_stage_id": 13,
  "current_stage_name": "装修施工",
  "progress_percent": 60,
  "project_status": "卡点",
  "building": "F6d-1"
}
```

```json
{
  "total_projects": 3,
  "by_status": { "进行中": 2, "卡点": 1, "已完成": 0 },
  "by_stage": { "装修施工": 2, "设计审查": 1 },
  "blockers": [
    {
      "project_id": 1,
      "project": "ENT-01",
      "task_id": 15,
      "task": "安评报告",
      "note": "等待专家评审"
    }
  ]
}
```

### 6.4 错误格式

与 CLI 错误语义对齐：

```json
{
  "error": true,
  "code": "ERR_NOT_FOUND",
  "message": "项目不存在: 99"
}
```

HTTP：400 参数 / 404 未找到 / 401 未鉴权 / 409 冲突 / 500 内部错误。

---

## 七、前端页面

### 7.1 页面结构

| 页面 | 路由 | 优先级 | 核心功能 |
|------|------|--------|----------|
| Dashboard | `/ops` | P0 | 企业卡片（显示 ENT-xx）、卡点、阶段分布 |
| 企业列表 | `/ops/projects` | P0 | 搜索、状态/阶段筛选 |
| 企业详情 | `/ops/projects/:id` | P0 | 进度、任务清单、**关键路径图** |
| 进度更新 | `/ops/projects/:id/tasks/:taskId` | P0 | 改状态、卡点备注（需 token） |
| 新增企业 | `/ops/projects/new` | P1 | 必填含 project_code |
| 阶段地图 | `/ops/stages` | P1 | 8 阶段可视化 |
| 阶段详情 | `/ops/stages/:id` | P1 | 任务列表 + 关联避坑 |
| 避坑指南 | `/ops/pitfalls` | P1 | 筛选 / 搜索 |
| 避坑详情 | `/ops/pitfalls/:id` | P2 | 12 字段卡片 |
| 登录/口令 | `/login` | P0 | 写入 Bearer Token |
| 企业端占位 | `/tenant/*` | — | v1.3 仅占位页「即将开放」 |

### 7.2 UI 规范（运营工具，非品牌站）

组件库：**Ant Design 5**（`ConfigProvider` 主题）。

```
colorPrimary:  #1677ff   （antd 默认蓝即可，可微调）
colorError:    #ff4d4f   （卡点）
colorWarning:  #faad14   （重要）
colorSuccess:  #52c41a   （完成）
```

关键路径标记：红 / 黄 / 绿文字或 Tag，不依赖 emoji。

### 7.3 关键路径展示

- 数据来自 `/api/ops/projects/{id}/critical-path`  
- 前端：Ant Design `Steps` / 时间轴 **优先**（移动端更稳）；可选再加 Mermaid

---

## 八、项目结构

```
innogreen-pmo/
├── development_plan_v1.0.md          # v1.2 数据/CLI 规格（文件名历史遗留）
├── development_plan_v1.3_web_app.md  # 本文
├── data/
│   ├── innogreen_pmo.db
│   └── backups/
├── sql/                              # v1.2 产出，Web 只读引用
│   ├── schema.sql                    # v1.2 原 schema（7表）
│   └── schema_v1.3.sql              # v1.3 完整 schema（含新增字段和表）
│       ├── 步骤1: 添加 project_code   -- ALTER TABLE project_profile ADD COLUMN project_code TEXT UNIQUE;
│       ├── 步骤2: 创建 audit_log     -- 详见 §13.2.2
│       └── 步骤3: 创建索引           -- 详见 §13.2.2
├── scripts/                          # CLI / 导入（批量窗使用）
├── web/
│   ├── backend/
│   │   ├── main.py
│   │   ├── config.py                 # DB 路径、TOKEN、WAL、DOCS 开关
│   │   ├── database.py
│   │   ├── models/
│   │   │   ├── stage.py
│   │   │   ├── task.py
│   │   │   ├── project.py
│   │   │   ├── progress.py
│   │   │   ├── pitfall.py
│   │   │   └── audit.py             # Phase C 新增
│   │   ├── schemas/
│   │   │   ├── ops.py               # 运营端 schema（含写操作）
│   │   │   ├── tenant.py            # 企业端 schema（预留，v1.4）
│   │   │   └── common.py            # 错误响应、枚举
│   │   ├── routers/
│   │   │   ├── stages.py
│   │   │   ├── tasks.py
│   │   │   ├── projects.py
│   │   │   ├── progress.py
│   │   │   ├── pitfalls.py
│   │   │   ├── dashboard.py
│   │   │   └── tenant.py            # 预留空壳（v1.3 返回 501）
│   │   ├── services/
│   │   │   ├── progress_service.py
│   │   │   ├── critical_path_service.py
│   │   │   └── audit_service.py     # Phase C 新增
│   │   └── deps.py                   # 鉴权依赖
│   ├── frontend/                     # React + Ant Design
│   │   ├── src/
│   │   │   ├── pages/
│   │   │   │   ├── ops/             # 运营端页面（v1.3 实现）
│   │   │   │   │   ├── Dashboard.tsx
│   │   │   │   │   ├── ProjectList.tsx
│   │   │   │   │   ├── ProjectDetail.tsx
│   │   │   │   │   ├── TaskUpdate.tsx
│   │   │   │   │   ├── ProjectNew.tsx
│   │   │   │   │   ├── StageMap.tsx
│   │   │   │   │   ├── StageDetail.tsx
│   │   │   │   │   ├── PitfallList.tsx
│   │   │   │   │   └── PitfallDetail.tsx
│   │   │   │   └── tenant/          # 企业端占位（v1.3）
│   │   │   │       └── Placeholder.tsx
│   │   │   ├── components/
│   │   │   │   ├── StageCard.tsx
│   │   │   │   ├── TaskItem.tsx
│   │   │   │   ├── BlockerTag.tsx
│   │   │   │   └── CriticalPath.tsx
│   │   │   ├── api/
│   │   │   │   ├── client.ts        # Axios 实例
│   │   │   │   ├── ops.ts           # 运营端 API
│   │   │   │   └── tenant.ts        # 企业端 API（预留）
│   │   │   ├── routes/
│   │   │   │   ├── index.tsx        # 路由汇总
│   │   │   │   ├── opsRoutes.tsx    # /ops/* 路由
│   │   │   │   └── tenantRoutes.tsx # /tenant/* 占位
│   │   │   ├── auth/
│   │   │   │   └── TokenContext.tsx # Bearer Token 上下文
│   │   │   ├── App.tsx
│   │   │   └── main.tsx
│   │   ├── package.json
│   │   ├── tsconfig.json
│   │   └── vite.config.ts
│   ├── requirements.txt
│   ├── .env.example
│   └── README.md
└── tests/
    ├── test_api/                     # pytest
    │   ├── test_health.py
    │   ├── test_projects.py
    │   ├── test_progress.py
    │   ├── test_auth.py
    │   └── test_critical_path.py
    └── test_data/
```

---

## 九、开发计划（修订工期）

原「6 天全做完」偏乐观。按前置 + 分期：

### 9.1 Phase A — 数据底座（若未完成，3–4 天）

| 项 | 内容 |
|----|------|
| A1 | schema / init / WAL |
| A2 | Excel→CSV→DB |
| A3 | 依赖导入 + 方向校验脚本 |
| A4 | 2–3 家样例企业 + 进度 + 1 条卡点 |
| A5 | 最小查询脚本（Python 优先） |

### 9.2 Phase B — 只读 Web（3–4 天）

> **更新：2026-07-21 Phase B 骨架已落地 ✅**（FastAPI 只读 API + React/Ant Design 运营端）

| 日 | 内容 | 状态 |
|----|------|------|
| B1 | 后端脚手架、models、只读 API、鉴权骨架 | ✅ |
| B2 | Dashboard + 企业列表/详情（只读） | ✅ |
| B3 | 阶段地图 + 避坑列表 | ✅ |
| B4 | 关键路径 Steps + 响应式布局 + 冒烟 | ✅ |

**Phase B 可联调后，再开 Phase C 写入。**

### 9.3 Phase C — 受控写入（2–3 天）

| 日 | 内容 |
|----|------|
| C1 | PUT 进度 upsert + 百分比回写 + 审计 |
| C2 | 新增/编辑企业表单 |
| C3 | 避坑录入（可选）+ 文档 + 备份脚本联调 |

**v1.3 合计（含已完成的 Phase A 则约 5–7 天；A 未做则约 8–11 天）。**

---

## 十、验收标准（v1.3 Done）

### 10.1 Phase B（只读）

| # | 场景 | 通过标准 |
|---|------|----------|
| B-T1 | 打开 Dashboard | 看到样例企业数、阶段分布、卡点列表非空 |
| B-T2 | 筛选「卡点」 | 与 SQL `status='卡点'` 结果一致 |
| B-T3 | 打开企业详情 | 显示当前阶段、任务状态、关键路径可读 |
| B-T4 | 阶段地图 | 8 个阶段可点进任务列表 |
| B-T5 | 手机宽度 | 关键列表不横向溢出到不可用 |
| B-T6 | 无 Token 写接口 | 返回 401 |

### 10.2 Phase C（写入）

| # | 场景 | 通过标准 |
|---|------|----------|
| C-T1 | 将某任务标为卡点 | DB 中 progress + project_status 正确；Dashboard 出现该卡点 |
| C-T2 | 标为已完成 | `completed_at` 有值；`progress_percent` 上升 |
| C-T3 | 新增企业 | DB 可查；列表可见 |
| C-T4 | CLI 批量导入后 | 刷新 Web 可见新数据（同一 DB） |
| C-T5 | 备份 | `backup` 脚本生成可还原文件 |

### 10.3 回归（与 v1.2 对齐）

仍须能回答：

1. 多少企业在「装修施工」？  
2. 谁卡点、卡在哪个任务？  
3. 某阶段避坑字段是否完整（有内容时）？  

---

## 十一、启动与配置

### 11.1 环境变量（`.env.example`）

```bash
# ============ 数据库 ============
PMO_DB_PATH=../data/innogreen_pmo.db

# ============ 鉴权（必填，v1.3 启动前必须修改）============
# 生成方式：python -c "import secrets; print(secrets.token_hex(32))"
PMO_API_TOKEN=change-me-in-production

# ============ 服务 ============
PMO_HOST=127.0.0.1
PMO_PORT=8000
PMO_ENABLE_DOCS=true
```

### 11.2 开发启动

```bash
# 后端
cd web/backend
pip install -r ../requirements.txt
uvicorn main:app --reload --host 127.0.0.1 --port 8000

# 前端
cd web/frontend
npm install
npm run dev
```

- 前端：`http://127.0.0.1:5173`  
- API 文档（开发）：`http://127.0.0.1:8000/docs`

### 11.3 依赖

**requirements.txt（建议钉最低版本）**：

```
fastapi>=0.100
uvicorn[standard]>=0.20
sqlalchemy>=2.0
pydantic>=2.0
pydantic-settings>=2.0
python-dotenv>=1.0
```

**前端（package.json 核心依赖）**：

```json
{
  "dependencies": {
    "react": "^18.2",
    "react-dom": "^18.2",
    "react-router-dom": "^6.22",
    "antd": "^5.14",
    "@ant-design/icons": "^5.3",
    "axios": "^1.6"
  },
  "devDependencies": {
    "typescript": "^5.3",
    "vite": "^5.1",
    "@vitejs/plugin-react": "^4.2"
  }
}
```

### 11.4 部署（v1.3 最小）

| 方式 | 适用 |
|------|------|
| **本机双进程**（uvicorn + vite dev / preview） | **v1.3 默认（Q5 已确认）** |
| `docker-compose`（api + 静态，挂载 `data/`） | **后续迭代**，不阻塞首版 |

README 须写清本机启动步骤，以及如何让同事在内网用浏览器打开（含改 `PMO_HOST` 的风险说明）。

---

## 十二、与 CLI 的关系

| 场景 | CLI / 脚本 | Web |
|------|------------|-----|
| 批量导入阶段/任务/依赖 | 主路径 | 不做 |
| Excel ↔ DB 同步 | 主路径 | 不做 |
| 日常查询看板 | 备选 | 主路径 |
| 进度点选更新 | 备选 | 主路径（Phase C） |
| 自动化 / CI 校验 | 主路径 | `/health` 即可 |

**数据**：共用 `data/innogreen_pmo.db`。  
**同步语义**：不是「双向实时同步服务」，而是「同一文件、单写者、读方即时可见」。

---

## 十三、数据模型

沿用 v1.2 七表（详见 `development_plan_v1.0.md` 第三章）：

- `stage_map` / `task_detail` / `task_dependency`
- `pitfall_guide` / `stage_pitfall_ref`
- `project_profile` / `project_progress`

### 13.1 v1.3 建模注意（修订）

| 点 | 要求 |
|----|------|
| 避坑关联 | 查询以 `stage_pitfall_ref` 为准；`stage_ref` 仅作展示冗余，录入时同时写关联表 |
| 依赖方向 | `depends_on` = 前置任务；导入后跑校验脚本，禁止注释与数据相反 |
| 类型 | SQLite 无真正 DECIMAL/DATE；金额/日期在 Pydantic 层校验 |
| **task_code** | `task_detail` 增加 `task_code` 字段（如 `2.2.1`），保留Excel层级编号便于对照 |
| **project_code** | `project_profile.project_code` 唯一编号（如 ENT-01）；UI 默认展示此字段 |

### 13.2 v1.3 Schema 变更

#### 13.2.1 task_detail 新增字段

```sql
-- task_detail 表新增 task_code 字段（已实现）
ALTER TABLE task_detail ADD COLUMN task_code TEXT;
-- 示例值: '2.2.1' = 阶段2 > 任务2 > 子任务1
```

#### 13.2.2 audit_log 表（Phase C 新增）

```sql
-- v1.3/Phase C 新增审计表
-- 文件位置：sql/audit_log.sql
CREATE TABLE IF NOT EXISTS audit_log (
  audit_id       INTEGER PRIMARY KEY AUTOINCREMENT,
  actor          TEXT NOT NULL,              -- token别名或user_id
  action         TEXT NOT NULL,             -- CREATE/UPDATE/DELETE
  resource       TEXT NOT NULL,              -- projects/tasks/pitfalls/progress
  resource_id    INTEGER,                    -- 被操作的记录ID
  payload        TEXT,                       -- JSON变更详情
  created_at     TEXT DEFAULT (datetime('now'))
);
```

### 13.2 v1.3 新增字段

#### 13.2.1 project_profile 新增字段

```sql
-- v1.3 启动前执行（已有库需迁移）
ALTER TABLE project_profile ADD COLUMN project_code TEXT UNIQUE;
```

**说明**：脱敏展示字段，格式为 `ENT-01`、`ENT-02` 等。

> **注意**：新库初始化可直接使用 `sql/schema_v1.3.sql`（包含此字段）。

#### 13.2.2 新增 audit_log 表（Phase C）

```sql
-- v1.3/Phase C 新增审计表
-- 文件位置：sql/audit_log.sql
CREATE TABLE IF NOT EXISTS audit_log (
  audit_id       INTEGER PRIMARY KEY AUTOINCREMENT,
  actor          TEXT NOT NULL,              -- token别名或user_id
  action         TEXT NOT NULL,             -- CREATE/UPDATE/DELETE
  resource       TEXT NOT NULL,              -- projects/tasks/pitfalls/progress
  resource_id    INTEGER,                    -- 被操作的记录ID
  payload        TEXT,                       -- JSON变更详情
  created_at     TEXT DEFAULT (datetime('now'))
);

-- 索引
CREATE INDEX idx_audit_actor ON audit_log(actor);
CREATE INDEX idx_audit_resource ON audit_log(resource, resource_id);
CREATE INDEX idx_audit_time ON audit_log(created_at);
```

**写入时机**：POST/PATCH/DELETE 操作时记录。

> **注意**：将上述 SQL 保存为 `sql/audit_log.sql`，初始化时执行。

### 13.3 Tenant Schema（预留）

```python
# schemas/tenant.py
from pydantic import BaseModel

class TenantProject(BaseModel):
    """企业端可见字段（白名单）"""
    project_id: int
    company_name: str          # 脱敏编号（实际存储为 ENT-01）
    short_name: str | None
    business_type: str | None
    current_stage_name: str    # JOIN stage_map 获取
    progress_percent: int
    project_status: str
    building: str | None
    updated_at: str

    class Config:
        from_attributes = True
```

> 注意：即使 v1.3 未启用 /api/tenant，也应先定义 schema，避免 v1.4 重写。

---

## 十四、风险与应对

| # | 风险 | 等级 | 应对 |
|---|------|------|------|
| R1 | 无样例数据导致空壳 UI | 高 | 强制 Phase A 门禁 |
| R2 | CLI 与 API 并发写坏库 | 高 | 单写者约定 + WAL + 导入维护窗 |
| R3 | 内网口令泄露 | 中 | Token 可轮换；v1.4 再上用户体系 |
| R4 | 依赖 ID 与 Excel 错位 | 高 | 用业务键（阶段名+任务名）解析后再写 ID |
| R5 | 工期膨胀 | 中 | B/C 分期验收，不做企业门户 |
| R6 | Windows 脚本兼容 | 中 | **统一使用 Python**（web/ 与 scripts/ 均用 Python） |

### 十四.1 Windows 兼容性措施

| 目录 | 措施 |
|------|------|
| `scripts/` | 提供 Python 等效脚本（`scripts/*.py`）替代 shell |
| `web/backend/` | 纯 Python，无 shell 依赖 |
| `web/frontend/` | npm/Vite 跨平台，无需额外处理 |
| 数据库 | SQLite 跨平台，无需迁移 |

**注意**：原 v1.2 文档中的 `scripts/*.sh` 可保留用于 Linux/macOS；Windows 用户使用 Python 版本。

---

## 十五、测试策略

| 层 | 工具 | 最小集 |
|----|------|--------|
| API | pytest + httpx | health、projects 列表、blocker、进度 upsert、401 |
| 数据 | SQL 断言 | 18/92 计数、依赖无自环 |
| 前端 | 手动清单 | 第十章 B-T / C-T |
| 回归 | 对比同一查询 | CLI/SQL 与 Dashboard 数字一致 |

### 15.1 API 测试用例（pytest）

```python
# tests/test_api/test_health.py
def test_health_returns_200():
    """健康检查应返回 200"""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"

# tests/test_api/test_auth.py
def test_write_without_token_returns_401():
    """无 token 写入应返回 401"""
    response = client.post("/api/ops/projects", json={"company_name": "test"})
    assert response.status_code == 401

def test_read_without_token_allowed():
    """只读操作可不带 token（取决于配置）"""
    response = client.get("/api/ops/projects")
    # 根据 PMO_API_TOKEN 配置决定预期状态码

# tests/test_api/test_projects.py
def test_list_projects_returns_data():
    """项目列表应返回数据"""
    response = client.get("/api/ops/projects")
    assert response.status_code == 200
    assert "data" in response.json() or isinstance(response.json(), list)

def test_filter_by_status():
    """按状态筛选应生效"""
    response = client.get("/api/ops/projects?status=卡点")
    assert response.status_code == 200

# tests/test_api/test_progress.py
def test_progress_upsert_blocker():
    """将任务标为卡点 → project_status 同步更新"""
    # 1. 创建测试项目
    proj_resp = client.post("/api/ops/projects", json={
        "company_name": "test-blocker",
        "project_code": "TST-001",
        "business_type": "研发"
    })
    project_id = proj_resp.json()["project_id"]

    # 2. 标记任务为卡点
    update_resp = client.put(
        f"/api/ops/projects/{project_id}/tasks/1",
        json={"status": "卡点", "blocker_note": "安评报告待审"},
        headers={"Authorization": "Bearer test-token"}
    )
    assert update_resp.status_code == 200

    # 3. 验证 project_profile.project_status 已更新
    proj_detail = client.get(f"/api/ops/projects/{project_id}")
    assert proj_detail.json()["project_status"] == "卡点"

def test_progress_complete_sets_completed_at():
    """标为已完成应设置 completed_at"""
    # ... 类似上述测试结构
```

### 15.2 数据校验测试

```bash
# tests/test_data/check_counts.sh
#!/bin/bash
# Phase A 门禁校验

DB_PATH="../data/innogreen_pmo.db"

echo "=== Phase A 数据校验 ==="

# A2: 计数校验
stage_count=$(sqlite3 "$DB_PATH" "SELECT COUNT(*) FROM stage_map;")
task_count=$(sqlite3 "$DB_PATH" "SELECT COUNT(*) FROM task_detail;")
dep_count=$(sqlite3 "$DB_PATH" "SELECT COUNT(*) FROM task_dependency;")

echo "阶段数: $stage_count (预期: 18)"
echo "任务数: $task_count (预期: 92)"
echo "依赖数: $dep_count (预期: ≥30)"

# A3: 自环检测
self_loop=$(sqlite3 "$DB_PATH" "SELECT COUNT(*) FROM task_dependency WHERE task_id = depends_on;")
echo "自环数: $self_loop (预期: 0)"

# A4: 样例数据检测
sample_count=$(sqlite3 "$DB_PATH" "SELECT COUNT(*) FROM project_profile WHERE project_code LIKE 'ENT-%';")
echo "样例企业: $sample_count (预期: ≥2)"
```

---

## 十六、Daniel 确认记录

| # | 问题 | 确认结果 |
|---|------|----------|
| Q1 | 近期团队用、远期企业端；是否按企业端逻辑开发？ | **是** — 采用 §1.4 企业就绪骨架；v1.3 不上线企业门户 |
| Q2 | 写入是否必须口令？ | **是** |
| Q3 | 前端 Vue 还是 React？ | **React + Ant Design 5**（不混用 MUI） |
| Q4 | 样例企业数据？ | **真实案例 + 名称脱敏为编号（ENT-xx）** |
| Q5 | 是否现在 Docker？ | **否** — 先本机；后续再 Docker |

执行顺序：**验收 Phase A（含脱敏样例）→ Phase B → Phase C**。

---

## 十七、变更记录

| 版本 | 日期 | 变更 |
|------|------|------|
| v1.3 初稿 | 2026-07-21 | CLI→Web 技术选型与页面草案 |
| v1.3 修订稿 | 2026-07-21 | 门禁、鉴权、WAL、验收、分期工期 |
| **v1.3 修订稿+决策** | **2026-07-21** | Q1–Q5 确认；前端锁定 React + Ant Design；`/api/ops` 分层 |
| **v1.3 补充更新** | **2026-07-21** | 补录：task_code/audit_log schema、前端目录结构、Bearer Token 规范、Windows 兼容性措施、pytest 测试用例 |
| **Phase A 完成** | **2026-07-21** | 数据底座验收通过：8阶段/107任务/69依赖/3企业样例 |
| **Phase A 修复** | **2026-07-21** | project_code、样例对齐、依赖父子方向、init_db 幂等、避坑 stage_ref |
| **Phase B 骨架** | **2026-07-21** | FastAPI 只读 API + React/Ant Design 运营端可联调 |
| **Phase B 优化** | **2026-07-21** | 前端代码分割(lazy)、WAL模式、审计模型+服务预留、写入Schema预留 |

---

**方案版本：v1.3 Phase B 完成，优化待 Phase C**
