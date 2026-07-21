-- project_progress：计划日期 + 第三方（幂等由调用方 PRAGMA 判断后再 ADD）
ALTER TABLE project_progress ADD COLUMN planned_start TEXT;
ALTER TABLE project_progress ADD COLUMN planned_end TEXT;
ALTER TABLE project_progress ADD COLUMN vendor TEXT;
