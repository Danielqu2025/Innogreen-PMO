-- ============================================
-- 触发器：自动更新 updated_at
-- ============================================

-- stage_map 更新触发器
CREATE TRIGGER IF NOT EXISTS update_stage_timestamp
AFTER UPDATE ON stage_map
WHEN NEW.updated_at = OLD.updated_at
BEGIN
  UPDATE stage_map SET updated_at = datetime('now') WHERE stage_id = NEW.stage_id;
END;

-- task_detail 更新触发器
CREATE TRIGGER IF NOT EXISTS update_task_timestamp
AFTER UPDATE ON task_detail
WHEN NEW.updated_at = OLD.updated_at
BEGIN
  UPDATE task_detail SET updated_at = datetime('now') WHERE task_id = NEW.task_id;
END;

-- project_profile 更新触发器
CREATE TRIGGER IF NOT EXISTS update_project_timestamp
AFTER UPDATE ON project_profile
WHEN NEW.updated_at = OLD.updated_at
BEGIN
  UPDATE project_profile SET updated_at = datetime('now') WHERE project_id = NEW.project_id;
END;

-- project_progress 更新触发器
CREATE TRIGGER IF NOT EXISTS update_progress_timestamp
AFTER UPDATE ON project_progress
WHEN NEW.updated_at = OLD.updated_at
BEGIN
  UPDATE project_progress SET updated_at = datetime('now') WHERE progress_id = NEW.progress_id;
END;

-- pitfall_guide 更新触发器
CREATE TRIGGER IF NOT EXISTS update_pitfall_timestamp
AFTER UPDATE ON pitfall_guide
WHEN NEW.updated_at = OLD.updated_at
BEGIN
  UPDATE pitfall_guide SET updated_at = datetime('now') WHERE pitfall_id = NEW.pitfall_id;
END;

-- ============================================
-- audit_log 插入触发器（v1.3 新增）
-- 用于自动记录数据变更
-- 注意：由应用层显式插入更灵活，此处仅记录结构
-- ============================================
