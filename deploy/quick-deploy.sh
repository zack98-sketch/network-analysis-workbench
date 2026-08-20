#!/bin/bash
# 网络环境分析工作台 - Docker 一键部署
# 用法: ./quick-deploy.sh [build|start|stop|logs|rebuild]
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

ACTION="${1:-start}"

case "$ACTION" in
  build)
    echo "构建 Docker 镜像（首次约 5-10 分钟）..."
    docker compose build
    echo "构建完成。运行 ./quick-deploy.sh start 启动服务。"
    ;;
  start)
    echo "启动工作台..."
    docker compose up -d
    echo "等待服务启动..."
    sleep 5
    if curl -sf http://localhost:8080/api/health >/dev/null 2>&1; then
      echo ""
      echo "============================================"
      echo "  部署成功！"
      echo "  访问地址: http://localhost:8080"
      echo "  数据目录: $SCRIPT_DIR/data/"
      echo "  查看日志: ./quick-deploy.sh logs"
      echo "  停止服务: ./quick-deploy.sh stop"
      echo "============================================"
    else
      echo "服务还在启动中，稍等几秒后访问 http://localhost:8080"
      echo "查看启动日志: ./quick-deploy.sh logs"
    fi
    ;;
  stop)
    echo "停止工作台..."
    docker compose down
    echo "已停止。数据保留在 $SCRIPT_DIR/data/"
    ;;
  rebuild)
    echo "重新构建并启动..."
    docker compose down
    docker compose build --no-cache
    docker compose up -d
    sleep 5
    echo "访问地址: http://localhost:8080"
    ;;
  logs)
    docker compose logs -f --tail=50
    ;;
  status)
    docker compose ps
    curl -sf http://localhost:8080/api/health 2>&1 || echo "服务未就绪"
    ;;
  *)
    echo "用法: $0 {build|start|stop|rebuild|logs|status}"
    echo ""
    echo "  build   - 构建镜像（首次部署前执行）"
    echo "  start   - 启动服务（默认）"
    echo "  stop    - 停止服务"
    echo "  rebuild - 重新构建并启动（代码更新后）"
    echo "  logs    - 查看实时日志"
    echo "  status  - 查看服务状态"
    exit 1
    ;;
esac
