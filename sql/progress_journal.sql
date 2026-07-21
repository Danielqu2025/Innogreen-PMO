-- ============================================
-- progress_journal：项目任务周进展日志（v1.3+）
-- 用途：承接 Projects.xlsx 中按周叙述列，保留时间线，不覆盖当前态
-- 与 project_progress 关系：
--   project_progress = 任务「当前快照」（状态/计划实际日期/第三方）
--   progress_journal = 任务「历史叙事」（每周一条，可追加）
-- 日期：2026-07-22
-- ============================================

CREATE TABLE IF NOT EXISTS progress_journal (
  journal_id     INTEGER PRIMARY KEY AUTOINCREMENT,
  project_id     INTEGER NOT NULL,
  task_id        INTEGER,                     -- NULL = 项目级周记（非任务绑定）
  week_start     TEXT NOT NULL,               -- ISO 日期 YYYY-MM-DD（该周周一或列起始日）
  week_label     TEXT,                        -- 原始列头，如「每周工作进展（3.9-3.15）」
  note           TEXT NOT NULL,               -- 周进展正文（Excel 单元格原文）
  source         TEXT NOT NULL DEFAULT 'web', -- web / excel_import / api
  actor          TEXT,                        -- 写入人 username（导入可为 system/import）
  created_at     TEXT DEFAULT (datetime('now')),
  FOREIGN KEY (project_id) REFERENCES project_profile(project_id) ON DELETE CASCADE,
  FOREIGN KEY (task_id) REFERENCES task_detail(task_id) ON DELETE SET NULL
);

-- 同一项目+任务+周+相同正文去重（导入幂等）
CREATE UNIQUE INDEX IF NOT EXISTS uq_journal_dedupe
  ON progress_journal(project_id, IFNULL(task_id, -1), week_start, note);

CREATE INDEX IF NOT EXISTS idx_journal_project_week
  ON progress_journal(project_id, week_start DESC);

CREATE INDEX IF NOT EXISTS idx_journal_task
  ON progress_journal(task_id, week_start DESC);

CREATE INDEX IF NOT EXISTS idx_journal_project_task
  ON progress_journal(project_id, task_id, week_start DESC);
