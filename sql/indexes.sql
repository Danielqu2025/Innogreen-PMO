-- ============================================
-- 索引定义
-- ============================================

-- stage_map 索引
CREATE INDEX IF NOT EXISTS idx_stage_order ON stage_map(sort_order);
CREATE INDEX IF NOT EXISTS idx_stage_critical ON stage_map(critical_path);

-- task_detail 索引
CREATE INDEX IF NOT EXISTS idx_task_stage ON task_detail(stage_id);
CREATE INDEX IF NOT EXISTS idx_task_order ON task_detail(stage_id, sort_order);
CREATE INDEX IF NOT EXISTS idx_task_critical ON task_detail(critical_path);

-- task_dependency 索引
CREATE INDEX IF NOT EXISTS idx_dep_task ON task_dependency(task_id);
CREATE INDEX IF NOT EXISTS idx_dep_depends ON task_dependency(depends_on);

-- pitfall_guide 索引
CREATE INDEX IF NOT EXISTS idx_pitfall_stage ON pitfall_guide(stage_ref);
CREATE INDEX IF NOT EXISTS idx_pitfall_impact ON pitfall_guide(impact_level);
CREATE INDEX IF NOT EXISTS idx_pitfall_source ON pitfall_guide(source);

-- stage_pitfall_ref 索引
CREATE INDEX IF NOT EXISTS idx_sp_stage ON stage_pitfall_ref(stage_id);
CREATE INDEX IF NOT EXISTS idx_sp_pitfall ON stage_pitfall_ref(pitfall_id);

-- project_profile 索引
CREATE INDEX IF NOT EXISTS idx_project_status ON project_profile(project_status);
CREATE INDEX IF NOT EXISTS idx_project_stage ON project_profile(current_stage_id);
CREATE INDEX IF NOT EXISTS idx_project_building ON project_profile(building);
CREATE INDEX IF NOT EXISTS idx_project_type ON project_profile(business_type);
CREATE UNIQUE INDEX IF NOT EXISTS idx_project_code ON project_profile(project_code);

-- project_progress 索引
CREATE INDEX IF NOT EXISTS idx_progress_project ON project_progress(project_id);
CREATE INDEX IF NOT EXISTS idx_progress_task ON project_progress(task_id);
CREATE INDEX IF NOT EXISTS idx_progress_status ON project_progress(status);
CREATE INDEX IF NOT EXISTS idx_progress_priority ON project_progress(priority);

-- audit_log 索引（v1.3 新增）
CREATE INDEX IF NOT EXISTS idx_audit_actor ON audit_log(actor);
CREATE INDEX IF NOT EXISTS idx_audit_resource ON audit_log(resource, resource_id);
CREATE INDEX IF NOT EXISTS idx_audit_action ON audit_log(action);
CREATE INDEX IF NOT EXISTS idx_audit_time ON audit_log(created_at DESC);
