-- ============================================
-- Innogreen PMO 用户表 v1.3 (Phase C auth)
-- 用途：账号密码登录 + 三角色权限（admin/operator/viewer）
-- 日期：2026-07-21
-- ============================================

CREATE TABLE IF NOT EXISTS users (
  user_id        INTEGER PRIMARY KEY AUTOINCREMENT,
  username       TEXT NOT NULL UNIQUE,        -- 登录名
  password_hash  TEXT NOT NULL,               -- bcrypt 哈希
  display_name   TEXT,                        -- 显示名（审计/界面）
  role           TEXT NOT NULL DEFAULT 'operator',  -- admin / operator / viewer
  is_active      INTEGER NOT NULL DEFAULT 1,  -- 1=启用 0=禁用（软删除）
  created_at     TEXT DEFAULT (datetime('now')),
  updated_at     TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_users_role ON users(role);
CREATE INDEX IF NOT EXISTS idx_users_active ON users(is_active);
