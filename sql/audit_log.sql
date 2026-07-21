-- ============================================
-- Innogreen PMO 审计日志表 v1.3
-- 用途：记录所有写操作，便于运营追溯和合规审计
-- 日期：2026-07-21
-- ============================================

-- ============================================
-- audit_log (审计日志表)
-- ============================================
CREATE TABLE IF NOT EXISTS audit_log (
  audit_id       INTEGER PRIMARY KEY AUTOINCREMENT,
  actor          TEXT NOT NULL,              -- 操作人（token别名或user_id）
  action         TEXT NOT NULL,             -- 操作类型：CREATE/UPDATE/DELETE
  resource       TEXT NOT NULL,              -- 资源类型：projects/tasks/pitfalls/progress/stages
  resource_id    INTEGER,                    -- 被操作的记录ID
  payload        TEXT,                       -- JSON变更详情（变更前后）
  ip_address     TEXT,                       -- 操作来源IP（可选）
  user_agent     TEXT,                       -- 操作来源（可选）
  created_at     TEXT DEFAULT (datetime('now'))
);

-- ============================================
-- 索引定义
-- ============================================
CREATE INDEX IF NOT EXISTS idx_audit_actor ON audit_log(actor);
CREATE INDEX IF NOT EXISTS idx_audit_resource ON audit_log(resource, resource_id);
CREATE INDEX IF NOT EXISTS idx_audit_action ON audit_log(action);
CREATE INDEX IF NOT EXISTS idx_audit_time ON audit_log(created_at DESC);

-- ============================================
-- 触发器：自动记录写入操作
-- （可选，由应用层调用更灵活，此处仅保留结构）
-- ============================================
