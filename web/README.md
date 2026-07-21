# Innogreen PMO Web（Phase B 只读）

## 前置

```bash
# 仓库根目录确保数据库已初始化
python scripts/init_db.py
```

## 后端

```bash
cd web
copy .env.example .env   # Windows
pip install -r requirements.txt
cd backend
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

- API 文档: http://127.0.0.1:8000/docs  
- 默认 Token: `dev-token-change-me`（见 `.env`）

## 前端

```bash
cd web/frontend
npm install
npm run dev
```

- 界面: http://127.0.0.1:5173  
- 登录页填入与后端相同的 Token

## 路由

| 路径 | 说明 |
|------|------|
| `/login` | 口令登录 |
| `/ops` | Dashboard |
| `/ops/projects` | 企业列表（可筛卡点） |
| `/ops/projects/:id` | 企业详情 + 关键路径 Steps |
| `/ops/stages` | 8 阶段地图 |
| `/ops/pitfalls` | 避坑指南 |
| `/tenant/*` | 企业端占位（v1.4） |
