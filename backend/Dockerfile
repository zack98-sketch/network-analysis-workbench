# ===== 阶段1: 构建前端 =====
FROM node:20-alpine AS frontend-build

WORKDIR /build
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build
# 产物在 /build/../backend/static = /backend/static

# ===== 阶段2: 后端运行时 =====
FROM python:3.11-slim-bookworm

# 安装 CJK 字体和报告导出依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    fonts-noto-cjk \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 安装 Python 依赖
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# 复制后端代码
COPY backend/ ./

# 从前端构建阶段复制静态资源
COPY --from=frontend-build /backend/static ./static

# 数据持久化目录
VOLUME ["/app/data"]

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
