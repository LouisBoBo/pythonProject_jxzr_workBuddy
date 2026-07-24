#!/usr/bin/env bash
# 一键启动本地开发：API (8765) + Web (5180)
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

API_PORT="${MES_SERVER_PORT:-8765}"
WEB_PORT="${VITE_PORT:-5180}"
PID_DIR="$ROOT/.run"
mkdir -p "$PID_DIR" "$ROOT/data"/{history,uploads,exports,converted}

log() { printf '\033[1;34m[dev]\033[0m %s\n' "$*"; }
err() { printf '\033[1;31m[dev]\033[0m %s\n' "$*" >&2; }

need_cmd() {
  command -v "$1" >/dev/null 2>&1 || { err "缺少命令: $1"; exit 1; }
}

need_cmd python3
need_cmd npm

# 可选：安装依赖
if [[ "${INSTALL_DEPS:-0}" == "1" ]]; then
  log "安装 Python 依赖..."
  python3 -m pip install -r "$ROOT/requirements.txt"
  log "安装前端依赖..."
  (cd "$ROOT/apps/web" && npm install)
fi

if [[ ! -d "$ROOT/apps/web/node_modules" ]]; then
  log "首次启动：安装前端依赖..."
  (cd "$ROOT/apps/web" && npm install)
fi

# 清理旧进程（仅本仓库相关）
stop_port() {
  local port="$1"
  local pids
  pids="$(lsof -tiTCP:"$port" -sTCP:LISTEN 2>/dev/null || true)"
  if [[ -n "$pids" ]]; then
    log "释放端口 $port (pids: $pids)"
    kill $pids 2>/dev/null || true
    sleep 1
  fi
}

stop_port "$API_PORT"
stop_port "$WEB_PORT"

log "启动 API → http://127.0.0.1:${API_PORT}  (health: /health)"
(
  cd "$ROOT/apps/api"
  export PYTHONUNBUFFERED=1
  python3 main.py
) >"$PID_DIR/api.log" 2>&1 &
echo $! >"$PID_DIR/api.pid"

log "启动 Web → http://127.0.0.1:${WEB_PORT}"
(
  cd "$ROOT/apps/web"
  npm run dev -- --host 0.0.0.0 --port "$WEB_PORT" --strictPort
) >"$PID_DIR/web.log" 2>&1 &
echo $! >"$PID_DIR/web.pid"

# 等待健康检查
for i in $(seq 1 40); do
  if curl -sf "http://127.0.0.1:${API_PORT}/health" >/dev/null 2>&1; then
    break
  fi
  sleep 0.5
done

if curl -sf "http://127.0.0.1:${API_PORT}/health" >/dev/null 2>&1; then
  log "API 就绪"
else
  err "API 启动失败，查看 $PID_DIR/api.log"
  tail -n 40 "$PID_DIR/api.log" || true
  exit 1
fi

log "全部启动完成"
log "  Web UI : http://127.0.0.1:${WEB_PORT}"
log "  API    : http://127.0.0.1:${API_PORT}/health"
log "  日志   : $PID_DIR/api.log , $PID_DIR/web.log"
log "  停止   : ./scripts/stop.sh"
log "  Agent CLI: python3 apps/agent/run.py cli"

# 前台跟随日志（Ctrl+C 不杀后台；用 stop.sh 停止）
tail -n 0 -f "$PID_DIR/api.log" "$PID_DIR/web.log"
