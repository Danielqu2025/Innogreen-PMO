# Innogreen PMO Web（Phase C）

## 前置

```bash
# 仓库根目录确保数据库已初始化
python scripts/init_db.py
```

## 测试（CI 同款）

```bash
pip install -r web/requirements.txt
pytest tests/ -v
```

测试会使用独立库 `data/test_api.db`，不影响开发库。

## 备份

```bash
python scripts/backup_db.py
python scripts/backup_db.py --db-path data/innogreen_pmo.db
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

## 前端

```bash
cd web/frontend
npm install
npm run dev
```

- 界面: http://127.0.0.1:5173
- 登录：使用管理员分配的账号密码（或通过 `PMO_BOOTSTRAP_ADMIN_*` 启动后用 bootstrap admin 登录）

## 路由

| 路径 | 说明 |
|------|------|
| `/login` | 账号密码登录 |
| `/ops` | Dashboard |
| `/ops/projects` | 企业列表（可筛卡点） |
| `/ops/projects/new` | 新增企业 |
| `/ops/projects/:id` | 企业详情 + 关键路径 + 周进展时间线 |
| `/ops/projects/:id/edit` | 编辑企业 |
| `/ops/projects/:id/tasks/:taskId` | 更新任务进度 + 追加周记 |
| `/ops/stages` | 8 阶段地图 |
| `/ops/stages/:id` | 阶段详情 |
| `/ops/pitfalls` | 避坑指南 |
| `/ops/pitfalls/new` | 录入避坑 |
| `/ops/pitfalls/:id` | 避坑详情 |
| `/ops/tasks` | 任务清单维护（仅管理员；停用软删、插入自动顺移编号） |
| `/ops/users` | 用户管理（仅管理员） |
| `/tenant/*` | 企业端占位（v1.4） |

## 生产部署（参考）

前端 `api/client.ts` 用 `baseURL=""`（同源），dev 靠 Vite proxy，**生产必须由 nginx 同源托管 `dist/` 并反代 `/api`**——不能让浏览器直连后端 8000。

### 1. 后端（只绑本机，不对外）

```bash
cd web
# 生产 .env：session_secret 必填，关文档
#   PMO_SESSION_SECRET = python -c "import secrets; print(secrets.token_hex(32))"
#   PMO_BOOTSTRAP_ADMIN_USERNAME/PASSWORD = 首个管理员（可选，冷启动用）
#   PMO_ENABLE_DOCS = false
#   PMO_HTTPS_ONLY = true     # HTTPS 反代后开启 Secure cookie
#   PMO_HOST = 127.0.0.1        # 关键：不要改 0.0.0.0，会话密钥不能对外暴露
cp .env.example .env   # 编辑实际值
cd backend
pip install -r requirements.txt
uvicorn main:app --host 127.0.0.1 --port 8000   # 建议用 systemd / supervisord 常驻
```

### 2. 前端（构建产物进镜像/部署目录，别 volume 挂宿主机 dist）

```bash
cd web/frontend
npm ci
npm run build          # 产物在 web/frontend/dist/
```

### 3. nginx（同源：托管 dist + 反代 /api、/health）

```nginx
server {
    listen 80;
    server_name pmo.innogreen.local;

    root /opt/innogreen-pmo/web/frontend/dist;
    index index.html;

    # SPA 路由回退
    location / {
        try_files $uri $uri/ /index.html;
    }

    # 注意 proxy_pass 末尾不要加 "/"，否则会吃掉 /api 前缀
    location /api/  { proxy_pass http://127.0.0.1:8000; }
    location = /health { proxy_pass http://127.0.0.1:8000; }
}
```

### 4. 备份（定时）

```bash
# crontab 每天 02:30 备份（Online Backup API，事务一致快照）
30 2 * * * cd /opt/innogreen-pmo && python scripts/backup_db.py
```

### 安全要点

- **后端必须只绑 `127.0.0.1`**：`PMO_SESSION_SECRET` 一旦泄漏，攻击者可伪造任意会话。应用对外暴露 = 攻击者拿到密钥后直接以 admin 身份操作。
- 上线前确认 `PMO_SESSION_SECRET` 已设、`PMO_ENABLE_DOCS=false`。
- `dist/` 要打进部署目录或镜像，不要用 compose 挂宿主机 `dist`（否则忘了 rebuild 就是旧前端）。
