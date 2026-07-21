-- Phase C: task_detail 软删除标记（幂等由调用方检查列是否已存在后再执行）
-- SQLite 不支持 IF NOT EXISTS for ADD COLUMN；init_db / lifespan 用 PRAGMA 判断。
ALTER TABLE task_detail ADD COLUMN is_active INTEGER NOT NULL DEFAULT 1;
