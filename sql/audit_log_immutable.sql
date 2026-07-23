-- ============================================
-- audit_log 不可篡改触发器（v1.3+ Phase D）
-- 用途：审计日志只能 INSERT，任何 UPDATE/DELETE 由 SQLite 直接 RAISE 拦截。
-- 适用：生产部署的 PMO（v1.3 C3 及以上）。
-- 启动期由 web/backend/main.py 的 lifespan 幂等执行（IF NOT EXISTS）。
-- ============================================

CREATE TRIGGER IF NOT EXISTS audit_log_no_update
BEFORE UPDATE ON audit_log
BEGIN
  SELECT RAISE(ABORT, 'audit_log is append-only: UPDATE forbidden');
END;

CREATE TRIGGER IF NOT EXISTS audit_log_no_delete
BEFORE DELETE ON audit_log
BEGIN
  SELECT RAISE(ABORT, 'audit_log is append-only: DELETE forbidden');
END;