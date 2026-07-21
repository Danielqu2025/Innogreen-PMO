-- ============================================
-- Innogreen PMO 数据库 Schema v1.2
-- 7 张表：阶段、任务、依赖、避坑、阶段-避坑关联、企业档案、进度
-- ============================================

-- ============================================
-- 表1: stage_map (阶段定义表)
-- ============================================
CREATE TABLE IF NOT EXISTS stage_map (
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

-- ============================================
-- 表2: task_detail (任务定义表)
-- ============================================
CREATE TABLE IF NOT EXISTS task_detail (
  task_id           INTEGER PRIMARY KEY AUTOINCREMENT,
  stage_id          INTEGER NOT NULL,         -- 所属阶段
  task_name         TEXT NOT NULL,            -- 任务名称
  task_code         TEXT,                     -- Excel原始编号 (如 1.3.1)
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

-- ============================================
-- 表3: task_dependency (任务依赖关系表)
-- ============================================
CREATE TABLE IF NOT EXISTS task_dependency (
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

-- ============================================
-- 表4: pitfall_guide (避坑指南表)
-- ============================================
CREATE TABLE IF NOT EXISTS pitfall_guide (
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

-- ============================================
-- 表5: stage_pitfall_ref (阶段避坑关联表)
-- ============================================
CREATE TABLE IF NOT EXISTS stage_pitfall_ref (
  stage_id   INTEGER NOT NULL,
  pitfall_id INTEGER NOT NULL,
  ref_type   TEXT DEFAULT '常见',           -- 常见/偶尔/罕见
  created_at TEXT DEFAULT (datetime('now')),
  PRIMARY KEY (stage_id, pitfall_id),
  FOREIGN KEY (stage_id) REFERENCES stage_map(stage_id) ON DELETE CASCADE,
  FOREIGN KEY (pitfall_id) REFERENCES pitfall_guide(pitfall_id) ON DELETE CASCADE
);

-- ============================================
-- 表6: project_profile (企业档案表)
-- ============================================
CREATE TABLE IF NOT EXISTS project_profile (
  project_id        INTEGER PRIMARY KEY AUTOINCREMENT,
  project_code      TEXT NOT NULL UNIQUE,    -- 对外脱敏编号 ENT-01（v1.3）
  company_name      TEXT NOT NULL UNIQUE,
  short_name        TEXT,
  -- 公司信息
  credit_code       TEXT UNIQUE,             -- 统一社会信用代码
  registered_cap    DECIMAL(15,2),           -- 注册资本
  founded_date      DATE,                    -- 成立日期
  shareholder       TEXT,                    -- 股东结构
  industry          TEXT,                    -- 所属行业
  is_high_tech      INTEGER DEFAULT 0,       -- 是否高新 0/1
  is_specialized    INTEGER DEFAULT 0,       -- 是否专精特新 0/1
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

-- ============================================
-- 表7: project_progress (项目进度跟踪表)
-- ============================================
CREATE TABLE IF NOT EXISTS project_progress (
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
