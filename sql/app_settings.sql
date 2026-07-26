-- ============================================
-- app_settings：系统级键值配置（JSON）
-- 例：journal_alert → 周报异常判定规则
-- ============================================
CREATE TABLE IF NOT EXISTS app_settings (
  setting_key   TEXT PRIMARY KEY,
  value_json    TEXT NOT NULL,
  updated_at    TEXT DEFAULT (datetime('now')),
  updated_by    TEXT
);
