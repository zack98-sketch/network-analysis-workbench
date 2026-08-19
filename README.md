# 网络环境分析工作台

面向企业网络安全审计场景的一体化离线分析平台。支持防火墙/交换机等设备的日志关联分析、配置合规检测、产品手册全文检索、风险评估与整改建议输出、网络拓扑自动推导以及标准化审计报告导出。

---

## 项目简介

网络环境分析工作台（Network Analysis Workbench）旨在为安全运维人员和审计人员提供一个**本地化、离线可用**的综合分析环境，覆盖从原始材料导入到最终审计报告生成的完整闭环。

**核心能力**：
- 多格式材料导入：设备日志（.log/.csv）、配置文件（.cfg/.conf）、产品手册（.chm/.pdf）
- 结构化解析与建模：华为 VRP 等主流网络操作系统配置自动拆解
- 关联分析：基于时间轴与会话的日志关联、事件聚类与攻击链还原
- 风险检测：内置规则引擎 + CIS/等保基线，自动生成分级风险清单与整改建议
- 知识检索：CHM/PDF/HTML 文档全文索引，支持自然语言搜索
- 拓扑推导：根据配置自动生成网络拓扑图，支持手动调整
- 报告导出：PDF / Word / Markdown / HTML 多格式标准化审计报告

---

## 技术架构

```
┌────────────────────────────────────────────────────────────┐
│                        前端 (Vue 3 + Vite)                 │
│  Dashboard · 文件上传 · 日志分析 · 配置解析 · 风险分析      │
│  拓扑视图 · 手册检索 · 规则引擎 · 项目中心 · 报告导出       │
└──────────────────────────┬─────────────────────────────────┘
                           │ HTTP / WebSocket
┌──────────────────────────▼─────────────────────────────────┐
│                    后端 (FastAPI + Python 3.11)            │
│  ┌────────────┐ ┌───────────┐ ┌───────────┐ ┌────────────┐ │
│  │ API 路由层 │ │ 业务服务层│ │ 规则引擎  │ │ 文档解析器 │ │
│  └────────────┘ └───────────┘ └───────────┘ └────────────┘ │
│  ┌────────────┐ ┌───────────┐ ┌───────────┐ ┌────────────┐ │
│  │ 日志解析器 │ │ 配置解析器│ │ 全文检索  │ │ 报告生成器 │ │
│  └────────────┘ └───────────┘ └───────────┘ └────────────┘ │
└──────────────────────────┬─────────────────────────────────┘
                           │
            ┌──────────────┴──────────────┐
            ▼                             ▼
      SQLite (Alembic)              文件系统
   workbench.db                /app/data/
                              ├── uploads/   (原始文件)
                              ├── exports/   (导出报告)
                              └── index/     (全文索引)
```

**打包方式**：通过多阶段 Docker 构建，前端构建产物（`backend/static/`）由后端 FastAPI 直接托管，单一镜像即可运行完整服务，无需独立部署 Nginx 或前端服务器。

---

## 快速开始

### Docker Compose 一键部署（推荐）

前置条件：已安装 Docker >= 24.0 和 Docker Compose v2。

```bash
# 1. 进入 deploy 目录
cd network-analysis-workbench/deploy

# 2. 构建镜像并后台启动
docker compose up -d --build

# 3. 打开浏览器访问
# http://localhost:8080
```

数据持久化目录：`deploy/data/`（映射到容器内 `/app/data/`）。

### WSL2 部署 / 源码部署 / 离线部署

详细步骤参见：
- [WSL2 Ubuntu 部署指南](docs/DEPLOY_WSL.md)
- [Docker 部署详细说明](docs/DEPLOY_DOCKER.md)

---

## 文档索引

| 文档 | 说明 |
|------|------|
| [docs/DEPLOY_WSL.md](docs/DEPLOY_WSL.md) | WSL2 Ubuntu 环境下的完整部署指南，含 Docker Compose 与源码两种方式，数据迁移，常见问题 |
| [docs/DEPLOY_DOCKER.md](docs/DEPLOY_DOCKER.md) | 通用 Linux 服务器 Docker 部署手册，含在线/离线部署、HTTPS 配置、升级流程、安全加固 |
| [docs/USER_GUIDE.md](docs/USER_GUIDE.md) | 用户操作手册，所有模块说明、典型工作流、快捷键、支持格式、FAQ |

---

## 目录结构

```
network-analysis-workbench/
├── backend/
│   ├── Dockerfile              # 多阶段生产构建
│   ├── app/                    # FastAPI 后端应用
│   ├── requirements.txt        # Python 依赖
│   └── data/                   # 运行时数据（部署后自动创建）
│       ├── workbench.db        # SQLite 数据库
│       ├── uploads/            # 上传文件
│       ├── exports/            # 导出报告
│       └── index/              # 全文检索索引
├── frontend/
│   ├── package.json
│   ├── vite.config.ts
│   └── src/                    # Vue 3 前端源码
├── deploy/
│   ├── docker-compose.yml      # Compose 编排文件
│   ├── nginx.conf              # Nginx 反向代理配置（可选）
│   ├── entrypoint.sh           # 容器入口脚本（可选）
│   └── data/                   # Docker 数据卷挂载点（运行后创建）
├── docs/
│   ├── DEPLOY_WSL.md
│   ├── DEPLOY_DOCKER.md
│   └── USER_GUIDE.md
├── .dockerignore
└── README.md
```

---

## 注意事项

- 本工具为**离线审计工具**，设计用于内网环境，部署时请通过防火墙限制可信 IP 访问，**不要直接暴露到公网**。
- 所有数据保存在本地 `data/` 目录，请定期备份。
- PDF 报告导出依赖 Chromium 运行时；中文显示依赖 `fonts-noto-cjk`，Docker 镜像已预装。
- 上传的原始材料不会离开部署机器，无任何云端上传行为。
