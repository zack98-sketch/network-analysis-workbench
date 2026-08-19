#!/bin/bash
# ============================================================
# 网络环境分析工作台 - 生产启动脚本 (WSL Ubuntu / Kali-Linux)
# Usage: ./deploy/start_workbench.sh [start|stop|restart|status]
# ============================================================
set -e

APP_DIR="$(cd "$(dirname "$0")/.." && pwd)"
BACKEND_DIR="$APP_DIR/backend"
FRONTEND_DIST="$APP_DIR/frontend/dist"
LOG_DIR="$BACKEND_DIR/logs"
PID_FILE="$LOG_DIR/workbench.pid"
LOG_FILE="$LOG_DIR/workbench.log"
HOST="0.0.0.0"
PORT="${PORT:-8000}"
WORKERS="${WORKERS:-1}"

mkdir -p "$LOG_DIR" "$BACKEND_DIR/data/uploads" "$BACKEND_DIR/data/exports" "$BACKEND_DIR/data/index"

get_pid() {
    if [ -f "$PID_FILE" ]; then
        local pid
        pid=$(cat "$PID_FILE" 2>/dev/null)
        if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
            echo "$pid"
            return 0
        fi
        rm -f "$PID_FILE"
    fi
    return 1
}

is_running() {
    local pid
    pid=$(get_pid 2>/dev/null) && [ -n "$pid" ]
}

start_server() {
    if is_running; then
        echo "[INFO] 服务器已在运行 (PID=$(get_pid))"
        return 0
    fi
    echo "[INFO] 启动网络环境分析工作台..."
    echo "  APP_DIR  = $APP_DIR"
    echo "  HOST:PORT = $HOST:$PORT"
    echo "  WORKERS  = $WORKERS"
    echo "  LOG      = $LOG_FILE"

    cd "$BACKEND_DIR"
    nohup python3 -m uvicorn app.main:app \
        --host "$HOST" \
        --port "$PORT" \
        --workers "$WORKERS" \
        --log-level info \
        --timeout-keep-alive 30 \
        > "$LOG_FILE" 2>&1 &
    echo $! > "$PID_FILE"
    sleep 2

    if is_running; then
        echo "[OK] 启动成功，PID=$(get_pid)"
        echo "     访问地址: http://127.0.0.1:$PORT/"
    else
        echo "[FAIL] 启动失败，请查看日志 $LOG_FILE"
        tail -30 "$LOG_FILE"
        return 1
    fi
}

stop_server() {
    local pid
    pid=$(get_pid 2>/dev/null) || true
    if [ -z "$pid" ]; then
        echo "[INFO] 服务器未运行"
        return 0
    fi
    echo "[INFO] 停止服务器 (PID=$pid)..."
    kill "$pid" 2>/dev/null || true
    for i in 1 2 3 4 5 6 7 8 9 10; do
        if ! kill -0 "$pid" 2>/dev/null; then
            echo "[OK] 已停止"
            rm -f "$PID_FILE"
            return 0
        fi
        sleep 1
    done
    echo "[WARN] 优雅停止超时，强制 kill -9"
    kill -9 "$pid" 2>/dev/null || true
    rm -f "$PID_FILE"
    echo "[OK] 已强制停止"
}

show_status() {
    if is_running; then
        echo "[RUNNING] 服务器运行中，PID=$(get_pid)"
        echo "          访问: http://127.0.0.1:$PORT/"
        local size
        size=$(du -sh "$LOG_FILE" 2>/dev/null | cut -f1)
        echo "          日志: $LOG_FILE (${size:-?})"
    else
        echo "[STOPPED] 服务器未运行"
    fi
}

run_smoke_test() {
    echo "[INFO] 等待服务就绪..."
    for i in $(seq 1 15); do
        if curl -sf "http://127.0.0.1:$PORT/api/health" >/dev/null 2>&1; then
            break
        fi
        sleep 1
    done
    bash "$APP_DIR/deploy/smoke_test.sh"
}

case "${1:-start}" in
    start)   start_server ;;
    stop)    stop_server ;;
    restart) stop_server; sleep 1; start_server ;;
    status)  show_status ;;
    smoke)   run_smoke_test ;;
    test)
        start_server
        run_smoke_test
        stop_server
        ;;
    *)
        echo "Usage: $0 {start|stop|restart|status|smoke|test}"
        exit 1
        ;;
esac
