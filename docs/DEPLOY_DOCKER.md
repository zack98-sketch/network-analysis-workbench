# Docker 部署详细说明

本文档适用于 Linux 服务器（x86_64）或任意支持 Docker 的主机进行独立部署，包括在线部署、离线部署、HTTPS 配置、升级运维等完整流程。

---

## 系统要求

| 项目 | 最低要求 | 推荐配置 |
|------|----------|----------|
| 架构 | x86_64 / amd64 | x86_64 / amd64 |
| 操作系统 | Linux（Ubuntu 20.04+, Debian 11+, CentOS 7+） | Ubuntu 22.04 LTS |
| Docker | >= 24.0 | 最新稳定版 |
| Docker Compose | v2（docker compose 子命令） | v2.20+ |
| 内存 | 4 GB RAM | 8 GB RAM |
| 磁盘 | 20 GB 可用空间 | 50 GB SSD |
| CPU | 2 核 | 4 核 |

> 注意：本工具为离线审计工具，**设计用于内网环境，请勿直接暴露到公网**。

---

## 一键部署（在线环境）

### 第 1 步：准备项目代码

```bash
# 方式 1：Git 克隆（如果代码托管在 Git 服务器）
git clone <your-repo-url> network-analysis-workbench
cd network-analysis-workbench

# 方式 2：SCP 上传开发机打包的源码
# 在开发机上：
#   tar -czf network-analysis-workbench.tar.gz network-analysis-workbench/
#   scp network-analysis-workbench.tar.gz user@server:/opt/
# 在服务器上：
#   cd /opt && tar -xzf network-analysis-workbench.tar.gz
```

### 第 2 步：启动服务

```bash
cd /opt/network-analysis-workbench/deploy

# 构建镜像并后台启动
docker compose up -d --build
```

> 首次构建会拉取 `node:20-alpine` 和 `python:3.11-slim-bookworm` 基础镜像，需确保服务器可访问 Docker Hub（或配置私有镜像源）。

### 第 3 步：验证

```bash
# 容器状态应为 healthy
docker compose ps

# 健康检查日志
docker inspect --format='{{json .State.Health}}' sec-workbench | python3 -m json.tool

# API 验证
curl http://服务器IP:8080/api/v1/projects
```

浏览器访问 `http://服务器IP:8080` 即可使用。

---

## 离线部署（无外网服务器）

适用于无法访问 Docker Hub 的内网/隔离环境。

### 在联网机器上：导出镜像

```bash
cd /path/to/network-analysis-workbench

# 1. 构建镜像（需要能访问 Docker Hub + npm + PyPI）
docker build -t sec-workbench:latest -f backend/Dockerfile ..

# 2. 验证镜像
docker images sec-workbench

# 3. 导出并压缩镜像 tarball
docker save sec-workbench:latest | gzip > sec-workbench-image.tar.gz

# 4. 同时导出 docker-compose.yml 和 nginx.conf（如果需要）
#    将以下文件一并拷贝到离线服务器：
#    - sec-workbench-image.tar.gz
#    - deploy/docker-compose.yml
#    - deploy/nginx.conf（可选）
```

产物大小约 **800 MB - 1.2 GB**（gzip 压缩后）。

### 在离线服务器上：导入并启动

```bash
# 1. 加载镜像
docker load < sec-workbench-image.tar.gz

# 验证
docker images | grep sec-workbench

# 2. 创建部署目录结构
mkdir -p /opt/network-analysis-workbench/deploy/data
cp docker-compose.yml /opt/network-analysis-workbench/deploy/
cp nginx.conf /opt/network-analysis-workbench/deploy/   # 可选

# 3. 修改 docker-compose.yml，删除 build 段，仅保留 image
cd /opt/network-analysis-workbench/deploy
# 编辑 docker-compose.yml，注释或删除 build: 段：
# services:
#   workbench:
#     # build:                      # ← 删除或注释
#     #   context: ..               # ← 删除或注释
#     #   dockerfile: backend/Dockerfile  # ← 删除或注释
#     image: sec-workbench:latest   # ← 保留这行

# 4. 启动服务
docker compose up -d
```

---

## HTTPS 配置（Nginx + Let's Encrypt）

如需通过 HTTPS 访问（生产推荐），在服务器上使用 Nginx 反向代理 + Certbot 自动签发证书。

### 第 1 步：安装 Certbot

```bash
# Ubuntu/Debian
sudo apt install -y certbot python3-certbot-nginx

# CentOS/RHEL
sudo yum install -y certbot python3-certbot-nginx
```

### 第 2 步：签发证书（Standalone 模式，不依赖现有 Nginx）

```bash
# 先确保 80 端口未被占用
sudo systemctl stop nginx 2>/dev/null || true
sudo docker compose -f /opt/network-analysis-workbench/deploy/docker-compose.yml stop

# 签发证书（替换为你的域名和邮箱）
sudo certbot certonly --standalone \
    -d workbench.yourcompany.com \
    --email admin@yourcompany.com \
    --agree-tos \
    --no-eff-email
```

证书签发后路径：
- Full Chain: `/etc/letsencrypt/live/workbench.yourcompany.com/fullchain.pem`
- Private Key: `/etc/letsencrypt/live/workbench.yourcompany.com/privkey.pem`

### 第 3 步：更新 Nginx 配置

将 `deploy/nginx.conf` 升级为带 HTTPS 的版本：

```nginx
events {
    worker_connections 1024;
}

http {
    include mime.types;
    default_type application/octet-stream;

    sendfile on;
    keepalive_timeout 65;

    gzip on;
    gzip_types text/plain text/css application/json application/javascript image/svg+xml;

    # HTTP -> HTTPS 跳转
    server {
        listen 80;
        server_name workbench.yourcompany.com;
        return 301 https://$host$request_uri;
    }

    # HTTPS 服务
    server {
        listen 443 ssl http2;
        server_name workbench.yourcompany.com;

        ssl_certificate     /etc/letsencrypt/live/workbench.yourcompany.com/fullchain.pem;
        ssl_certificate_key /etc/letsencrypt/live/workbench.yourcompany.com/privkey.pem;

        ssl_protocols TLSv1.2 TLSv1.3;
        ssl_ciphers HIGH:!aNULL:!MD5;
        ssl_prefer_server_ciphers on;

        client_max_body_size 500m;

        location / {
            proxy_pass http://127.0.0.1:8080;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;

            proxy_http_version 1.1;
            proxy_set_header Upgrade $http_upgrade;
            proxy_set_header Connection "upgrade";

            proxy_read_timeout 86400;
            proxy_send_timeout 86400;
        }
    }
}
```

### 第 4 步：启动 Nginx + Workbench

```bash
# 修改 docker-compose.yml 只监听本地（防止绕过 Nginx 直接访问）
# ports:
#   - "127.0.0.1:8080:8000"
cd /opt/network-analysis-workbench/deploy
docker compose up -d

# 启动 Nginx
sudo nginx -t   # 测试配置
sudo systemctl start nginx
sudo systemctl enable nginx
```

### 第 5 步：证书自动续期

Let's Encrypt 证书有效期 90 天，Certbot 默认已配置 systemd timer 自动续期：

```bash
# 验证 timer 状态
systemctl list-timers | grep certbot

# 手动测试续期
sudo certbot renew --dry-run
```

---

## 升级流程

### 小版本升级（数据向后兼容）

```bash
cd /opt/network-analysis-workbench

# 1. 拉取最新代码（或手动覆盖更新）
git pull origin main

# 2. 进入 deploy 目录，重新构建并滚动更新
cd deploy
docker compose up -d --build
```

容器会先构建新镜像，然后停止旧容器、启动新容器，期间服务中断约 5-10 秒。

**数据库迁移**：应用启动时自动检测并创建缺失的表/列（SQLite 向后兼容），无需手动操作。

### 升级前备份（推荐）

```bash
cd /opt/network-analysis-workbench/deploy

# 1. 停止服务
docker compose stop

# 2. 备份数据目录
tar -czf ../backup/data-upgrade-backup-$(date +%Y%m%d-%H%M).tar.gz data/

# 3. 启动并升级
docker compose up -d --build
```

---

## 日志查看

```bash
cd /opt/network-analysis-workbench/deploy

# 查看最近 200 行日志
docker compose logs -f --tail=200 workbench

# 只看错误日志
docker compose logs workbench 2>&1 | grep -i error

# 按时间范围（配合 journald 或重定向到文件）
docker compose logs workbench --since "2026-08-19T00:00:00" --until "2026-08-19T23:59:59"
```

**日志持久化**（可选）：修改 `docker-compose.yml` 增加日志驱动配置：

```yaml
services:
  workbench:
    # ...
    logging:
      driver: json-file
      options:
        max-size: "100m"
        max-file: "5"
```

---

## 安全加固

### 1. 防火墙限制访问

本工具为离线审计工具，包含敏感的网络配置和日志数据，**严禁直接暴露到公网**。

```bash
# Ubuntu UFW 示例：仅允许内网网段访问
sudo ufw enable
sudo ufw allow from 10.0.0.0/8 to any port 8080
sudo ufw allow from 172.16.0.0/12 to any port 8080
sudo ufw allow from 192.168.0.0/16 to any port 8080

# 或限制特定管理机 IP
sudo ufw allow from 10.0.0.0/24 to any port 8080
```

### 2. 不要暴露 8000 端口

容器内是 8000，但 `docker-compose.yml` 映射为 8080。若使用 Nginx 反向代理，改为：

```yaml
ports:
  - "127.0.0.1:8080:8000"   # 仅本机可访问，外部需走 Nginx
```

### 3. 定期更新基础镜像

```bash
# 拉取最新基础镜像并重建
docker pull node:20-alpine
docker pull python:3.11-slim-bookworm
cd deploy && docker compose build --no-cache && docker compose up -d
```

### 4. 容器以非 root 运行（进阶）

修改 Dockerfile，在最后阶段添加：

```dockerfile
RUN useradd -m -u 1000 appuser && chown -R appuser /app
USER appuser
```

同时确保宿主机 `deploy/data/` 目录 UID 1000 可写。

---

## 附：常用命令速查

```bash
# 进入容器内部调试
docker exec -it sec-workbench bash

# 查看容器资源使用
docker stats sec-workbench

# 查看挂载的卷
docker inspect sec-workbench | jq '.[0].Mounts'

# 清理未使用的旧镜像（升级后）
docker image prune -f
```
