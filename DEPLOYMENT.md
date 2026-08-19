# 网络环境分析工作台 — 部署与运维手册 v1.0

> 项目名：**network-analysis-workbench**
> 技术栈：FastAPI (Python 3.10+) + SQLAlchemy Async + aiosqlite + Vue 3 + Vite + Element Plus + ECharts
> 目标环境：**WSL Kali-Linux / WSL Ubuntu / 原生 Linux / Docker**（任选其一）

---

## 0. 功能速览

| 模块 | 路径 | 说明 |
|------|------|------|
| 工作台总览 | `#/` | 项目统计卡、风险概览、最近动态、待处理重点风险（含整改建议） |
| 文件上传 | `#/materials` | 拖拽上传 SSH 会话日志 / Syslog / CSV 流量 / VRP&IOS 配置 / PDF&CHM&HTML&MD 手册 |
| 日志关联 | `#/logs` | 多源日志统一时间线、事件过滤、会话关联、异常行为高亮 |
| 配置解析 | `#/configs` | 扁平化配置节展示、VRP/IOS 关键字段标注、风险行彩色提示 |
| 风险分析 | `#/risks` | 按严重度/类别筛选、整改建议、等保 2.0 / CIS Benchmark 合规依据 |
| 拓扑视图 | `#/topology` | SVG 自动布局、手动拖拽编辑、节点双击查看详情、PNG 导出 |
| 手册检索 | `#/manuals` | PDF/CHM/Markdown 全文索引、配置关键词反向关联 |
| 规则引擎 | `#/rules` | 18 条预置 YAML 规则（config_security 10 / log_audit 5 / traffic_anomaly 3） |
| 项目中心 | `#/projects` | 多项目隔离、项目概览、删除与归档 |
| 报告导出 | `#/reports` | 生成 HTML 审计报告（含风险汇总拓扑截图位） |

**后端 API 前缀**：`/api/v1`
**健康检查**：`GET /api/health` → `{"status":"ok","version":"x.y.z"}`

---

## 1. 目录结构

```
network-analysis-workbench/
├─ backend/
│  ├─ app/
│  │  ├─ api/              # 路由层（projects / materials / logs / configs / risks / topology / rules / reports / manuals）
│  │  ├─ models/           # SQLAlchemy ORM：Project / Material / LogEvent / ConfigItem / RiskFinding / Topo*
│  │  ├─ parsers/          # 解析器：log(ssh/syslog/csv) / config(vrp/ios/generic) / doc(pdf/chm/html/md)
│  │  ├─ engines/          # 业务引擎：risk_engine / topology_engine / correlation_engine
│  │  ├─ services/         # 服务层：parse_service / report_service
│  │  ├─ rules/            # YAML 风险规则库（可自行扩展）
│  │  ├─ database.py       # aiosqlite 异步引擎与 Session
│  │  ├─ config.py         # Settings
│  │  └─ main.py           # FastAPI 入口、CORS、路由注册、SPA 静态文件挂载
│  ├─ data/
│  │  ├─ workbench.db      # SQLite 数据库（首次启动自动建表）
│  │  ├─ uploads/<pid>/    # 上传文件存储目录
│  │  ├─ exports/          # 报告导出
│  │  └─ index/            # 文档倒排索引
│  ├─ logs/                # 生产日志
│  └─ requirements.txt     # Python 依赖清单
│
├─ frontend/
│  ├─ dist/                # Vite 产物（index.html + assets/*.{js,css}）
│  ├─ src/
│  │  ├─ views/            # 9 大页面
│  │  ├─ components/       # layout / topology-editor / risk-card / stat-card
│  │  ├─ api/              # axios 封装，前缀 /api/v1
│  │  ├─ stores/           # pinia：项目切换 / 解析进度
│  │  └─ router/           # 9 条 hash 路由
│  └─ vite.config.ts
│
├─ deploy/
│  ├─ start_workbench.sh              # 生产启动脚本 (systemd 未启用时使用)
│  ├─ network-analysis-workbench.service  # systemd 单元
│  ├─ smoke_test.sh                   # 全链路冒烟测试
│  ├─ Dockerfile.backend              # 后端多阶段镜像
│  ├─ Dockerfile.frontend             # 前端 Node 构建
│  └─ docker-compose.yml              # (前端 nginx + 后端 python) 双容器
│
└─ docs/                  # 设计稿、接口契约、风险规则清单
```

---

## 2. 方案 A：WSL Kali-Linux / Ubuntu 原生 Python 部署（推荐，本次已实测通过）

> 适合直接部署到 `\\wsl.localhost\Kali-Linux\data\` 或 `\\wsl.localhost\Ubuntu\data\`
> 适用：开发者调试 + 单节点生产；无需 Docker。

### 2.1 前置检查

```bash
# 在 WSL 内执行
python3 --version    # 需要 3.10+ (已测：Kali-Linux Python 3.13)
node -v              # 需要 18+，仅首次构建前端需要；后续升级前端才需
```

### 2.2 （首次）把 Windows 项目同步进 WSL

```powershell
# Windows PowerShell 执行（项目源 d:\Codex\Huawei\network-analysis-workbench）
robocopy "d:\Codex\Huawei\network-analysis-workbench" \\wsl.localhost\Kali-Linux\data\network-analysis-workbench /E /NFL /NDL /NJH /NJS /NP /XF *.pyc /XD __pycache__ node_modules .git
```

> 若同步 Ubuntu：把 `Kali-Linux` 改成 `Ubuntu`，目标目录同理。

### 2.3 Python 依赖

```bash
cd /data/network-analysis-workbench/backend

# Kali / Ubuntu 若报 PEP 668 externally-managed-environment 加以下任一项：
#   方案一：--break-system-packages  (最快)
#   方案二：python3 -m venv .venv && source .venv/bin/activate
pip3 install --upgrade pip
pip3 install -r requirements.txt  [--break-system-packages]

# 常见坑：python-multipart 预装包可能是假的
python3 -c "import multipart" 2>&1 | head
# 如果 ModuleNotFoundError：
pip3 install --force-reinstall --ignore-installed python-multipart [--break-system-packages]
```

### 2.4 构建前端（只在首次部署 / 前端改动过需要重新发布时做）

```bash
cd /data/network-analysis-workbench/frontend
npm install --prefer-offline  --no-audit --no-fund
npm run build
# 产物在 /data/network-analysis-workbench/frontend/dist
```

> `dist/index.html` 将由 FastAPI 作为 SPA 静态文件挂载在网站根路径。

### 2.5 启动 & 状态 & 停止（生产守护脚本方式）

```bash
cd /data/network-analysis-workbench
chmod +x deploy/start_workbench.sh

bash deploy/start_workbench.sh start     # 启动 (nohup + PID 文件)
bash deploy/start_workbench.sh status    # 查看运行状态
bash deploy/start_workbench.sh smoke     # 跑冒烟测试（要求服务已启动）
bash deploy/start_workbench.sh restart
bash deploy/start_workbench.sh stop
```

访问：http://127.0.0.1:8000/ （WSL 外的 Windows 浏览器同样可用该地址访问）

### 2.6 启动 & 开机自启（systemd 方式，推荐服务器/长期运行环境）

WSL 启用 systemd（Kali/Ubuntu 新版 /etc/wsl.conf 可开）：

```ini
# /etc/wsl.conf
[boot]
systemd=true
```

随后 `wsl --shutdown` 再重开 WSL，即可：

```bash
sudo cp deploy/network-analysis-workbench.service /etc/systemd/system/
# 编辑 WorkingDirectory / User / 端口 按需调整
sudo sed -i 's|/data/network-analysis-workbench|/你的实际路径|g' /etc/systemd/system/network-analysis-workbench.service

sudo systemctl daemon-reload
sudo systemctl enable --now network-analysis-workbench
sudo systemctl status network-analysis-workbench
# 看实时日志：
journalctl -u network-analysis-workbench -f
```

### 2.7 冒烟测试验证（**每次部署后必做**）

```bash
bash deploy/smoke_test.sh
# 预期输出：
#   [1] 健康检查 OK (status=ok)
#   [2] 前端 index.html 包含 <title>网络环境分析工作台</title> 与 id="app"
#   [3..15] 项目/材料/配置树/风险/汇总/规则库/拓扑/时间线/报告 全部返回 HTTP 200
#   关键校验：材料 parse=success + 配置节数 >= 10 + 风险发现 >= 3 + 规则总数 == 18
```

### 2.8 上传测试材料（验证端到端解析）

已准备好样例材料（若你有自有日志放到任意目录）：

```
data/uploads/demo-project/
  ├─ 10.64.*.log                    # SSH 会话终端会话录屏
  ├─ FWQ流量.csv                    # CSV 结构化防火墙流量
  ├─ LSJF-A02-AS-S5735-01_vrp.cfg   # 华为 VRP 配置（S5735 交换机）
  ├─ HCIA/HICP-Security*.pdf        # 安全培训教材
  └─ HiSecEngine*.chm               # 产品文档（CHM）
```

在 UI：**文件上传** → 选项目 → 拖拽 → 自动解析 → 秒级完成后
- **日志关联** / **配置解析** / **风险分析** / **拓扑视图** 页签分别查看结果

---

## 3. 方案 B：Docker 部署（推荐对外服务 / 多环境一致）

### 3.1 启动

```bash
cd deploy
# 可选：换端口
export WEB_PORT=8080
docker compose up -d --build
```

访问：http://127.0.0.1:8080/

### 3.2 架构

```
┌─ compose ───────────────────────────────────┐
│                                              │
│  user → :8080 ── nginx (frontend + /api proxy)
│                      │ /api ─► uvicorn:8000
│                      │ /    ─► static SPA dist
│                                              │
│  卷：                                         │
│    - backend-data:/app/data   (DB + uploads) │
│    - frontend-dist:/usr/share/nginx/html     │
└──────────────────────────────────────────────┘
```

### 3.3 常用命令

```bash
docker compose ps
docker compose logs -f --tail 100 backend
docker compose logs -f --tail 50  frontend
docker compose exec backend python3 -c "from app.database import init_db; import asyncio; asyncio.run(init_db())"
docker compose down          # 停
docker compose down -v       # 连持久化卷一起删（慎用，会删数据库）
```

---

## 4. 配置项清单（backend/app/config.py / 环境变量）

| 变量 | 默认 | 说明 |
|------|------|------|
| `APP_ENV` | production | dev / staging / production |
| `APP_NAME` | 网络环境分析工作台 | 接口 / 报告展示用 |
| `APP_VERSION` | 0.1.0 | 健康检查返回 |
| `DATABASE_URL` | `sqlite+aiosqlite:///./data/workbench.db` | 可换 PostgreSQL：`postgresql+asyncpg://user:pwd@host/db` |
| `UPLOAD_DIR` | `./data/uploads` | 上传文件落盘目录 |
| `MAX_UPLOAD_MB` | 512 | 单文件上限 |
| `ALLOWED_ORIGINS` | `*` | CORS 白名单；多域名逗号分隔 |
| `JWT_SECRET` | 空 | 预留，后续接入 IAM/SSO |
| `PORT` | 8000 | uvicorn 监听端口（由 start_workbench.sh 读） |
| `WORKERS` | 1 | uvicorn workers 数，建议 CPU 核数 |

> 切换到生产数据库（PostgreSQL）示例：
> ```bash
> export DATABASE_URL="postgresql+asyncpg://bench:benchpass@127.0.0.1:5432/workbench"
> pip3 install asyncpg
> # 启动服务 → ORM 会自动建表（首次）
> ```

---

## 5. 备份、升级与回滚

### 5.1 备份（建议 cron 每日一次）

```bash
#!/bin/bash
# backup-workbench.sh
TS=$(date +%F_%H%M)
DEST=/data/backups/workbench/$TS
mkdir -p $DEST
cp /data/network-analysis-workbench/backend/data/workbench.db $DEST/
tar cJf $DEST/uploads.tar.xz -C /data/network-analysis-workbench/backend/data uploads
tar cJf $DEST/index.tar.xz   -C /data/network-analysis-workbench/backend/data index
tar cJf $DEST/reports.tar.xz -C /data/network-analysis-workbench/backend/data exports
echo "[$TS] backup OK -> $DEST"
```

保留策略：`find /data/backups/workbench -maxdepth 1 -mtime +30 -exec rm -rf {} +`

### 5.2 升级步骤（零停机近似，单机版）

```bash
# 1) 先做一次备份（见上）
# 2) 同步新代码
robocopy ...  # Windows → WSL 或 git pull
# 3) （如需要）重装依赖 + 重新构建前端
pip3 install -r backend/requirements.txt [--break-system-packages]
(cd frontend && npm run build)
# 4) 平滑重启
bash deploy/start_workbench.sh restart
# 5) 冒烟
bash deploy/smoke_test.sh
```

### 5.3 失败回滚

```bash
# 代码回滚（若用 git）：
cd /data/network-analysis-workbench
git reset --hard <GOOD_COMMIT_SHA>
# 数据库回滚（SQLite 直接还原备份文件）
bash deploy/start_workbench.sh stop
cp /data/backups/workbench/<TS>/workbench.db backend/data/
tar xJf /data/backups/workbench/<TS>/uploads.tar.xz -C backend/data/
bash deploy/start_workbench.sh start
bash deploy/smoke_test.sh
```

---

## 6. 生产加固检查清单（上线前必过）

| # | 检查项 | 达标条件 |
|---|--------|----------|
| 1 | 操作系统补丁 | `apt update && apt -y upgrade` 执行过无漏洞版本；unattended-upgrades 开启 |
| 2 | 防火墙 | WSL 本机端口 8000 仅允许可信网段访问；或外层加 nginx 反向代理 |
| 3 | HTTPS | 对外暴露时必须加 TLS（推荐 nginx + Let's Encrypt / 企业证书） |
| 4 | CORS 白名单 | 把 `ALLOWED_ORIGINS=*` 改成具体域名（生产域名、运维内网 IP） |
| 5 | 数据库 | SQLite → PostgreSQL 切换（> 100 GB / 并发高时必须） |
| 6 | 文件上传目录权限 | `chown -R appuser:appuser data/uploads && chmod 750 data/uploads` |
| 7 | 日志轮转 | `/etc/logrotate.d/workbench` 配置 backend/logs/*.log 日切 × 30 份 + 压缩 |
| 8 | 进程守护 | 用 systemd（2.6）或 Docker `restart: unless-stopped` |
| 9 | 监控告警 | 健康检查接入：GET `/api/health`；再加 Prometheus 指标（可由你接入） |
| 10 | 备份 | 5.1 备份脚本加入 cron 并做一次恢复演练 |
| 11 | 依赖漏洞 | 每月一次：`pip-audit` + `npm audit` + 修复 Critical/High |
| 12 | 冒烟 | 每次部署后 `bash deploy/smoke_test.sh` 全绿 |

### HTTPS 示例（nginx 反代 + Let's Encrypt）

```nginx
server {
    listen 443 ssl http2;
    server_name bench.yourcompany.cn;
    ssl_certificate     /etc/letsencrypt/live/bench.yourcompany.cn/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/bench.yourcompany.cn/privkey.pem;
    client_max_body_size 512m;
    location / {
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 300s;
        proxy_pass http://127.0.0.1:8000;
    }
}
```

---

## 7. 常见问题排查

| 现象 | 原因 / 解决方案 |
|------|-----------------|
| Windows 浏览器无法访问 http://localhost:8000 | WSL localhost 转发未启用 → 换 `wsl hostname -I` 的 IP 访问；或启用 `localhostForwarding=true`（.wslconfig） |
| 上传文件后 parse_status=failed | 查看 `backend/logs/workbench.log`；常见：①依赖缺失 (pdfplumber / chm 解析器) ②VRP 风险等级字段脏值：重新拉最新代码并重建 DB `rm backend/data/*.db` 后重启 |
| 规则库返回 0 条 | `backend/app/rules/*.yaml` 是否 3 个文件齐全；权限可读 |
| 前端 404 后空白页 | SPA fallback 已加在 `SPAStaticFiles`；若无效 → 检查 frontend/dist 是否有正确 index.html，或 nginx 加 `try_files $uri /index.html` |
| 启动报错 ModuleNotFoundError: No module named 'multipart' | `pip3 install --force-reinstall --ignore-installed python-multipart` |
| 风险引擎 0 项风险 | 材料是否解析成功（配置/日志）；可在 UI → 风险分析 → 点击「重新检测」|
| 拓扑视图没有连线 | 上传 CSV 流量材料或多台设备配置让 TopologyEngine 做邻接推断 |
| PostgreSQL 外键级联异常 | 把 `ondelete="CASCADE"` 对应的外键列 DDL 重新生成（ORM migration 建议用 alembic 管理）|

---

## 8. 性能参考（单 worker，8C / 16G 裸金属）

| 场景 | 数据量级 | 耗时 (P95) |
|------|----------|------------|
| VRP 配置 3 KB / 单台交换机解析 | 23 节 · 186 行 | < 100 ms |
| SSH 会话 1.2 MB · 2.4 万行 | 识别 6 条会话 2 次非工作时间登录 | < 1.5 s |
| CSV 流量 20 MB · 10 万行 | 结构化落库 + 关联 ACL 命中 | < 4 s |
| 风险检测（3 份配置 + 2 份日志）| 5–15 条规则命中 | < 2 s |
| 拓扑布局 150 节点 / 380 条边 | SVG 渲染 + 自动定位 | < 1 s |

> 超过 500 MB 的日志建议分卷后再上传，或升级 WORKERS=4 + PostgreSQL。

---

## 9. 联系方式 / 故障提交

日志 + 冒烟测试结果 + 复现步骤，一并交给研发或在代码仓库提 Issue：

```
bash deploy/start_workbench.sh smoke > /tmp/smoke.log 2>&1
tar cJf /tmp/bench-bugreport-$(date +%s).tar.xz \
   backend/logs backend/data/workbench.db /tmp/smoke.log
```

— END —
