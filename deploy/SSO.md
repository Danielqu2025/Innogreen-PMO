# Innogreen 同域 SSO 部署（P3）

一条公网域名经 nginx 路径分流到 Portal / PMO / qcc / sh_eia，共享 `innogreen_session` cookie。

应用侧角色统一为 **admin / operator / viewer**（历史 qcc、sh_eia 的 `user` ≡ `operator`）。壳层响应式：`≤960` 侧栏抽屉、`≤720` 顶栏图标化。

## 路径约定

| 公网路径 | 上游 | 说明 |
|---------|------|------|
| `/` `/login` `/api/auth` `/api/apps` | `127.0.0.1:8001` Portal | IdP |
| `/pmo/` | `127.0.0.1:8000`（本机若 8000 占用可用 `8800`，见下方本地代理） | 去掉前缀后反代 |
| `/qcc/` | `127.0.0.1:8765` qcc | 去掉前缀后反代 |
| `/eia/` | `127.0.0.1:8080` sh_eia | 去掉前缀后反代 |

配置文件：[`nginx.innogreen-sso.conf`](nginx.innogreen-sso.conf)（listen `127.0.0.1:8788`）。

### Windows 本机快速试用（无 nginx）

```bash
# 终端分别启动 Portal:8001、PMO:8800、qcc:8765、sh_eia:8080 后：
python scripts/local_sso_proxy.py
```

打开 http://127.0.0.1:8788/ （`/pmo/`→8800，`/qcc/`→8765，`/eia/`→8080）。

## Cookie（各端必须一致）

| 项 | 值 |
|----|-----|
| Name | `innogreen_session` |
| Path | `/` |
| Secure | 生产 `true`（`HTTPS_ONLY` / `PMO_HTTPS_ONLY` / `QCC_HTTPS_ONLY` / `SH_EIA_HTTPS_ONLY`） |
| SameSite | `Lax` |
| Domain | 同域路径方案**留空** |

密钥：`SESSION_SECRET` == `PMO_SESSION_SECRET` == `QCC_SESSION_SECRET` == `SH_EIA_SESSION_SECRET`。

## 环境变量速查

**Portal `portal/.env`**
```
SESSION_SECRET=...
SESSION_COOKIE_NAME=innogreen_session
HTTPS_ONLY=true
CORS_ORIGINS=https://innogreen.example.com
PMO_PUBLIC_URL=https://innogreen.example.com/pmo/
QCC_PUBLIC_URL=https://innogreen.example.com/qcc/
SH_EIA_PUBLIC_URL=https://innogreen.example.com/eia/
```

**PMO `web/.env`**
```
PMO_SESSION_SECRET=...          # 同 Portal
PMO_SESSION_COOKIE_NAME=innogreen_session
PMO_HTTPS_ONLY=true
PMO_TRUST_PROXY_HEADER=true
PMO_CORS_ORIGINS=https://innogreen.example.com
PMO_PORTAL_BASE_URL=http://127.0.0.1:8001
PMO_PORTAL_WEB_URL=https://innogreen.example.com
PMO_PUBLIC_BASE=/pmo
```
前端构建：
```bash
cd web/frontend
set VITE_BASE=/pmo/          # Windows
# export VITE_BASE=/pmo/     # Linux
npm ci && npm run build
```

**qcc `.env`**
```
QCC_PORTAL_BASE_URL=http://127.0.0.1:8001
QCC_PORTAL_WEB_URL=https://innogreen.example.com
QCC_SESSION_SECRET=...
QCC_SESSION_COOKIE_NAME=innogreen_session
QCC_HTTPS_ONLY=true
QCC_PUBLIC_BASE=/qcc
```

**sh_eia `.env`（Scrapling/examples/sh_eia）**
```
SH_EIA_PORTAL_BASE_URL=http://127.0.0.1:8001
SH_EIA_PORTAL_WEB_URL=https://innogreen.example.com
SH_EIA_SESSION_SECRET=...
SH_EIA_SESSION_COOKIE_NAME=innogreen_session
SH_EIA_HTTPS_ONLY=true
SH_EIA_PUBLIC_BASE=/eia
SH_EIA_HOST=127.0.0.1
SH_EIA_PORT=8080
```

## Cloudflare 从「双域名」迁到「统一门户」（小白逐步操作）

### 先搞懂：以前 vs 现在

**以前（两个子域名，各自直连应用）**

```
https://pmo.你的域名  ──Cloudflare Tunnel──▶ 本机 127.0.0.1:8000（PMO）
https://qcc.你的域名  ──Cloudflare Tunnel──▶ 本机 127.0.0.1:8765（qcc）
```

**现在（一个域名，先进 nginx，再按路径分流）**

```
https://innogreen.你的域名/       ──Tunnel──▶ 本机 nginx:8788 ──▶ Portal :8001
https://innogreen.你的域名/pmo/   ──Tunnel──▶ 本机 nginx:8788 ──▶ PMO    :8000
https://innogreen.你的域名/qcc/   ──Tunnel──▶ 本机 nginx:8788 ──▶ qcc    :8765
https://innogreen.你的域名/eia/   ──Tunnel──▶ 本机 nginx:8788 ──▶ sh_eia :8080
```

要点：

1. Cloudflare Tunnel **只能按「域名」转发**，**不会**自动去掉 `/pmo`、`/qcc`、`/eia` 前缀。  
2. 所以 Tunnel 必须指到 **nginx（8788）**，由 nginx 负责剥前缀并转发到各应用。  
3. 旧的 `pmo.` / `qcc.` 子域名建议做成 **301 跳转到新地址**，书签不会彻底失效。

下面把「你的域名」举例写成 `dqhermes.kdns.fr`，新统一入口举例写成 `innogreen.dqhermes.kdns.fr`。  
你操作时把名字换成自己的真实域名即可。

### 开始前请确认（服务器上）

在服务器 SSH 里逐条检查：

```bash
# 1) Portal / PMO / qcc / sh_eia 都在本机监听（端口按你实际为准）
ss -lntp | grep -E '8001|8000|8765|8080|8788'

# 2) nginx 配置已安装且指向 8788（见 deploy/nginx.innogreen-sso.conf）
sudo nginx -t
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8788/
# 期望：200 或 302（能通就行，不要 Connection refused）

# 3) 找到 cloudflared 配置文件位置（常见如下）
ls ~/.cloudflared/config.yml
# 或
ls /etc/cloudflared/config.yml
```

如果 `8788` 不通：先按本文「路径约定」把 nginx 配好并 `sudo systemctl reload nginx`，**再改 Cloudflare**。  
顺序错误会导致公网全挂。

---

### 步骤 1：记下当前 Tunnel 配置（方便回滚）

```bash
# 备份旧配置
cp ~/.cloudflared/config.yml ~/.cloudflared/config.yml.bak.$(date +%Y%m%d)

# 看一眼现在有哪些 hostname（记下 pmo / qcc 旧域名）
cat ~/.cloudflared/config.yml
```

旧配置通常类似：

```yaml
ingress:
  - hostname: pmo.dqhermes.kdns.fr
    service: http://127.0.0.1:8000
  - hostname: qcc.dqhermes.kdns.fr
    service: http://127.0.0.1:8765
  - service: http_status:404
```

把这两个旧 hostname **抄到记事本**，后面做跳转要用。

---

### 步骤 2：改成「一个域名 → nginx:8788」

用编辑器打开配置（二选一，看你的文件实际在哪）：

```bash
nano ~/.cloudflared/config.yml
# 或
sudo nano /etc/cloudflared/config.yml
```

把 `ingress:` 整段改成下面这样（**保留**文件顶部的 `tunnel:` / `credentials-file:` 不动）：

```yaml
ingress:
  # 统一门户入口 → 本机 nginx
  - hostname: innogreen.dqhermes.kdns.fr
    service: http://127.0.0.1:8788

  # 必须保留：未匹配时返回 404
  - service: http_status:404
```

注意：

- **删掉**（或注释掉）原来指向 `:8000` / `:8765` 的两条。  
  留着等于绕过 Portal，cookie / SSO 会乱。  
- `hostname` 换成你要对外公布的**新统一域名**。  
- `service` 必须是 `http://127.0.0.1:8788`，不是 8000/8001/8765。

保存退出（nano：`Ctrl+O` 回车，再 `Ctrl+X`）。

---

### 步骤 3：给新域名加 DNS（指到这个 Tunnel）

在**服务器**执行（把名字换成你的）：

```bash
# 查看 tunnel 名称
cloudflared tunnel list

# 把新域名路由到该 tunnel（会在 Cloudflare DNS 自动加一条 CNAME）
cloudflared tunnel route dns <你的-tunnel名称> innogreen.dqhermes.kdns.fr
```

去 Cloudflare 网页确认：

1. 打开 [https://dash.cloudflare.com](https://dash.cloudflare.com) 并登录  
2. 点你的域名（如 `dqhermes.kdns.fr`）  
3. 左侧 **DNS** → **Records**  
4. 应能看到一条类似：  
   - **Type**: CNAME  
   - **Name**: `innogreen`  
   - **Target**: `xxxx.cfargotunnel.com`（一长串）  
   - 云朵图标为**橙色**（Proxied，已代理）  

若没有这条记录：再执行一次上面的 `tunnel route dns`，或在 DNS 页手动添加 CNAME（Name=`innogreen`，Target 填 Tunnel 的 `*.cfargotunnel.com`，代理开启）。

---

### 步骤 4：重启 cloudflared 使配置生效

先确认你是用 systemd 用户服务还是系统服务：

```bash
# 常见：用户级服务
systemctl --user list-units '*cloudflare*' --all

# 或系统级
systemctl list-units '*cloudflare*' --all
```

重启（按你实际服务名二选一）：

```bash
# 用户级示例
systemctl --user restart cloudflared.service
# 有的机器叫 cloudflared-qcc.service，以 list-units 看到的为准
systemctl --user status cloudflared.service --no-pager

# 系统级示例
sudo systemctl restart cloudflared
sudo systemctl status cloudflared --no-pager
```

状态应显示 `active (running)`。若失败，看日志：

```bash
journalctl --user -u cloudflared.service -n 50 --no-pager
# 或
sudo journalctl -u cloudflared -n 50 --no-pager
```

常见报错：`config.yml` 缩进错、`ingress` 最后缺少 `http_status:404`、hostname 拼错。

---

### 步骤 5：本机先验证「经 nginx」能通（还没动旧域名跳转）

在服务器上：

```bash
curl -sI http://127.0.0.1:8788/ | head -5
curl -sI http://127.0.0.1:8788/pmo/ | head -5
curl -sI http://127.0.0.1:8788/qcc/ | head -5
curl -sI http://127.0.0.1:8788/eia/ | head -5
```

然后在**你自己的电脑浏览器**打开（等 DNS 生效，通常几十秒到几分钟）：

1. `https://innogreen.dqhermes.kdns.fr/` → 应出现统一门户登录页  
2. 登录后打开 `https://innogreen.dqhermes.kdns.fr/pmo/`  
3. 打开 `https://innogreen.dqhermes.kdns.fr/qcc/`  
4. 打开 `https://innogreen.dqhermes.kdns.fr/eia/` 

若浏览器报 DNS 错误：再等一会，或用  
`nslookup innogreen.dqhermes.kdns.fr`  
看是否已有 CNAME。

若 502：多半是 nginx 通了但后端没起，或 Tunnel 仍指旧端口——回到步骤 2/4 核对。

---

### 步骤 6：旧子域名做 301 跳转（书签不废）

目的：有人访问旧的 `https://pmo.xxx` / `https://qcc.xxx` 时，自动跳到新路径。

> 推荐在 **Cloudflare 边缘**做跳转（不必让 Tunnel 再托管旧域名）。

#### 6.1 确认旧 DNS 记录还在

Dashboard → 你的域名 → **DNS** → **Records**  

`pmo`、`qcc` 两条 CNAME 可以**先留着**（橙云代理），后面 Redirect Rule 会在边缘改写，不一定要再回源。

#### 6.2 创建 Redirect Rule（逐条做）

1. Dashboard → 选中域名 → 左侧 **Rules** → **Redirect Rules**  
   （若界面是新版，可能在 **Rules** → **Overview** → **Create rule** → 选 Redirect）  
2. 点 **Create rule**  
3. 规则名称：`pmo-to-unified`  
4. **If incoming requests match…** 选 **Custom filter expression**，点 **Edit expression**，粘贴：

```
http.host eq "pmo.dqhermes.kdns.fr"
```

5. **Then…** 选择 **Dynamic**（动态），目标 URL 填：

```
concat("https://innogreen.dqhermes.kdns.fr/pmo", http.request.uri.path)
```

6. **Status code** 选 **301**  
7. 勾选 **Preserve query string**（保留 `?xxx=` 参数）  
8. 点 **Deploy**

再新建第二条，名称 `qcc-to-unified`：

- 匹配表达式：

```
http.host eq "qcc.dqhermes.kdns.fr"
```

- 动态目标：

```
concat("https://innogreen.dqhermes.kdns.fr/qcc", http.request.uri.path)
```

- 同样 301 + Preserve query string → **Deploy**

#### 6.3 验证跳转

在你电脑上：

```bash
curl -sI https://pmo.dqhermes.kdns.fr/ | head -15
curl -sI https://qcc.dqhermes.kdns.fr/ | head -15
```

应看到类似：

```
HTTP/2 301
location: https://innogreen.dqhermes.kdns.fr/pmo/
```

浏览器直接打开旧地址，也应自动跳到带 `/pmo/` 或 `/qcc/` 的新 URL。

---

### 步骤 7：关掉 Cloudflare Access（避免双重登录）

应用已经有 Portal 登录。如果还开着 Zero Trust Access，会出现「先登 Cloudflare、再登 Portal」，而且 cookie 容易乱。

1. 打开 [https://one.dash.cloudflare.com](https://one.dash.cloudflare.com)  
2. 左侧 **Access** → **Applications**  
3. 若列表里有针对 `pmo.` / `qcc.` / `innogreen.` 的应用：点进去 → **Delete**（或禁用）  
4. 再用无痕窗口访问 `https://innogreen.dqhermes.kdns.fr/`：  
   - 应直接看到 **Portal 登录页**  
   - **不应**先跳到 Cloudflare 那套邮箱验证码登录  

---

### 步骤 8：SSL / HTTPS 相关开关（Dashboard）

域名 → **SSL/TLS**：

1. **Overview**：加密模式建议 **Full** 或 **Full (strict)**（Tunnel 场景用 Full 即可）  
2. **Edge Certificates** → **Always Use HTTPS** = **On**  

域名 → **Speed**（建议先关掉，减少干扰）：

- **Rocket Loader** = Off  
- Auto Minify 若有，先 Off  

这些有助于：Secure Cookie、SSE 批量同步进度条更稳。

---

### 步骤 9：应用 `.env` 与前端（和 Cloudflare 配套）

Tunnel 指对了还不够，各端环境变量必须用**新统一域名**（示例）：

**Portal `portal/.env`**

```
HTTPS_ONLY=true
SESSION_COOKIE_NAME=innogreen_session
SESSION_COOKIE_DOMAIN=
CORS_ORIGINS=https://innogreen.dqhermes.kdns.fr
PMO_PUBLIC_URL=https://innogreen.dqhermes.kdns.fr/pmo/
QCC_PUBLIC_URL=https://innogreen.dqhermes.kdns.fr/qcc/
SH_EIA_PUBLIC_URL=https://innogreen.dqhermes.kdns.fr/eia/
```

**PMO `web/.env`**

```
PMO_HTTPS_ONLY=true
PMO_SESSION_COOKIE_NAME=innogreen_session
PMO_SESSION_COOKIE_DOMAIN=
PMO_PORTAL_BASE_URL=http://127.0.0.1:8001
PMO_PORTAL_WEB_URL=https://innogreen.dqhermes.kdns.fr
PMO_CORS_ORIGINS=https://innogreen.dqhermes.kdns.fr
PMO_PUBLIC_BASE=/pmo
```

并重建前端（路径前缀）：

```bash
cd /path/to/Innogreen-PMO/web/frontend
export VITE_BASE=/pmo/
npm ci && npm run build
# 然后按你现有方式重启 PMO 后端 / 静态资源服务
```

**qcc `.env`**

```
QCC_HTTPS_ONLY=true
QCC_SESSION_COOKIE_NAME=innogreen_session
QCC_SESSION_COOKIE_DOMAIN=
QCC_PORTAL_BASE_URL=http://127.0.0.1:8001
QCC_PORTAL_WEB_URL=https://innogreen.dqhermes.kdns.fr
QCC_PUBLIC_BASE=/qcc
```

**sh_eia `.env`**

```
SH_EIA_HTTPS_ONLY=true
SH_EIA_SESSION_COOKIE_NAME=innogreen_session
SH_EIA_SESSION_COOKIE_DOMAIN=
SH_EIA_PORTAL_BASE_URL=http://127.0.0.1:8001
SH_EIA_PORTAL_WEB_URL=https://innogreen.dqhermes.kdns.fr
SH_EIA_PUBLIC_BASE=/eia
```

`SESSION_SECRET` / `PMO_SESSION_SECRET` / `QCC_SESSION_SECRET` / `SH_EIA_SESSION_SECRET` **必须相同**。  
`SESSION_COOKIE_DOMAIN` **必须留空**（同域路径共享 cookie，不要写成 `.dqhermes.kdns.fr`）。

改完后重启 Portal、PMO、qcc、sh_eia、nginx。

若还没合并用户，先做上一节「生产账号合并清单」，再把各应用的 `*_PORTAL_BASE_URL` 配上以启用 SSO。

---

### 步骤 10：最终验收清单（按顺序勾）

| # | 操作 | 期望 |
|---|------|------|
| 1 | 打开 `https://innogreen…/` | Portal 登录页 |
| 2 | 登录成功 | 地址栏仍是同一域名；开发者工具 Cookie 有 `innogreen_session`（Secure） |
| 3 | 点进 PMO 或打开 `/pmo/` | 不用再登录；能正常用；顶栏有「返回门户」 |
| 4 | 打开 `/qcc/` | 不用再登录；能正常用 |
| 4b | 打开 `/eia/`（或直连 sh_eia） | 不用再登录；能正常用 |
| 5 | Portal 点退出 | 再开 `/pmo/` `/qcc/` `/eia/` 会要求重新登录 |
| 6 | 打开旧 `https://pmo.…/` | 301 到 `https://innogreen…/pmo/…` |
| 7 | 打开旧 `https://qcc.…/` | 301 到 `https://innogreen…/qcc/…` |
| 8 | 无痕窗口不应先出现 Cloudflare Access 登录 | 只有 Portal 登录 |

---

### 出问题怎么回滚

1. 恢复 Tunnel 配置：  
   `cp ~/.cloudflared/config.yml.bak.日期 ~/.cloudflared/config.yml`  
   然后 `systemctl --user restart cloudflared…`  
2. Cloudflare Redirect Rules 里把刚建的两条 **Disable** 或删除。  
3. PMO/qcc 的 `*_PORTAL_BASE_URL` 临时留空，可退回「各应用本地登录」（过渡期用）。

### 不推荐的做法（了解即可）

继续用两个子域名 + `SESSION_COOKIE_DOMAIN=.你的根域` 跨子域共享 cookie：能做，但 cookie 作用域更大、配置更容易错。本项目默认推荐 **单域名 + `/pmo` `/qcc` `/eia` 路径**。

## 生产账号合并清单（已有 PMO / qcc / sh_eia 用户时）

目标：把服务器上已有账号迁入 Portal，**保留各自应用角色**，不删除源库用户；切 SSO 后由 Portal 统一登录，用 `app_memberships` 控制能否进各应用。

### 模型对照

| 原系统 | 迁入 Portal 后 |
|--------|----------------|
| PMO `users.role`（admin/operator/viewer） | `app_memberships(app_code=PMO, role=原角色)` |
| qcc `users.role` + `is_approved` | 已审批 → `app_memberships(qcc, admin\|operator\|viewer)`（历史 `user`→`operator`）；未审批 → **不建** qcc 授权 |
| sh_eia `users.role` + `status` | `status=active` → `app_memberships(sh_eia, admin\|operator\|viewer)`（历史 `user`→`operator`）；pending/disabled → **不建** |
| 多端同名用户名 | **一个** Portal 用户 + 多条 membership |
| 密码 | 拷贝 bcrypt 哈希（优先 PMO → qcc → sh_eia） |
| Portal 自身 `role` | 任一侧为 admin → Portal `admin`，否则 `viewer`（仅管门户后台） |

无某应用 membership = 能登 Portal，但进不了该应用。管理员之后在 Portal「账号管理」加减授权即可。

### 步骤（务必按序）

1. **备份**  
   - PMO：`innogreen_pmo.db`（及 `-wal`/`-shm` 若存在）  
   - qcc：`qualifications.db`  
   - sh_eia：`data/auth.db`（与业务库 `eia.db` 分开）  
   - 若已有 `portal.db` 一并备份  

2. **先部署 / 启动 Portal**  
   - 配好 `SESSION_SECRET`（之后与各应用相同）  
   - **此时不要**给各应用填 `*_PORTAL_BASE_URL`（仍用本地登录，避免合并未完成就切 SSO）  

3. **干跑合并，核对计划**（仓库根目录执行，路径改成服务器真实路径）  
```bash
python scripts/merge_users_to_portal.py --dry-run \
  --portal-db /path/to/data/portal.db \
  --pmo-db /path/to/data/innogreen_pmo.db \
  --qcc-db /path/to/qcc/data/qualifications.db \
  --sh-eia-db /path/to/sh_eia/data/auth.db
```
   重点检查：  
   - 新建 vs「已存在仅补授权」  
   - 同名是否应为同一人（若同名不同人，先改一侧用户名再合并）  
   - qcc 未审批 / sh_eia 非 active 是否故意无对应 membership  
   - 同名多端密码不同时，合并后以 **PMO 密码** 优先  

4. **正式写入**（确认 dry-run 无误后）  
```bash
python scripts/merge_users_to_portal.py \
  --portal-db /path/to/data/portal.db \
  --pmo-db /path/to/data/innogreen_pmo.db \
  --qcc-db /path/to/qcc/data/qualifications.db \
  --sh-eia-db /path/to/sh_eia/data/auth.db
```

5. **在 Portal 管理页抽查**（`/admin`）  
   - 原仅某一端 / 多端用户的授权是否正确  
   - 试登几个真实账号（密码不对则在 Portal 重置）  

6. **再打开 SSO**  
   - 按上文为各应用配置 `*_PORTAL_BASE_URL`、共享 cookie / secret、路径前缀  
   - 重建 PMO 前端（`VITE_BASE=/pmo/`）并重启四端 + nginx  

7. **冒烟**（见下一节）+ 额外确认：  
   - 原仅 PMO 用户进得了 `/pmo/`、进不了 `/qcc/` `/eia/`（或反之）  
   - 多端用户对应路径都能进，角色与合并前一致  

8. **源库用户表**  
   - SSO 开启后鉴权不再读各应用本地 `users`，**不会自动删除**  
   - 稳定运行一段时间后再归档即可；切勿在合并/切 SSO 当天删源表  

### 合并后日常运维

- 新建用户、改密、启停、应用授权：只在 **Portal「账号管理」**  
- 给某人开通第二应用：编辑其 membership  
- 撤销某应用访问：去掉对应 membership（不必删 Portal 账号）  

脚本说明见 [`scripts/merge_users_to_portal.py`](../scripts/merge_users_to_portal.py)。

## 冒烟清单

1. `https://host/` 打开 Portal，登录成功，响应 `Set-Cookie: innogreen_session=...; Secure; HttpOnly; Path=/; SameSite=Lax`
2. 同标签打开 `/pmo/` → 无需再登，`/pmo/api/auth/me` 200
3. 打开 `/qcc/` → 无需再登，`/qcc/api/auth/me` 200
4. 打开 `/eia/` → 无需再登，`/eia/api/auth/me` 200
5. Portal 退出后，各应用 `/me` 均 401
6. 无 membership 的账号访问对应应用登录得 403「未授权」

建议上线顺序：**账号合并 → 本机 nginx 通 → Cloudflare Tunnel 改指 8788 → Redirect 旧子域 → 各端打开 SSO → 按本清单冒烟**。详细 Cloudflare 点击步骤见上文「Cloudflare 从双域名迁到统一门户」。
