# Innogreen PMO 部署指南（生产环境 / 公网 Tunnel）

本目录为生产部署辅助文件。本机已部署,服务地址:
- 公网：**https://pmo.dqhermes.kdns.fr/**
- 后端：`http://127.0.0.1:8000`（仅本机，不对外）

---

## 架构总览

```
浏览器
  ↓ HTTPS
Cloudflare 边缘 (Tunnel 0f853646-a94e-4ba2-8147-45fee95ec15b)
  ↓ 终结 TLS（CF 边缘证书） + 注入 X-Forwarded-Proto
cloudflared-qcc.service（共享隧道进程，配置 ~/.cloudflared/config.yml）
  ↓ http://127.0.0.1:8000
innogreen-pmo-app.service（uvicorn，仅绑 127.0.0.1）
  ↓
FastAPI（main.py）
  ├─ SessionMiddleware（签 cookie / 解 session，最外层）
  ├─ CORS（仅白名单 origin）
  ├─ SlowAPIMiddleware（登录 10/min、建用户 10/h、DB 替换 5/h）
  └─ SecurityHeadersMiddleware（X-Frame / CSP / HSTS / ...）
  ├─ /api/* / /health → 业务路由（auth/ops/tenant）
  └─ 其他路径 → React SPA（dist/index.html，从 web/frontend/dist 托管）
```

### 关键安全闸（详见 `web/CLAUDE.md` / 审查报告）

- `--host 127.0.0.1` 强制本地（**绝不**改 `0.0.0.0`，否则 `PMO_SESSION_SECRET` 泄漏即可伪造 admin 会话）
- `PMO_HTTPS_ONLY=true`（Tunnel 边缘 HTTPS → secure cookie）
- `PMO_TRUST_PROXY_HEADER=true`（读 `X-Forwarded-For` / `CF-Connecting-IP` 解真实 IP；**仅在可信反代后开启**）
- `PMO_CORS_ORIGINS` 含真实前端域（否则 withCredentials cookie 被浏览器拒）
- `PMO_ENABLE_DOCS=false`（Swagger / OpenAPI schema 关闭，防 password 字段名泄漏）
- `PMO_SESSION_SECRET` 强随机 ≥32 字节（`python -c "import secrets; print(secrets.token_hex(32))"`）

---

## 初次部署步骤

### 1. CF 控制台 / 隧道 DNS

在 `dqhermes.kdns.fr` 父域（或 kdns.fr 后台）注册 `pmo` 子域，
CNAME 指向 `0f853646-a94e-4ba2-8147-45fee95ec15b.cfargotunnel.com`，Proxied（橙色云）。

验证：
```bash
dig @1.1.1.1 +short pmo.dqhermes.kdns.fr
# 应返回 104.21.x.x 或 172.67.x.x（CF 通用边缘 IP）
```

### 2. 项目部署目录（已存在）

```bash
cd /home/ubuntu/Innogreen-PMO
# 单独的生产 venv（与开发/审计 venv 隔离）
python3 -m venv .venv
.venv/bin/pip install -r web/requirements.txt

# 前端构建产物
cd web/frontend && npm ci && npm run build && cd ../..
```

### 3. 初始化数据库（一次性）

```bash
python3 scripts/init_db.py --db-path data/innogreen_pmo.db
```

### 4. 生产 `.env`

复制并编辑 `web/.env`（**不**入库，权限 600）：
```bash
cp web/.env.example web/.env
chmod 600 web/.env
```

必填项：
- `PMO_SESSION_SECRET`：`secrets.token_hex(32)` 生成的 64 字符
- `PMO_BOOTSTRAP_ADMIN_PASSWORD`：≥8 位且**不在弱口令黑名单**
  （`change-me*` / `password` / `admin` / `12345678` 等，启动期会拒绝）
- `PMO_HTTPS_ONLY=true`
- `PMO_TRUST_PROXY_HEADER=true`
- `PMO_CORS_ORIGINS=https://pmo.dqhermes.kdns.fr`
- `PMO_ENABLE_DOCS=false`

### 5. systemd unit（已存在）

```bash
cat ~/.config/systemd/user/innogreen-pmo-app.service
# 拷贝本目录的 innogreen-pmo-app.service 到 ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now innogreen-pmo-app.service
systemctl --user status innogreen-pmo-app.service
journalctl --user -u innogreen-pmo-app.service -f  # 跟踪日志
```

### 6. Cloudflare Tunnel ingress（已配置）

`~/.cloudflared/config.yml` 共享同一 tunnel 进程（`qcc-tunnel`），已在文件末尾加：
```yaml
  - hostname: pmo.dqhermes.kdns.fr
    # Innogreen PMO (FastAPI + 静态前端 SPA)，严格本地；Tunnel 边缘终结 TLS
    service: http://127.0.0.1:8000
```

**注意**：Tunnel 配置变更必须 `systemctl --user restart cloudflared-qcc.service`（无 reload 支持），
会导致该 tunnel 上**所有 4 个域名短暂中断**约 5–10 秒。

```bash
# 校验 ingress 配置
cloudflared tunnel ingress validate

# 应用（短暂中断 qcc/sheia/webui/evo + pmo）
systemctl --user restart cloudflared-qcc.service
```

---

## 日常运维

### 重启/查看服务

```bash
systemctl --user status innogreen-pmo-app.service
systemctl --user restart innogreen-pmo-app.service
journalctl --user -u innogreen-pmo-app.service -n 200 --no-pager
```

### 数据库备份（与 dev 同源）

```bash
python3 scripts/backup_db.py --db-path data/innogreen_pmo.db
# 备份到 data/backups/innogreen_pmo_backup_<时间戳>.db
```

建议加 systemd timer 每天定时：
```bash
# /home/ubuntu/.config/systemd/user/pmo-backup.timer
[Unit]
Description=Daily InnoGreen PMO DB backup
[Timer]
OnCalendar=*-*-* 02:30:00
Persistent=true
[Install]
WantedBy=timers.target
```

### 切到 dev / 改代码后重新部署前端

```bash
cd /home/ubuntu/Innogreen-PMO/web/frontend
npm run build
systemctl --user restart innogreen-pmo-app.service
# dist/ 由 uvicorn 直接托管；不依赖 nginx
```

### 查看实时审计

```bash
# 管理员登录后在 UI：用户管理 → 审计日志 Tab
# 或直接查 DB（管理端导 .db 下载）：
.venv/bin/python -c "
import sqlite3
conn = sqlite3.connect('data/innogreen_pmo.db')
for r in conn.execute(\"SELECT created_at, actor, action, resource, resource_id FROM audit_log ORDER BY audit_id DESC LIMIT 20\").fetchall():
    print(r)
"
```

---

## 故障排查

| 症状 | 原因 / 处理 |
|---|---|
| 公网访问 `404` | kdns.fr 域名未生效；`dig @1.1.1.1 +short pmo.dqhermes.kdns.fr` 应返回 CF 边缘 IP |
| 公网访问 `502 Bad Gateway` | uvicorn 未运行；`systemctl --user status innogreen-pmo-app.service` |
| `curl /health` 返 `{"status":"ok","db_exists":false}` | 数据库路径不对；查 `PMO_DB_PATH` |
| 登录后 `/api/auth/me` 401 | session cookie 未生效；99% 是 `PMO_HTTPS_ONLY` 误设 false 或缺 `PMO_TRUST_PROXY_HEADER` |
| 前端 SPA 路由刷新后 404 | 静态 fallback 已加；若仍 404 检查 `web/frontend/dist/index.html` 是否存在 |
| `PMO_SESSION_SECRET` 启动失败 | 长度 < 32 或仍是 `replace-with-output-of-...` 占位符；重新生成 |
| 弱口令拒绝启动 | bootstrap admin 密码在黑名单；换 ≥8 位强密码 |

---

## 端口 / 进程清单

| 端口 | 进程 | 用途 |
|---|---|---|
| 127.0.0.1:8765 | qcc-app.service | 企业资质库（已有） |
| 127.0.0.1:8080 | sheia.service | 上海环评检索（已有） |
| 127.0.0.1:8787 | hermes-webui.service | Hermes WebUI（已有） |
| 127.0.0.1:8788 | evo-static.service | Evo Dashboard（已有） |
| **127.0.0.1:8000** | **innogreen-pmo-app.service** | **Innogreen PMO（本服务）** |

Tunnel：`qcc-tunnel`（`0f853646-...`），共享 `cloudflared-qcc.service` 一个进程承载所有 4+1 域名。

---

## 安全：必须保留的红线

1. `--host 127.0.0.1` —— 绝不改成 `0.0.0.0` 或内网 IP
2. `PMO_SESSION_SECRET` 不入库、不外泄；轮换需所有用户重新登录
3. 数据库备份目录 `data/backups/` 在 `.gitignore`，**勿 commit**
4. admin 操作员只通过 UI 操作，**勿**直接改 `data/innogreen_pmo.db`（绕过 audit_log）
5. `audit_log` 触发器已装（`BEFORE UPDATE/DELETE RAISE(ABORT)`），
   SQLite import (`POST /api/ops/import/db`) 也校验行数 ≥ 当前库 50%，
   防恶意"清空审计"式导入