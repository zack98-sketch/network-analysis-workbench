# WSL2 Ubuntu 部署指南

本文档详细说明如何在 Windows 10/11 的 WSL2 (Ubuntu) 环境中部署网络环境分析工作台。

---

## 前置条件

- **操作系统**: Windows 10 版本 1903+ 或 Windows 11
- **WSL2**: 已启用并安装 WSL2，内核版本 >= 5.10
- **Ubuntu 发行版**: Ubuntu 22.04 LTS 或 Ubuntu 24.04 LTS（推荐）
- **部署方式二选一**:
  - **方式 A（推荐）**: 安装 Docker Desktop for Windows 并启用 WSL2 集成
  - **方式 B（源码）**: 在 WSL 内直接安装 Python 3.11+ 和 Node.js 20+

---

## 方式 A：Docker Compose 部署（推荐，最简单）

此方式将前后端打包为单个 Docker 镜像，一键启动，数据持久化到宿主机目录。

### 第 1 步：从 Windows 拷贝项目到 WSL

在 WSL Ubuntu 终端中执行：

```bash
# 将项目从 Windows 磁盘复制到 WSL 用户主目录（推荐，避免 NTFS 性能问题）
# <项目源挂载路径> 替换为本地 Windows 项目所在 WSL 挂载路径，例如 /mnt/d/projects
cp -r /mnt/d/projects/network-analysis-workbench ~/

# 进入项目目录
cd ~/network-analysis-workbench
```

> **提示**: 也可直接使用 `/mnt/d/...` 路径，但 WSL2 访问 Windows NTFS 文件系统性能较差，建议拷贝到 WSL 内部的 ext4 分区。

### 第 2 步：进入 deploy 目录并启动服务

```bash
cd ~/network-analysis-workbench/deploy

# 构建镜像并后台启动（首次构建约 5-15 分钟，取决于网络速度）
sudo docker compose up -d --build
```

构建过程说明：
1. 第一阶段使用 `node:20-alpine` 安装前端依赖并构建生产静态文件
2. 第二阶段使用 `python:3.11-slim-bookworm` 安装 Chromium 依赖、CJK 字体、Python 后端依赖
3. 将前端构建产物拷贝到后端 `static/` 目录，最终镜像约 1.5-2 GB

### 第 3 步：验证部署

等待容器启动（约 15-30 秒），然后验证：

```bash
# 查看容器运行状态
sudo docker compose ps

# 查看启动日志
sudo docker compose logs -f --tail=50
```

浏览器访问：
- **前端界面**: http://localhost:8080
- **API 健康检查**:

```bash
curl http://localhost:8080/api/v1/projects
# 预期返回 JSON 数组（可能为空 []）
```

### 第 4 步：数据持久化说明

```
宿主机路径（相对于 docker-compose.yml）:
~/network-analysis-workbench/deploy/data/
    ├── workbench.db          # SQLite 数据库文件
    ├── uploads/              # 用户上传的原始文件
    │   ├── *.log             # 日志文件
    │   ├── *.cfg             # 配置文件
    │   ├── *.chm             # CHM 手册
    │   └── *.pdf             # PDF 文档
    ├── exports/              # 导出的报告文件
    └── index/                # 全文检索索引
```

映射关系：`deploy/data/` → 容器内 `/app/data/`

**备份整个数据目录**即可完整迁移项目数据：

```bash
# 备份
tar -czf workbench-data-backup-$(date +%Y%m%d).tar.gz ~/network-analysis-workbench/deploy/data/

# 恢复
tar -xzf workbench-data-backup-YYYYMMDD.tar.gz -C ~/network-analysis-workbench/deploy/
```

### 第 5 步：常用运维命令

```bash
# 查看实时日志
sudo docker compose logs -f workbench

# 重启服务
sudo docker compose restart

# 停止服务（保留数据）
sudo docker compose stop

# 启动已停止的服务
sudo docker compose start

# 停止并删除容器（数据卷不会删除）
sudo docker compose down

# 重新构建并升级（数据保留）
sudo docker compose up -d --build
```

---

## 方式 B：源码直接部署（适合开发调试）

此方式直接在 WSL 中运行前后端，无需 Docker，适合开发调试或机器资源有限的场景。

### 第 1 步：安装系统依赖

```bash
sudo apt update

# 安装 Python 3.11、venv、pip、Node.js、npm、7z、中日韩字体
sudo apt install -y \
    python3.11 python3.11-venv python3-pip \
    nodejs npm \
    p7zip-full fonts-noto-cjk

# 验证版本
python3.11 --version   # 期望 3.11.x
node --version         # 期望 >= 18.x（若不足，用 nvm 升级到 20）
```

> **可选 - 升级 Node.js 到 20**:
> ```bash
> curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
> sudo apt install -y nodejs
> ```

### 第 2 步：启动后端服务

```bash
cd ~/network-analysis-workbench/backend

# 创建并激活虚拟环境
python3.11 -m venv venv
source venv/bin/activate

# 安装 Python 依赖
pip install -r requirements.txt

# 创建数据目录
mkdir -p data/uploads data/exports data/index

# 启动后端（生产模式，2 workers）
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 2
```

后端运行在 http://localhost:8000

### 第 3 步：启动前端（新开一个终端）

**生产构建**（推荐，速度快，通过后端 8000 端口统一访问）：

```bash
cd ~/network-analysis-workbench/frontend
npm install
npm run build
# 构建产物输出到 backend/static/
# 打开 http://localhost:8000 即可访问
```

**开发模式**（热更新，端口 5173）：

```bash
cd ~/network-analysis-workbench/frontend
npm install
npm run dev
# 打开 http://localhost:5173
```

### 第 4 步：访问验证

| 模式 | 访问地址 |
|------|----------|
| 前端生产构建 + 后端 | http://localhost:8000 |
| 前端开发服务器 | http://localhost:5173 |
| 后端 API 直接 | http://localhost:8000/api/v1/projects |

---

## 数据迁移 / 测试材料导入

### 备份与迁移

直接打包 `data/` 目录即可：

```bash
# Docker 部署：数据在 deploy/data/
cd ~/network-analysis-workbench/deploy
tar -czf data-backup.tar.gz data/

# 源码部署：数据在 backend/data/
cd ~/network-analysis-workbench/backend
tar -czf data-backup.tar.gz data/
```

### 导入测试材料（批量）

Windows 下的测试文件可通过以下方式导入：

**方式 1：通过 UI 上传（推荐）**
1. 浏览器访问工作台
2. 进入「文件上传」模块
3. 拖拽或选择 `.log` / `.csv` / `.cfg` / `.chm` / `.pdf` 文件上传

**方式 2：直接拷贝 + 触发扫描**
```bash
# 将 Windows 下的文件拷贝到 uploads 目录（<测试材料挂载路径> 替换为本地路径）
cp /mnt/d/projects/test_materials/*.log /mnt/d/projects/test_materials/*.csv /mnt/d/projects/test_materials/*.cfg \
   /mnt/d/projects/test_materials/*.chm /mnt/d/projects/test_materials/*.pdf \
   ~/network-analysis-workbench/deploy/data/uploads/

# 调用扫描 API 让系统识别并入库
curl -X POST http://localhost:8080/api/v1/materials/scan \
     -H "Content-Type: application/json" \
     -d '{"project_id": "default"}'
```

**文件命名建议**（便于自动关联设备）：
- 日志：`{IP}_{日期}_{时间}.log`，例如 `10.0.0.1_2026-08-17_20_08_36.log`
- 配置：`{设备名或IP}_config.cfg`，例如 `demo_firewall_01.cfg`
- 手册：`{产品型号}_文档.{chm|pdf}`，例如 `demo_product_manual.chm`

---

## 常见问题排查

### 1. 端口占用（8080 或 8000 被占）

```bash
# 查看占用进程
sudo lsof -i :8080
sudo lsof -i :8000

# 修改 docker-compose.yml 端口映射，例如改为 9090:8000
ports:
  - "9090:8000"
```

### 2. 权限问题（data 目录写入失败）

```bash
# Docker 方式：修正目录所有者
sudo chown -R 1000:1000 ~/network-analysis-workbench/deploy/data
# 或放宽权限（开发环境）
sudo chmod -R 777 ~/network-analysis-workbench/deploy/data
```

### 3. CJK 字体缺失（PDF 报告中文为方块）

源码部署方式需要手动安装 CJK 字体：

```bash
sudo apt install -y fonts-noto-cjk
fc-cache -fv
```

Docker 镜像已预装 `fonts-noto-cjk`，无需额外操作。

### 4. SQLite 数据库文件锁（database is locked）

- 确保只有一个 uvicorn worker 写入 SQLite（生产建议 2 workers 只读时可接受，写入需加锁重试）
- 不要在 NTFS 分区（`/mnt/d/...`）上运行 SQLite，迁移到 WSL 内部 ext4
- 源码部署：降低 workers 为 1

### 5. 大文件上传超时（Nginx 反向代理场景）

若使用独立 Nginx 反向代理，确保配置：

```nginx
client_max_body_size 500m;
proxy_read_timeout 86400;
proxy_send_timeout 86400;
```

项目提供的 `deploy/nginx.conf` 已包含以上配置。

### 6. Docker Desktop WSL2 集成未启用

打开 Docker Desktop → Settings → Resources → WSL Integration → 勾选对应 Ubuntu 发行版 → Apply & Restart
