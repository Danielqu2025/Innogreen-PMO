# Innogreen PMO Web 应用方案 v1.3

> 更新日期：2026-07-21
> 从 v1.2 CLI方案升级为 Web 应用方案

---

## 一、升级决策

### v1.2 vs v1.3 对比

| 维度 | v1.2 (CLI) | v1.3 (Web) |
|------|-------------|-------------|
| 数据访问 | SQL查询 | 浏览器访问 |
| 学习曲线 | 需要SQL知识 | 无需技术背景 |
| 移动办公 | 不支持 | 响应式支持 |
| 用户范围 | Daniel团队 | Daniel + 企业客户 |
| 开发复杂度 | 低 | 中等 |

### 决策结论

✅ **升级到 Web 应用**，同时保留 CLI 工具作为批量操作和自动化的补充。

---

## 二、技术栈

| 层级 | 技术 | 选择理由 |
|------|------|----------|
| **后端** | FastAPI | 自动API文档、类型安全、异步支持 |
| **ORM** | SQLAlchemy 2.0 | 类型安全、与SQLite无缝衔接 |
| **数据库** | SQLite | 与CLI共用，无需迁移 |
| **前端** | Vue 3 + Vuetify 3 | Material Design、移动优先 |
| **状态管理** | Pinia | Vue官方推荐 |
| **路由** | Vue Router | SPA路由 |

---

## 三、系统架构

```
┌─────────────────────────────────────────────────────┐
│                    客户端 (浏览器/手机/平板)                │
└─────────────────────────────┬───────────────────────┘
                              │ HTTP/REST
                              ▼
┌─────────────────────────────────────────────────────┐
│                    FastAPI (后端)                         │
│  /api/stages  /api/projects  /api/dashboard           │
│  /api/tasks  /api/progress   /api/pitfalls            │
│  /docs (OpenAPI自动文档)                                │
└─────────────────────────────┬───────────────────────────┘
                              │ SQLAlchemy
                              ▼
┌─────────────────────────────────────────────────────┐
│                    SQLite 数据库                            │
│              (与 CLI 工具共用 innogreen_pmo.db)           │
└─────────────────────────────────────────────────────┘
```

---

## 四、API 设计

### 4.1 RESTful 端点

| 资源 | 方法 | 路径 | 说明 |
|------|------|------|------|
| **阶段** | GET | `/api/stages` | 所有阶段列表 |
| | GET | `/api/stages/{id}` | 阶段详情 |
| | GET | `/api/stages/{id}/tasks` | 阶段下所有任务 |
| **任务** | GET | `/api/tasks` | 所有任务 |
| | GET | `/api/tasks/{id}` | 任务详情 |
| | GET | `/api/tasks/{id}/dependencies` | 任务依赖关系 |
| **企业** | GET | `/api/projects` | 所有企业 |
| | GET | `/api/projects/{id}` | 企业详情 |
| | POST | `/api/projects` | 新增企业 |
| | PUT | `/api/projects/{id}` | 更新企业 |
| | GET | `/api/projects/{id}/progress` | 企业所有任务进度 |
| | GET | `/api/projects/{id}/critical-path` | 企业关键路径 |
| **进度** | GET | `/api/progress` | 所有进度记录 |
| | PUT | `/api/progress/{id}` | 更新单条进度 |
| | GET | `/api/progress/blockers` | 所有卡点列表 |
| **避坑** | GET | `/api/pitfalls` | 所有避坑指南 |
| | GET | `/api/pitfalls?stage=5` | 按阶段筛选 |
| | POST | `/api/pitfalls` | 新增避坑 |
| **仪表盘** | GET | `/api/dashboard/summary` | 统计数据 |
| | GET | `/api/dashboard/blockers` | 卡点汇总 |

### 4.2 API 响应示例

```json
// GET /api/projects/1
{
  "project_id": 1,
  "company_name": "朗盛特殊化学品有限公司",
  "short_name": "朗盛",
  "business_type": "研发",
  "current_stage_id": 13,
  "current_stage_name": "装修施工",
  "progress_percent": 60,
  "project_status": "进行中",
  "building": "F6d-1"
}

// GET /api/dashboard/summary
{
  "total_projects": 17,
  "by_status": {
    "进行中": 12,
    "卡点": 2,
    "已完成": 3
  },
  "by_stage": {
    "装修施工": 5,
    "设计审查": 4,
    "试生产": 3
  },
  "blockers": [
    {"project": "某企业", "task": "安评报告", "note": "等待专家评审"}
  ]
}
```

---

## 五、前端页面

### 5.1 页面结构

| 页面 | 路由 | 核心功能 |
|------|------|----------|
| **Dashboard** | `/` | 企业进度卡片、卡点提醒、阶段分布图 |
| **企业列表** | `/projects` | 搜索、状态筛选、排序 |
| **企业详情** | `/projects/:id` | 企业信息、阶段进度、任务清单 |
| **新增企业** | `/projects/new` | 表单验证、多步引导 |
| **阶段地图** | `/stages` | 18阶段可视化 |
| **阶段详情** | `/stages/:id` | 阶段任务列表、常见避坑 |
| **避坑指南** | `/pitfalls` | 按阶段/影响筛选、关键词搜索 |
| **进度更新** | `/progress/:projectId/:taskId` | 状态变更、卡点备注 |

### 5.2 UI 规范

**组件库**：Vuetify 3 (Material Design)

**配色**：
```
primary:    #1976D2  (蓝色 - 主色调)
error:      #FF5252  (红色 - 卡点)
warning:    #FFB74D  (橙色 - 重要)
success:    #69F0AE  (绿色 - 完成)
```

**关键路径**：
```
🔴 关键路径：#FF5252
🟡 重要任务：#FFB74D
🟢 一般任务：#69F0AE
```

---

## 六、项目结构

```
innogreen-pmo/
├── web/
│   ├── backend/                   # FastAPI后端
│   │   ├── main.py              # 应用入口
│   │   ├── config.py           # 配置
│   │   ├── database.py         # 数据库连接
│   │   ├── models/            # SQLAlchemy模型 (7表)
│   │   ├── schemas/           # Pydantic schemas
│   │   ├── routers/           # API路由
│   │   │   ├── stages.py
│   │   │   ├── tasks.py
│   │   │   ├── projects.py
│   │   │   ├── progress.py
│   │   │   ├── pitfalls.py
│   │   │   └── dashboard.py
│   │   └── services/          # 业务逻辑
│   │   └── progress_service.py
│   │
│   ├── frontend/               # Vue.js前端
│   │   ├── src/
│   │   │   ├── main.js
│   │   │   ├── App.vue
│   │   │   ├── router/index.js
│   │   │   ├── stores/       # Pinia
│   │   │   ├── api/          # Axios调用
│   │   │   ├── views/        # 页面
│   │   │   │   ├── Dashboard.vue
│   │   │   │   ├── ProjectList.vue
│   │   │   │   ├── ProjectDetail.vue
│   │   │   │   ├── ProjectForm.vue
│   │   │   │   ├── StageList.vue
│   │   │   │   ├── StageDetail.vue
│   │   │   │   ├── PitfallList.vue
│   │   │   │   └── PitfallDetail.vue
│   │   │   └── components/    # 公共组件
│   │   │       ├── AppHeader.vue
│   │   │       ├── AppNav.vue
│   │   │       ├── StageCard.vue
│   │   │       ├── TaskItem.vue
│   │   │       ├── ProgressBar.vue
│   │   │       └── BlockerAlert.vue
│   │   ├── package.json
│   │   └── vite.config.js
│   │
│   ├── requirements.txt        # Python依赖
│   └── README.md              # 启动说明
│
├── data/
│   └── innogreen_pmo.db      # SQLite数据库
│
└── scripts/                   # CLI工具(保留)
```

---

## 七、开发计划

### 7.1 开发阶段

| 阶段 | 内容 | 时间 |
|------|------|------|
| **M1** | 项目脚手架 | 0.5天 |
| **M2** | 数据库连接 + API路由 | 0.5天 |
| **M3** | 阶段/任务 API | 0.5天 |
| **M4** | 企业/进度 API | 0.5天 |
| **M5** | 避坑/仪表盘 API | 0.5天 |
| **M6** | 前端脚手架 | 0.5天 |
| **M7** | Dashboard页面 | 0.5天 |
| **M8** | 企业列表/详情 | 0.5天 |
| **M9** | 进度更新 | 0.5天 |
| **M10** | 避坑指南页面 | 0.5天 |
| **M11** | 响应式优化 | 0.5天 |
| **M12** | 文档与测试 | 0.5天 |

**总计：约 6 天**

### 7.2 里程碑

```
Day 1: 后端基础 + API完成
Day 2-3: 前端基础 + Dashboard
Day 4-5: 企业管理 + 进度更新
Day 6: 优化 + 文档 + 验收
```

---

## 八、启动方式

### 开发环境

```bash
# 后端
cd web/backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000

# 前端 (新终端)
cd web/frontend
npm install
npm run dev

# 访问
# 前端: http://localhost:5173
# API文档: http://localhost:8000/docs
```

### 依赖清单

**后端 (requirements.txt)**:
```
fastapi>=0.100
uvicorn[standard]>=0.20
sqlalchemy>=2.0
pydantic>=2.0
```

**前端 (package.json)**:
```json
{
  "dependencies": {
    "vue": "^3.4",
    "vue-router": "^4.2",
    "vuetify": "^3.4",
    "@mdi/font": "^7.4",
    "pinia": "^2.1",
    "axios": "^1.6"
  }
}
```

---

## 九、与 CLI 的关系

### 保留 CLI 的场景

| 场景 | CLI | Web |
|------|-----|-----|
| 批量导入数据 | ✅ | ❌ |
| 自动化脚本 | ✅ | ❌ |
| 日常查询 | ❌ | ✅ |
| 进度更新 | ❌ | ✅ |
| 移动办公 | ❌ | ✅ |

### 数据同步

共用 `data/innogreen_pmo.db`，CLI 和 Web 实时同步。

---

## 十、数据库模型（7张表）

详见 v1.2 方案 `development_plan_v1.0.md` 的"三、数据模型设计"章节。

核心表：
- `stage_map` - 18个阶段
- `task_detail` - 92个任务
- `task_dependency` - 任务依赖
- `pitfall_guide` - 避坑指南
- `stage_pitfall_ref` - 阶段-避坑关联
- `project_profile` - 企业档案
- `project_progress` - 项目进度

---

## 十一、下一步行动

1. **创建项目结构**
2. **实现后端 API**
3. **实现前端页面**
4. **测试与部署**

---

**方案版本：v1.3**
**状态：待 Daniel 确认后可开始开发**
