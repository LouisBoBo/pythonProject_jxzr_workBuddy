#!/usr/bin/env bash
# 一键启动本地开发：API 探活沙箱 (8001) + API (8765) + Web (5180)
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

API_PORT="${MES_SERVER_PORT:-8765}"
WEB_PORT="${VITE_PORT:-5180}"
SANDBOX_PORT="${API_PROBE_SANDBOX_PORT:-8001}"
SANDBOX_HOST="${API_PROBE_SANDBOX_HOST:-127.0.0.1}"
# 开发默认指向本仓沙箱；已 export 的 API_PROBE_SANDBOX_URL 优先（Agent 经 dotenv 也会读 .env）
export API_PROBE_SANDBOX_URL="${API_PROBE_SANDBOX_URL:-http://${SANDBOX_HOST}:${SANDBOX_PORT}}"
export API_PROBE_SANDBOX_PORT="$SANDBOX_PORT"
export API_PROBE_SANDBOX_HOST="$SANDBOX_HOST"
export LOCAL_DEV_AGENT="${LOCAL_DEV_AGENT:-cursor_sdk}"

PID_DIR="$ROOT/.run"
mkdir -p "$PID_DIR" "$ROOT/data"/{history,uploads,exports,converted,api_calls,api_catalog}

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

stop_port "$SANDBOX_PORT"
stop_port "$API_PORT"
stop_port "$WEB_PORT"

log "启动 API 探活沙箱 → ${API_PROBE_SANDBOX_URL}  (docs: /docs , health: /health)"
(
  cd "$ROOT"
  export PYTHONUNBUFFERED=1
  export API_PROBE_SANDBOX_PORT="$SANDBOX_PORT"
  export API_PROBE_SANDBOX_HOST="$SANDBOX_HOST"
  python3 "$ROOT/apps/sandbox/server.py"
) >"$PID_DIR/sandbox.log" 2>&1 &
echo $! >"$PID_DIR/sandbox.pid"

# 等沙箱就绪
for i in $(seq 1 30); do
  if curl -sf "${API_PROBE_SANDBOX_URL}/health" >/dev/null 2>&1; then
    break
  fi
  sleep 0.25
done
if curl -sf "${API_PROBE_SANDBOX_URL}/health" >/dev/null 2>&1; then
  log "沙箱就绪（remote_url 探活将打到此地址，不碰生产 ERP）"
else
  err "沙箱启动失败，查看 $PID_DIR/sandbox.log"
  tail -n 40 "$PID_DIR/sandbox.log" || true
  exit 1
fi

# 本地无真实 ERP(:8000) 时：登录会回落沙箱；同时把沙箱 URL 显式传给 API
if ! curl -sf --connect-timeout 1 "${PLATFORM_BASE_URL:-http://127.0.0.1:8000}/health" >/dev/null 2>&1 \
  && ! curl -sf --connect-timeout 1 "${PLATFORM_BASE_URL:-http://127.0.0.1:8000}/docs" >/dev/null 2>&1; then
  log "PLATFORM_BASE_URL 不可达 → 登录将回落探活沙箱 ${API_PROBE_SANDBOX_URL}"
fi

log "启动 API → http://127.0.0.1:${API_PORT}  (health: /health)"
(
  cd "$ROOT/apps/api"
  export PYTHONUNBUFFERED=1
  export API_PROBE_SANDBOX_URL
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
log "  Web UI     : http://127.0.0.1:${WEB_PORT}"
log "  API        : http://127.0.0.1:${API_PORT}/health"
log "  探活沙箱   : ${API_PROBE_SANDBOX_URL}/docs"
log "  日志       : $PID_DIR/sandbox.log , $PID_DIR/api.log , $PID_DIR/web.log"
log "  停止       : ./scripts/stop.sh"
log "  测接口话术 : 根据 http://127.0.0.1:8000/docs 测试文档接口"
log "               （目录=用户文档；探活→沙箱 ${API_PROBE_SANDBOX_URL}）"

# 前台跟随日志（Ctrl+C 不杀后台；用 stop.sh 停止）
tail -n 0 -f "$PID_DIR/sandbox.log" "$PID_DIR/api.log" "$PID_DIR/web.log"
