# Excel 任务映射 & 周进展表设计（草案）

> 日期：2026-07-22  
> 输入：`Projects.xlsx`（15 sheet）↔ `task_detail.task_code`  
> 状态：**草案，待运营确认 `review_status=todo` 行后再用于导入**

---

## 1. 映射表

**文件**：[`excel_task_to_task_code.csv`](excel_task_to_task_code.csv)

### 键怎么定

Excel 不是「任务名唯一」，而是：

```text
excel_section（大段，如「工艺审批」）
  └ excel_parent（中类，如「安评」「环评」）
       └ excel_task_name（叶子，如「报告编制」）
```

同名「报告编制」在安评/环评/职评下应对不同 `task_code`，因此映射主键为三元组，不是单列任务名。

### 列说明

| 列 | 含义 |
|----|------|
| `excel_section` / `excel_parent` / `excel_task_name` | Excel 三层键 |
| `excel_count` | 在 15 个 sheet 中出现次数 |
| `confidence` | `rule` 规则消歧 / `alias` 别名 / `exact` 全名相同 / `fuzzy` 模糊 / `unmapped` 待确认 / `skip` 非进度 |
| `task_code` / `task_id` / `task_name` / `stage_name` | 标准库目标 |
| `notes` | 消歧说明 |
| `review_status` | `proposed` 可先用 / `todo` 需人工 |

### 当前统计（自动生成）

以 `python scripts/rebuild_excel_task_mapping.py` 最近一次为准：

- 复合键约 **188** 条  
- 已映射约 **177** 条（`rule` / `alias` / `exact` / `fuzzy`）  
- **unmapped** 约 **10** 条：多为现场细拆或库中无对应标准任务，需人工补码或 skip  

重新生成：

```bash
python scripts/rebuild_excel_task_mapping.py
```

### 使用约定

1. 导入前优先用 `review_status=proposed` 且 `task_code` 非空的行。  
2. `unmapped` / `fuzzy`：人工补 `task_code`、扩 seed、或标 skip。  
3. 「商务谈判 / 合同签订 / 正式提供服务」必须靠 parent 服务类型消歧（物业/消防/污水/危废…）。

---

## 2. `progress_journal` 表设计

**DDL**：[`sql/progress_journal.sql`](../../sql/progress_journal.sql)

### 职责切分

| 表 | 存什么 | 不存什么 |
|----|--------|----------|
| `project_progress` | 任务**当前态**：状态、计划/实际日期、第三方、卡点摘要 | 每周历史正文 |
| `progress_journal` | 任务（或项目）**按周叙事**：week + note | 不单独充当「当前状态」 |

Excel 一列「3.9-3.15」里的长文本 → **一行 journal**；改状态仍写 `project_progress`。

### 字段要点

- `week_start`：规范日（建议解析列头得到的起始日，ISO `YYYY-MM-DD`）  
- `week_label`：保留 Excel 原始列头，便于对账  
- `task_id` 可空：项目级周记（少见）  
- `source`：`excel_import` / `web` / `api`  
- 唯一索引 `(project_id, task_id, week_start, note)`：支持重复导入幂等  

### 建议的配套扩展（非本文件 DDL，导入前宜补）

在 `project_progress` 增加（或等价列）：

- `planned_start` / `planned_end` ← Excel E/F  
- `vendor` ← Excel「涉及第三方单位」  

当前态与周记分离后，Dashboard「本周有更新」= 查 `progress_journal` 最近 `week_start`。

### API / UI（后续，非本草案范围）

```http
GET  /api/ops/projects/{id}/tasks/{task_id}/journal
POST /api/ops/projects/{id}/tasks/{task_id}/journal
     { "week_start": "2026-03-09", "week_label": "...", "note": "..." }
```

任务详情页：上方当前状态表单，下方周记时间线。

---

## 3. 推荐确认流程

1. 运营打开 CSV，过滤 `review_status=todo`，逐行填 `task_code` 或标 skip。  
2. 把确认结果另存为 `excel_task_to_task_code.reviewed.csv`。  
3. 执行 `progress_journal.sql` +（可选）progress 日期/第三方迁移。  
4. 再写导入脚本：项目建档 → progress upsert → journal 按周插入。

### 导入命令（已实现）

```bash
# 默认 dry-run
python scripts/import_projects_progress.py
python scripts/import_projects_progress.py --sheets B5,A13

# 写库（先自动备份 data/backups/）
python scripts/import_projects_progress.py --apply
```

- 每个 sheet → `project_profile.project_code`（如 `B5`）  
- 状态：未启动→待开始，不涉及→已跳过，进行中（正常|延后）→进行中，已完成→已完成  
- 计划开始/完成 → `planned_start` / `planned_end`；实际完成 → `completed_at`；第三方 → `vendor`  
- 周进展列 → `progress_journal`（`source=excel_import`，重复导入幂等）  
- 映射主键：Excel 三层键 `(excel_section, excel_parent, excel_task_name)` → `task_id`（见 reviewed CSV）  
- 映射文件优先：`excel_task_to_task_code.reviewed.csv`  

---

## 4. 刻意不做

- 不把 40+ 周列建成宽表  
- 不在无映射确认时全量自动导入  
- 不把「问题汇总」行映射进进度任务（归 Problems / 另表）
