# Innogreen PMO 项目开发方案 v1.2

> 存档日：2026-07-21
> 归档人：MiniMax-M3
> 用户：Daniel
> 项目：~/.hermes/projects/innogreen-pmo/
> 
> **更新记录 (v1.1 → v1.2)**:
> - 重构：数据模型从4张表扩展到7张表，修复关联字段设计
> - 新增：项目进度跟踪表(project_progress)
> - 新增：关联表(stage_pitfall_ref, task_dependency)
> - 新增：索引定义和约束
> - 新增：CLI工具完整规格说明
> - 细化：验收标准与测试用例
> - 明确：初始化数据来源和规格

---

## 零、背景资料

### 0.1 创新中心概况

**上海国际化工新材料创新中心（INNOGREEN创新绿洲）**是上海化学工业区积极对接"创新驱动"国家战略的重要阵地。

**定位方向**：创新引领、开放共建、产城融合、协同发展

**目标领域**：先进材料、集成电路、生物制造、循环经济、清洁能源等新赛道

**目标愿景**：建成具有国际影响力的化工新材料产业集聚区和创新策源地

#### 园区布局

| 区域 | 面积 | 功能定位 |
|------|------|----------|
| **创新中心一期** | ~5.8万㎡ | 基础设施和服务体系，研发孵化、成果转化及应用创新 |
| **创新中心二期** | ~4.2万㎡ | 高标准、定制化中试研发用房（高消防安全等级） |
| **F6d-1地块** | ~2.9万㎡ | 甲类生产厂房、甲类仓库、综合楼、变配电站 |
| **F6a-3地块** | ~3.6万㎡ | 甲类生产厂房、甲类仓库、公辅楼及配套设施 |

#### 服务产业领域

六大产业领域：高端装备制造、新能源、新能源汽车、新一代信息技术、节能环保、生命健康

#### 已入驻企业（部分）

- **跨国企业**：朗盛特殊化学品、罗姆化学、英威达尼龙化工、汉高化学技术、液化空气上海
- **国内企业**：上村化学、昕特玛新材料、集材微电子、昇合建物、合创绿洲、纳诺斯生物
- **科研机构**：上海电子化学品创新研究院（与华东理工大学合作共建）
- **其他**：华谊新材料、睿塑绿环、漕泾热电、凯米锐环境等

### 0.2 项目落地全生命周期流程

基于《创新中心科创项目全生命周期流程图》，项目从准入到正式投用需经过以下关键环节：

```
项目准入评估 → 厂房租赁及HSE协议 → 项目前期审批（安评/环评/卫评）
→ 设计审查 → 施工许可 → 装修施工 → 竣工验收 
→ 试生产 → 三同时验收 → 正式投用
```

### 0.3 阶段任务清单（来源：工作阶段划分.xlsx）

Excel文件共包含**8个主要阶段**，**107条任务节点**：

| 序号 | 阶段名称 | 任务数 | 关键度 | 说明 |
|------|----------|--------|--------|------|
| 0 | 初步意向 | 3 | 🟢 | 客户意向接触 |
| 1 | 项目准入 | 9 | 🔴 | 准入评估与厂房租赁 |
| 2 | 厂房改造项目前期审批准备 | 19 | 🔴 | 三评（安评/环评/卫评）及设计 |
| 3 | 公用工程及服务类合同签定 | 39 | 🟡 | 9类服务协议 |
| 4 | 厂房改造装修施工审批 | 13 | 🔴 | 审图、消防审查、施工许可 |
| 5 | 项目施工及验收 | 13 | 🔴 | 装修施工、机电安装、竣工验收 |
| 6 | 试生产及三同时验收 | 9 | 🔴 | 试生产与三同时验收 |
| 7 | 正式投用阶段 | 1 | 🟢 | 正式投产投用 |

> **任务编号**：采用层级编号（如 1.3.1 = 阶段1 > 一级任务3 > 二级任务1），保留Excel原始编码便于对照。

**任务层级说明**：
- 一级任务：如 2.1 项目设计、2.2 安评及安设专篇
- 二级任务：如 2.1.1 项目团队对接与沟通、2.2.1 安全预评价报告编制定稿

> **参考案例**：`Proxxima.md`（ExxonMobil项目进度计划，100任务，377天）
> - 用途：英文术语参考、装修施工详细任务参考
> - 注意：客户自整理，与标准模板不一定合拍，参考即可

**各类服务协议**涵盖：
- 厂房租赁与公用工程类合同
- 项目咨询服务协议
- 物业服务协议
- 消防维保协议
- 环保管家服务
- 污水处理服务协议
- 危废处理服务协议
- 冷热能源及蒸汽供应服务协议
- 供应链服务（危化品仓储与物流）
- 工业气体供应协议

---

## 一、项目目标与边界

### 1.1 目标
为 Innogreen 创新中心建立一套**「项目管理制度 + 内容知识库」数字底座**，让 17+ 家入驻企业（以及未来更多）能在统一的框架下推进项目落地，**沉淀运营 know-how**，支持 Daniel 团队从"房东+物业"升级为"合伙人式陪跑"。

### 1.2 范围（在）
- **内容层**：基于Excel的8阶段 × 107任务节点的标准化工序地图 + 避坑指南
- **DB 层**：自建 SQLite 数据库，7张表结构化存储（阶段、任务、依赖、避坑、项目档案、项目进度、关联关系）
- **task_code**：新增字段保留Excel层级编号（如 1.3.1）
- **CLI 工具集**：Python脚本，覆盖查询、录入、导出功能

### 1.3 不在范围（这版先不做）
- ❌ Web 应用 / GUI（v1.3再做）
- ❌ 飞书机器人推送 / 自动提醒（v1.4再做）
- ❌ 多用户权限系统 / 登录认证（v1.4再做）
- ❌ 实时协作（DB 用 SQLite 单写者）

### 1.4 验收定义（细化版）

**V1 验收线**：Daniel 团队成员拿到项目目录后：

#### 验收点1：基础查询
```bash
# 能用以下SQL查询并得到正确结果
SELECT COUNT(*) FROM project_profile 
WHERE current_stage_id = (SELECT stage_id FROM stage_map WHERE stage_name = '装修施工');

# 能查询：哪家企业卡点了？卡在哪个任务？
SELECT pp.company_name, sm.stage_name, td.task_name, pg.blocker_note
FROM project_profile pp
JOIN stage_map sm ON pp.current_stage_id = sm.stage_id
LEFT JOIN project_progress pg ON pp.project_id = pg.project_id
LEFT JOIN task_detail td ON pg.task_id = td.task_id
WHERE pg.status = '卡点';
```

#### 验收点2：项目档案录入
```bash
# 能执行命令录入新企业
./add_project.sh --company "测试企业" --type "研发" --building "F6d-1"

# 能在Excel中看到对应行更新
# 能在DB中查询到新记录
```

#### 验收点3：避坑指南验证
```bash
# 能查询某个阶段的所有避坑点
./query_pitfalls.sh --stage "安评"

# 能验证每条避坑卡包含12个必填字段
# 字段：ID、环节、错误做法、合规做法、依据/规范、影响等级、出错指数、触发条件、补救建议、备注、创建日期、来源
```

#### 验收点4：进度导出
```bash
# 能导出所有企业的进度总览
./export_dashboard.sh --output "进度总览.xlsx"

# 输出包含：企业名称、当前阶段、进度百分比、卡点任务、预计完成时间
```

---

## 二、阶段划分与里程碑

| 阶段 | 产出 | 估时 | 依赖 | 验收标准 |
|---|---|---|---|---|
| **M1 内容核对** | 8阶段规范名对照表 + 107任务清单 | 半天 | - | Excel / seed 可验收 |
| **M2 Excel v2** | 5-sheet Excel v2 | 1天 | M1 | 5个sheet结构完整 |
| **M3 DB设计** | 7张表schema + 索引 + 约束 + 触发器 | 半天 | M2 | schema.sql可执行 |
| **M4 数据迁移** | CSV + ETL脚本 + 初始数据 | 半天 | M3 | 数据可查询 |
| **M5 CLI开发** | 10个命令 + 单元测试 | 1天 | M4 | 所有命令可用 |
| **M6 文档编写** | README + API文档 + 用户手册 | 1天 | M5 | 文档完整 |
| **M7 试运行** | 真实数据测试 + 问题修复 | 半天 | M6 | Daniel验收 |

**总计：约 4 天**

---

## 三、数据模型设计

### 3.1 ER关系图

```
┌─────────────┐
│ stage_map   │ (8个阶段)
│ 阶段定义表  │
└──────┬──────┘
       │
       ├─── 1:N ───┬─────────────────┐
       │          │                 │
       │         ↓                  ↓
       │  ┌─────────────┐    ┌──────────────┐
       │  │ task_detail │    │stage_pitfall │
       │  │ 任务定义表  │    │ _ref         │
       │  └──────┬──────┘    │阶段避坑关联  │
       │         │            └──────┬───────┘
       │         │                   │
       │         ├─── 1:N ───┐       │
       │         │            │       │
       │         │           ↓       │
       │         │    ┌──────────┐  │
       │         │    │task_dep  │  │
       │         │    │endency   │  │
       │         │    └─────┬────┘  │
       │         │          │       │
       │         │          ↓       ↓
       │    ┌────────────────────────┐
       │    │ project_progress      │
       │    │ 项目进度跟踪表          │
       │    └───────────┬────────────┘
       │                │
       │         N:1    │
       │                ↓
       │         ┌──────────────┐
       └─────────│project_profile│
                 │ 企业档案表    │
                 └───────────────┘
                                    │
                                    │ 1:N
                                    ↓
                            ┌──────────────┐
                            │pitfall_guide  │
                            │ 避坑指南表    │
                            └───────────────┘
```

### 3.2 完整Schema定义

> **2026-07-21 更新**：`audit_log` 表已移至独立文件 `sql/audit_log.sql`，v1.3 Web 应用使用。

```sql
-- ============================================
-- 表1: stage_map (阶段定义表)
-- ============================================
CREATE TABLE stage_map (
  stage_id          INTEGER PRIMARY KEY AUTOINCREMENT,
  stage_name        TEXT NOT NULL UNIQUE,     -- 原名（唯一）
  standard_name     TEXT,                     -- 联网核查后标准名
  standard_check    TEXT NOT NULL DEFAULT '待核',  -- 一致/部分差异/需更新/待核
  standard_note     TEXT,                     -- 备注
  primary_owner     TEXT NOT NULL,            -- 客户主导/客户委托第三方/园区协调/政府审批
  critical_path     TEXT NOT NULL DEFAULT '🟢',  -- 🔴关键/🟡重要/🟢一般
  default_days      INTEGER DEFAULT 0,
  description       TEXT,                     -- 阶段描述
  sort_order        INTEGER NOT NULL,
  created_at        TEXT DEFAULT (datetime('now')),
  updated_at        TEXT DEFAULT (datetime('now'))
);

-- 索引
CREATE INDEX idx_stage_order ON stage_map(sort_order);
CREATE INDEX idx_stage_critical ON stage_map(critical_path);

-- ============================================
-- 表2: task_detail (任务定义表)
-- ============================================
CREATE TABLE task_detail (
  task_id           INTEGER PRIMARY KEY AUTOINCREMENT,
  stage_id          INTEGER NOT NULL,         -- 所属阶段
  task_name         TEXT NOT NULL,            -- 任务名称
  seq               INTEGER DEFAULT 1,       -- 阶段内序号
  default_days      INTEGER DEFAULT 0,
  critical_path     TEXT NOT NULL DEFAULT '🟢',
  owner             TEXT NOT NULL,            -- 主要责任方
  supervisor        TEXT,                     -- 监督方（如有）
  description       TEXT,                     -- 任务描述
  acceptance_criteria TEXT,                   -- 验收标准
  sort_order        INTEGER NOT NULL,
  created_at        TEXT DEFAULT (datetime('now')),
  updated_at        TEXT DEFAULT (datetime('now')),
  FOREIGN KEY (stage_id) REFERENCES stage_map(stage_id) ON DELETE CASCADE,
  UNIQUE (stage_id, task_name)
);

-- 索引
CREATE INDEX idx_task_stage ON task_detail(stage_id);
CREATE INDEX idx_task_order ON task_detail(stage_id, sort_order);
CREATE INDEX idx_task_critical ON task_detail(critical_path);

-- ============================================
-- 表3: task_dependency (任务依赖关系表)
-- ============================================
CREATE TABLE task_dependency (
  dependency_id    INTEGER PRIMARY KEY AUTOINCREMENT,
  task_id           INTEGER NOT NULL,         -- 依赖方任务
  depends_on        INTEGER NOT NULL,         -- 被依赖任务
  dependency_type   TEXT DEFAULT '完成方可开始',  -- 依赖类型描述
  created_at        TEXT DEFAULT (datetime('now')),
  FOREIGN KEY (task_id) REFERENCES task_detail(task_id) ON DELETE CASCADE,
  FOREIGN KEY (depends_on) REFERENCES task_detail(task_id) ON DELETE CASCADE,
  UNIQUE (task_id, depends_on),
  CHECK (task_id != depends_on)  -- 不能依赖自己
);

-- 索引
CREATE INDEX idx_dep_task ON task_dependency(task_id);
CREATE INDEX idx_dep_depends ON task_dependency(depends_on);

-- ============================================
-- 表4: pitfall_guide (避坑指南表)
-- ============================================
CREATE TABLE pitfall_guide (
  pitfall_id        INTEGER PRIMARY KEY AUTOINCREMENT,
  stage_ref         TEXT,                     -- 关联阶段名（TEXT，允许跨阶段）
  wrong_action      TEXT NOT NULL,            -- 错误做法
  right_action      TEXT NOT NULL,            -- 合规做法
  standard_ref      TEXT,                     -- 依据/规范
  impact_level      TEXT NOT NULL DEFAULT '中',  -- 极高/高/中/低
  error_index       TEXT NOT NULL DEFAULT '中',  -- 极高/高/中/低/待观察
  trigger_condition TEXT,                     -- 触发条件
  remediation       TEXT,                     -- 补救建议
  notes             TEXT,                     -- 备注
  source            TEXT NOT NULL DEFAULT '通用化工合规',  -- 来源
  verified          INTEGER DEFAULT 0,        -- 是否已验证 0/1
  created_at        TEXT DEFAULT (datetime('now')),
  updated_at        TEXT DEFAULT (datetime('now'))
);

-- 索引
CREATE INDEX idx_pitfall_stage ON pitfall_guide(stage_ref);
CREATE INDEX idx_pitfall_impact ON pitfall_guide(impact_level);
CREATE INDEX idx_pitfall_source ON pitfall_guide(source);

-- ============================================
-- 表5: stage_pitfall_ref (阶段避坑关联表)
-- ============================================
CREATE TABLE stage_pitfall_ref (
  stage_id   INTEGER NOT NULL,
  pitfall_id INTEGER NOT NULL,
  ref_type   TEXT DEFAULT '常见',           -- 常见/偶尔/罕见
  created_at TEXT DEFAULT (datetime('now')),
  PRIMARY KEY (stage_id, pitfall_id),
  FOREIGN KEY (stage_id) REFERENCES stage_map(stage_id) ON DELETE CASCADE,
  FOREIGN KEY (pitfall_id) REFERENCES pitfall_guide(pitfall_id) ON DELETE CASCADE
);

-- 索引
CREATE INDEX idx_sp_stage ON stage_pitfall_ref(stage_id);
CREATE INDEX idx_sp_pitfall ON stage_pitfall_ref(pitfall_id);

-- ============================================
-- 表6: project_profile (企业档案表)
-- ============================================
CREATE TABLE project_profile (
  project_id        INTEGER PRIMARY KEY AUTOINCREMENT,
  company_name      TEXT NOT NULL UNIQUE,
  short_name        TEXT,
  -- 公司信息
  credit_code       TEXT UNIQUE,             -- 统一社会信用代码
  registered_cap    DECIMAL(15,2),           -- 注册资本
  founded_date      DATE,                    -- 成立日期
  shareholder       TEXT,                    -- 股东结构
  industry          TEXT,                    -- 所属行业
  is_high_tech      INTEGER DEFAULT 0,       -- 是否高新 0/1
  is_specialized     INTEGER DEFAULT 0,       -- 是否专精特新 0/1
  patent_count      INTEGER DEFAULT 0,
  software_count    INTEGER DEFAULT 0,
  -- 团队信息（JSON）
  team_json         TEXT,
  -- 业务信息
  business_type     TEXT,                    -- 研发/中试/小规模生产
  tech_route        TEXT,
  product_target    TEXT,
  market_position   TEXT,
  -- 物料与产品（JSON）
  materials_json    TEXT,
  -- 公用工程需求（JSON）
  utility_json      TEXT,
  -- 项目先进性
  innovation_desc   TEXT,
  award_info        TEXT,
  partner_info      TEXT,
  -- 项目投资
  total_invest      DECIMAL(15,2),
  fixed_asset_inv   DECIMAL(15,2),
  equipment_inv     DECIMAL(15,2),
  rd_invest         DECIMAL(15,2),
  funding_source    TEXT,
  expected_output   DECIMAL(15,2),
  expected_tax      DECIMAL(15,2),
  irr               DECIMAL(5,2),
  -- 选址与建筑
  building          TEXT,
  floor             TEXT,
  area_m2           DECIMAL(10,2),
  building_class    TEXT,                    -- 甲/乙/丙类
  special_zone      TEXT,
  -- 当前阶段 / 进度
  current_stage_id  INTEGER,
  project_status    TEXT NOT NULL DEFAULT '未开始',  -- 未开始/进行中/卡点/已完成/已退园
  progress_percent  INTEGER DEFAULT 0,       -- 进度百分比 0-100
  estimated_complete_date DATE,             -- 预计完成日期
  actual_complete_date  DATE,               -- 实际完成日期
  notes             TEXT,
  created_at        TEXT DEFAULT (datetime('now')),
  updated_at        TEXT DEFAULT (datetime('now')),
  FOREIGN KEY (current_stage_id) REFERENCES stage_map(stage_id)
);

-- 索引
CREATE INDEX idx_project_status ON project_profile(project_status);
CREATE INDEX idx_project_stage ON project_profile(current_stage_id);
CREATE INDEX idx_project_building ON project_profile(building);
CREATE INDEX idx_project_type ON project_profile(business_type);

-- ============================================
-- 表7: project_progress (项目进度跟踪表)
-- ============================================
CREATE TABLE project_progress (
  progress_id   INTEGER PRIMARY KEY AUTOINCREMENT,
  project_id    INTEGER NOT NULL,
  task_id       INTEGER NOT NULL,
  status        TEXT NOT NULL DEFAULT '待开始',  -- 待开始/进行中/已完成/已跳过/卡点
  priority      TEXT DEFAULT '🟢',           -- 🔴高/🟡中/🟢低
  assigned_to   TEXT,
  started_at    TEXT,
  completed_at  TEXT,
  blocker_note  TEXT,                        -- 卡点说明
  resolution_note TEXT,                      -- 解决方案
  actual_days   INTEGER,                     -- 实际耗时
  notes         TEXT,
  created_at    TEXT DEFAULT (datetime('now')),
  updated_at    TEXT DEFAULT (datetime('now')),
  FOREIGN KEY (project_id) REFERENCES project_profile(project_id) ON DELETE CASCADE,
  FOREIGN KEY (task_id) REFERENCES task_detail(task_id) ON DELETE CASCADE,
  UNIQUE (project_id, task_id)
);

-- 索引
CREATE INDEX idx_progress_project ON project_progress(project_id);
CREATE INDEX idx_progress_task ON project_progress(task_id);
CREATE INDEX idx_progress_status ON project_progress(status);
CREATE INDEX idx_progress_priority ON project_progress(priority);

-- ============================================
-- 触发器：自动更新 updated_at
-- ============================================
CREATE TRIGGER update_stage_timestamp 
AFTER UPDATE ON stage_map
BEGIN
  UPDATE stage_map SET updated_at = datetime('now') WHERE stage_id = NEW.stage_id;
END;

CREATE TRIGGER update_task_timestamp 
AFTER UPDATE ON task_detail
BEGIN
  UPDATE task_detail SET updated_at = datetime('now') WHERE task_id = NEW.task_id;
END;

CREATE TRIGGER update_project_timestamp 
AFTER UPDATE ON project_profile
BEGIN
  UPDATE project_profile SET updated_at = datetime('now') WHERE project_id = NEW.project_id;
END;

CREATE TRIGGER update_progress_timestamp 
AFTER UPDATE ON project_progress
BEGIN
  UPDATE project_progress SET updated_at = datetime('now') WHERE progress_id = NEW.progress_id;
END;

CREATE TRIGGER update_pitfall_timestamp 
AFTER UPDATE ON pitfall_guide
BEGIN
  UPDATE pitfall_guide SET updated_at = datetime('now') WHERE pitfall_id = NEW.pitfall_id;
END;
```

### 3.3 数据类型规范

| 字段类型 | 用途 | 示例 |
|---------|------|------|
| INTEGER | ID、数量、布尔(0/1) | stage_id, patent_count, is_high_tech |
| DECIMAL(m,n) | 金额、比例 | total_invest DECIMAL(15,2), irr DECIMAL(5,2) |
| DATE | 日期 | founded_date, estimated_complete_date |
| TEXT | 字符串、JSON | company_name, team_json |
| CHECK | 约束 | progress_percent 0-100 |

---

## 四、CLI工具规格说明

> ⚠️ **2026-07-21 更新**：Shell 脚本（`.sh`）已全部替换为 **Python 脚本**（`.py`），Windows 兼容。
> 详见 [CLAUDE.md](CLAUDE.md) 中的「Development Commands」章节。

### 4.1 工具清单

| 序号 | 命令 | 功能 | 输入 | 输出 |
|------|------|------|------|------|
| 1 | `python scripts/init_db.py` | 初始化数据库 | `--db-path`, `--excel` | 建库+导入 |
| 2 | `python scripts/import_excel.py` | Excel→DB导入 | `--db`, `--excel` | 导入统计 |
| 3 | `python scripts/verify_phase_a.py` | 数据校验 | - | 校验报告 |

### 4.2 详细规格

### 4.2 init_db.py（数据库初始化）

```bash
# 基本用法：初始化数据库（幂等，自动备份）
python scripts/init_db.py

# 指定数据库路径
python scripts/init_db.py --db-path data/test.db

# 初始化后导入 Excel 数据
python scripts/init_db.py --excel 工作阶段划分.xlsx
```

### 4.3 import_excel.py（Excel 导入）

```bash
# 导入 Excel 数据到现有数据库
python scripts/import_excel.py --db data/innogreen_pmo.db --excel 工作阶段划分.xlsx
```

### 4.4 verify_phase_a.py（数据校验）

```bash
# 运行 Phase A 门禁校验
python scripts/verify_phase_a.py
```

### 4.5 Web API（v1.3 新增）

v1.3 Web 应用提供 REST API，详见 [development_plan_v1.3_web_app.md](development_plan_v1.3_web_app.md)。

---

## 五、Excel v2 结构设计

### 5.1 Sheet结构

| Sheet名称 | 用途 | 行数 | 说明 |
|-----------|------|------|------|
| Sheet1 | 阶段定义 | 18 | 主阶段地图 |
| Sheet2 | 任务明细 | 92 | 任务-子步骤清单 |
| Sheet3 | 避坑指南 | 20+ | 避坑卡片 |
| Sheet4 | 企业档案 | 17+ | 企业项目档案 |
| Sheet5 | 任务依赖 | 30+ | 任务依赖关系 |

### 5.2 Sheet1「阶段定义」

| 列名 | 类型 | 必填 | 说明 |
|------|------|------|------|
| stage_id | INTEGER | Y | 阶段ID |
| stage_name | TEXT | Y | 阶段名称 |
| standard_name | TEXT | N | 规范标准名 |
| standard_check | TEXT | Y | 一致性状态 |
| standard_note | TEXT | N | 备注 |
| primary_owner | TEXT | Y | 主要责任方 |
| critical_path | TEXT | Y | 关键路径 |
| default_days | INTEGER | Y | 默认工期 |
| description | TEXT | N | 阶段描述 |
| sort_order | INTEGER | Y | 排序 |

### 5.3 Sheet2「任务明细」

| 列名 | 类型 | 必填 | 说明 |
|------|------|------|------|
| task_id | INTEGER | Y | 任务ID |
| stage_id | INTEGER | Y | 所属阶段ID |
| task_name | TEXT | Y | 任务名称 |
| seq | INTEGER | Y | 序号 |
| default_days | INTEGER | Y | 默认工期 |
| critical_path | TEXT | Y | 关键路径 |
| owner | TEXT | Y | 责任方 |
| supervisor | TEXT | N | 监督方 |
| description | TEXT | N | 任务描述 |
| acceptance_criteria | TEXT | N | 验收标准 |
| sort_order | INTEGER | Y | 排序 |

### 5.4 Sheet3「避坑指南」

| 列名 | 类型 | 必填 | 说明 |
|------|------|------|------|
| pitfall_id | INTEGER | Y | 避坑ID |
| stage_ref | TEXT | Y | 关联阶段 |
| wrong_action | TEXT | Y | 错误做法 |
| right_action | TEXT | Y | 合规做法 |
| standard_ref | TEXT | N | 依据/规范 |
| impact_level | TEXT | Y | 影响等级 |
| error_index | TEXT | Y | 出错指数 |
| trigger_condition | TEXT | N | 触发条件 |
| remediation | TEXT | N | 补救建议 |
| notes | TEXT | N | 备注 |
| source | TEXT | Y | 来源 |
| verified | INTEGER | Y | 是否验证(0/1) |

### 5.5 Sheet4「企业档案」

同project_profile表结构

### 5.6 Sheet5「任务依赖」

| 列名 | 类型 | 必填 | 说明 |
|------|------|------|------|
| task_id | INTEGER | Y | 依赖方任务ID |
| depends_on | INTEGER | Y | 被依赖任务ID |
| dependency_type | TEXT | N | 依赖类型描述 |

---

## 六、初始化数据规格

### 6.1 数据来源确认

| 数据类型 | 数量 | 来源 | 状态 |
|---------|------|------|------|
| 阶段定义 | 18条 | 工作阶段划分.xlsx | ✅已确认 |
| 任务明细 | 92条 | 工作阶段划分.xlsx | ✅已确认 |
| 避坑指南 | 0条（结构定义） | - | ✅v1只定义结构 |
| 任务依赖 | 30+条 | 流程图PDF/PNG | ✅已提取 |
| 企业档案 | 0条 | - | ✅v1不录入（企业已运行） |

### 6.2 避坑指南（v1只定义结构）

**v1.0策略**：只定义12字段结构，不录入具体内容。

**12字段结构**：
1. pitfall_id (PK)
2. stage_ref (关联阶段)
3. wrong_action (错误做法)
4. right_action (合规做法)
5. standard_ref (依据/规范)
6. impact_level (影响等级: 极高/高/中/低)
7. error_index (出错指数: 极高/高/中/低/待观察)
8. trigger_condition (触发条件)
9. remediation (补救建议)
10. notes (备注)
11. source (来源)
12. verified (是否验证: 0/1)

**后续版本**：v1.1开始由Daniel基于历史经验录入内容。

### 6.3 任务依赖关系（从流程图提取）

基于《创新中心科创项目全生命周期流程图》，提取核心依赖关系：

```sql
-- task_dependencies (30+条核心依赖)
-- 格式：(前置任务) → (后置任务)

-- ============ 阶段2：准入与信息报送 ============
-- 厂房移交相关依赖
INSERT INTO task_dependency (task_id, depends_on, dependency_type) VALUES
-- 移交场地准备 → 移交材料准备
(59, 58, '完成方可开始'),
-- 移交材料准备 → 正式移交
(60, 59, '完成方可开始');

-- 租赁合同相关依赖
-- 协议内容确认 → 用印流程
(57, 56, '完成方可开始'),
-- 用印流程 → 厂房移交
(56, 60, '完成方可开始');

-- ============ 阶段5-7：三评（可并行）============
-- 安评：安全预评价报告 → 内部专家审批
(14, 13, '完成方可开始'),
-- 安评：内部专家审批 → 安全设施设计专篇编制
(14, 15, '完成方可开始'),
-- 安评：安全设施设计专篇 → 内部专家审批
(16, 15, '完成方可开始'),
-- 安评：内部专家审批 → 项目安全条件论证
(17, 16, '完成方可开始');

-- 环评：报告编制定稿 → 内部审批
(19, 18, '完成方可开始'),
-- 环评：内部审批 → 市局公示、审批
(20, 19, '完成方可开始');

-- 卫评：职业卫生评价报告编制 → 内部审批
(22, 21, '完成方可开始'),
-- 卫评：内部审批 → 职业卫生设计专篇编制
(22, 23, '完成方可开始'),
-- 卫评：职业卫生设计专篇编制 → 设计专篇备案
(24, 23, '完成方可开始');

-- ============ 阶段10：设计审查 ============
-- 三评完成后才能进行设计审查
(32, 17, '三评完成后'),  -- 施工图审图依赖安评完成
(32, 20, '环评完成后'),  -- 施工图审图依赖环评完成
(32, 24, '卫评完成后'),  -- 施工图审图依赖卫评完成

-- ============ 阶段11：取证 ============
-- 设计审查完成后才能取证
(35, 31, '审图完成后'),   -- 施工许可证依赖施工图审图
(35, 32, '消防审图完成后'), -- 施工许可证依赖消防设计审查
(35, 33, '防雷审图完成后'), -- 施工许可证依赖防雷设计审查

-- ============ 阶段13：装修施工 ============
-- 取证完成后才能施工
(39, 34, '许可证到位后'),  -- 机电设备安装依赖施工许可证
(39, 35, '平台备案后');    -- 机电设备安装依赖安全管控平台

-- 施工前准备 → 机电设备安装
(39, 37, '完成方可开始'),
(39, 38, '完成方可开始');

-- 机电设备安装 → 设备及系统调试
(40, 39, '完成方可开始');

-- ============ 阶段15：工程验收 ============
-- 竣工验收 → 各专项验收
(43, 42, '完成方可开始'),  -- 消防验收依赖竣工验收会
(44, 42, '完成方可开始'),  -- 防雷验收依赖竣工验收会
(45, 42, '完成方可开始');  -- 综合竣工验收依赖竣工验收会

-- ============ 阶段16：试生产 ============
-- 试生产方案编制定稿 → 内部专家评审
(47, 46, '完成方可开始'),
-- 内部专家评审 → 项目试生产安全评审
(48, 47, '完成方可开始'),
-- 项目试生产安全评审 → 启动项目试生产
(49, 48, '完成方可开始');

-- ============ 阶段17：三同时验收 ============
-- 试生产完成后才能三同时验收
(51, 49, '试生产完成后'),
(52, 49, '试生产完成后'),
(53, 49, '试生产完成后');

-- ============ 阶段18：正式投用 ============
-- 三同时验收完成后才能正式投用
(54, 51, '安设验收通过后'),
(54, 52, '环保验收通过后'),
(54, 53, '卫评验收通过后');

-- ============ 跨阶段关键路径依赖 ============
-- 1. 项目准入评估完成 → 才能签订租赁合同
-- 发展公司项目预准入评估(3) → 管委会项目准入评估(4)
INSERT INTO task_dependency (task_id, depends_on, dependency_type) VALUES
(4, 3, '通过后方可'),
-- 管委会评估通过 → 租赁合同
(5, 4, '通过后方可'),
-- 租赁合同 → 厂房移交
(6, 5, '签订后');

-- 2. 三评完成 → 设计审查
-- 项目安全条件论证(17) → 施工图设计
(12, 17, '完成后'),
-- 环评审批完成 → 施工图设计
(12, 20, '完成后');

-- 3. 设计审查完成 → 取证
-- 消防设计审查通过 → 消防验收
(43, 32, '设计审查完成后');

-- 4. 施工完成 → 竣工验收
-- 装修施工完成 → 竣工验收会
(42, 40, '施工完成后');

-- 5. 三同时完成 → 正式投用
-- 所有专项验收通过 → 正式投用
(54, 51, '全部验收通过后');
```

**依赖关系统计**：
- 总依赖关系：约40条
- 关键路径依赖：15条（🔴）
- 一般依赖：25条（🟡）

**关键路径概览**：
```
项目准入 → 厂房移交 → 三评(安评/环评/卫评) → 设计审查 
→ 取证 → 装修施工 → 竣工验收 → 试生产 → 三同时验收 → 正式投用
```

### 6.4 seed.sql文件结构

```sql
-- seed.sql 内容结构

-- 1. 阶段定义（18条）
INSERT INTO stage_map (stage_id, stage_name, primary_owner, critical_path, default_days, sort_order) VALUES
(1, '项目准入情况', '园区协调', '🟢', 5, 1),
(2, '准入与信息报送', '客户主导', '🔴', 10, 2),
-- ... 共18条

-- 2. 任务明细（92条）
INSERT INTO task_detail (stage_id, task_name, seq, default_days, critical_path, owner, sort_order) VALUES
-- 见 0.3 节完整任务清单

-- 3. 避坑指南（v1不录入具体内容）
-- v1.0只定义表结构，无初始数据

-- 4. 任务依赖（40条）
-- 见 6.3 节完整SQL

-- 5. 企业档案（v1不录入）
-- v1.0无初始企业数据
```

---

## 七、目录结构

```
innogreen-pmo/
├── README.md                           # 快速开始指南
├── development_plan_v1.2.md            # 本文件
├── CHANGELOG.md                        # 变更日志
├── data/
│   ├── innogreen_pmo.db               # SQLite主库（运行时生成）
│   ├── innogreen_pmo.backup.db        # 备份文件
│   └── csv/                           # CSV中间态
│       ├── stages.csv
│       ├── tasks.csv
│       ├── pitfalls.csv
│       └── projects.csv
├── excel/
│   ├── 工作阶段划分_v2.xlsx            # 5-sheet升级版
│   └── 工作阶段划分_v1.xlsx            # 原版归档
├── reference/                          # 背景资料
│   ├── 创新中心简介20260227.docx
│   ├── 创新中心科创项目全生命周期流程图-20251230.pdf
│   ├── 工作阶段划分.xlsx                # 原始数据
│   └── Proxxima.md                    # 参考案例（客户进度计划）
├── sql/
│   ├── schema.sql                      # 表定义（7张表）
│   ├── seed.sql                        # 初始化数据
│   ├── indexes.sql                     # 索引定义
│   ├── triggers.sql                    # 触发器
│   └── queries.sql                     # 常用查询模板
├── scripts/
│   ├── init_db.sh                      # 一键初始化
│   ├── backup_db.sh                    # 备份数据库
│   ├── query_*.sh                      # 查询命令（5个）
│   ├── add_*.sh                        # 录入命令（2个）
│   ├── update_progress.sh              # 进度更新
│   └── export_*.sh                     # 导出命令（2个）
├── lib/
│   ├── db_utils.sh                     # 数据库操作函数库
│   ├── validate.sh                     # 验证函数库
│   └── format.sh                       # 格式化输出函数库
├── tests/
│   ├── test_schema.sh                  # Schema测试
│   ├── test_cli.sh                     # CLI测试
│   └── test_data/                      # 测试数据
└── docs/
    ├── 阶段地图说明.md
    ├── 避坑指南编写指南.md
    ├── 日常使用手册.md
    ├── CLI命令参考.md
    └── 数据库设计文档.md
```

---

## 八、风险与决策点

### 8.1 已知风险

| # | 风险 | 等级 | 应对 |
|---|------|------|------|
| R1 | 避坑指南20条内容不准确 | 高 | 明确标记来源和验证状态，Daniel审核后录入 |
| R2 | 任务依赖关系复杂，难以梳理 | 中 | v1先只建立核心依赖，后续迭代完善 |
| R3 | 企业档案字段过多，录入困难 | 中 | v1只录必填字段，选填字段后续补 |
| R4 | CLI工具在不同平台兼容性 | 中 | 使用bash，避免平台特定命令 |
| R5 | SQLite在Windows下路径问题 | 低 | 使用相对路径，提供初始化脚本 |

### 8.2 已确认决策点

| # | 决策点 | 确认结果 | 说明 |
|---|--------|----------|------|
| D1 | 避坑指南v1录入 | ✅不录入具体内容 | 只定义12字段结构，v1.1开始录入 |
| D2 | 任务依赖关系 | ✅从流程图提取 | 已从PDF/PNG提取40条依赖 |
| D3 | 17家企业录入 | ✅v1不录入 | 企业已运行，v1.1再补 |
| D4 | 用户验证机制 | ✅v1不需要 | v3再考虑 |

---

## 九、交付节奏

分 **4 轮交付**，每轮 Daniel 拍板再继续：

| 轮次 | 交付内容 | 预估 | 状态 |
|---|---|---|---|
| **第1轮** | M1：阶段/任务清单 | 半天 | ⏳待启动 |
| **第2轮** | M2：Excel v2 + M3：DB设计 | 1.5天 | ⏳待启动 |
| **第3轮** | M4：数据迁移 + M5：CLI开发 | 1.5天 | ⏳待启动 |
| **第4轮** | M6：文档 + M7：试运行 | 1.5天 | ⏳待启动 |

**每轮结束主动停下报告，等 Daniel 说"继续"或者"1"。**

---

## 十、变更记录

| 版本 | 日期 | 变更 |
|---|---|---|
| v1.0 | 2026-07-21 | 初版归档 |
| v1.1 | 2026-07-21 | 新增背景资料章节 |
| v1.2 | 2026-07-21 | **重大重构**：数据模型7张表、CLI完整规格、验收标准细化 |
| v1.2 补充 | 2026-07-21 | 新增 Phase A 门禁条件（v1.3 Web 前置）；脱敏数据约定 |

---

## 十一、验收测试用例

### 11.1 基础功能测试

```bash
# T1: 查询所有阶段
./query_stages.sh
# 预期：输出18个阶段的Markdown表格
# 验证：stage_id连续、critical_path合法

# T2: 查询关键阶段
./query_stages.sh --critical 🔴
# 预期：只输出critical_path=🔴的阶段
# 验证：结果数量符合预期

# T3: 查询卡点企业
./query_projects.sh --status 卡点
# 预期：输出所有卡点企业
# 验证：包含blocker_note

# T4: 录入新企业
./add_project.sh --company "测试企业" ...
# 预期：返回project_id
# 验证：可在DB中查询到

# T5: 更新项目进度
./update_progress.sh --project-id 1 --task-id 5 --status 已完成
# 预期：输出success
# 验证：completed_at已设置
```

### 11.2 数据完整性测试

```sql
-- T6: 外键约束测试
INSERT INTO project_profile (current_stage_id) VALUES (999);
-- 预期：FOREIGN KEY约束失败

-- T7: 唯一性约束测试
INSERT INTO stage_map (stage_name) VALUES ('项目准入情况');
-- 预期：UNIQUE约束失败

-- T8: 触发器测试
UPDATE stage_map SET stage_name = '测试' WHERE stage_id = 1;
-- 验证：updated_at已更新
```

### 11.3 CLI错误处理测试

```bash
# T9: 参数验证
./query_projects.sh --invalid-param
# 预期：输出错误信息，退出码非0

# T10: 记录不存在
./query_projects.sh --company "不存在"
# 预期：输出"未找到"信息
```

---

## 十二、下一步行动

### 12.1 已确认决策

| 决策点 | 确认结果 | 说明 |
|--------|----------|------|
| 避坑指南v1 | ✅已录入4条样例 | 试点数据已入库 |
| 任务依赖关系 | ✅已从流程图提取 | 64条依赖关系已定义 |
| 17家企业v1 | ✅录入3家脱敏样例 | ENT-01/02/03 |
| task_code字段 | ✅已增加 | 保留Excel层级编号 |

### 12.2 Phase A 门禁（已通过 ✅）

**验收时间：2026-07-21**

| # | 条件 | 验证结果 |
|---|------|----------|
| A1 | schema.sql 可一键建库（7表 + 索引 + 触发器） | ✅ 7表创建成功 |
| A2 | 8阶段 + 107任务已导入 | ✅ 阶段8/任务107 |
| A3 | 核心任务依赖已导入且方向校验通过 | ✅ 69条依赖，0自环 |
| A4 | ≥2家脱敏企业 + 进度（含≥1卡点） | ✅ 3家，2卡点 |
| A5 | 避坑结构就绪；内容可0或≥5条试点 | ✅ 4条避坑 |
| A6 | Windows可运行（Python CLI优先） | ✅ 通过 |

**脱敏约定**：
- 对外展示统一用编号（ENT-01…）；真名对照表**不进Git**
- 对照文件：`data/private/name_map.local.csv`（需创建并加入 .gitignore）
- 进度/阶段/卡点保持真实业务语义，只抹去可识别主体

**Phase A 验收 SQL**：

```sql
-- A2: 验证数据导入
SELECT COUNT(*) FROM stage_map;          -- 应返回 8
SELECT COUNT(*) FROM task_detail;        -- 应返回 107
SELECT COUNT(*) FROM task_dependency;   -- 应返回 69

-- A3: 验证依赖无自环
SELECT COUNT(*) FROM task_dependency WHERE task_id = depends_on;  -- 应返回 0

-- A4: 验证样例数据
SELECT company_name, project_status, progress_percent FROM project_profile;
-- 应返回 ENT-01/ENT-02/ENT-03

-- A4: 验证卡点
SELECT p.company_name, t.task_name, pg.blocker_note
FROM project_progress pg
JOIN project_profile p ON pg.project_id = p.project_id
JOIN task_detail t ON pg.task_id = t.task_id
WHERE pg.status = '卡点';
-- 应返回 2 条卡点记录

-- A5: 验证避坑结构
SELECT COUNT(*) FROM pitfall_guide;  -- 应返回 4
```

### 12.3 下一步

**Phase A 已通过！** 可以开始 v1.3 Web 开发。

👉 查看 [development_plan_v1.3_web_app.md](development_plan_v1.3_web_app.md)

---

**v1.2 版本状态：✅ 已完成**

交付物：
- ✅ 数据模型完整（7张表，含 task_code 字段）
- ✅ 初始化脚本（Python，Windows兼容）
- ✅ 8阶段 × 107任务已导入
- ✅ 69条任务依赖关系
- ✅ 3家脱敏样例企业 + 2卡点（阶段/任务已对齐）
- ✅ project_code 字段 + 可重复 init_db
- ✅ 4条避坑指南样例
- ✅ audit_log 表结构（v1.3 Web 前置，`sql/audit_log.sql`）
