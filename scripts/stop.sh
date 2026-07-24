#!/usr/bin/env bash
# 停止由 scripts/dev.sh 启动的本地服务
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PID_DIR="$ROOT/.run"
API_PORT="${MES_SERVER_PORT:-8765}"
WEB_PORT="${VITE_PORT:-5180}"

log() { printf '\033[1;34m[stop]\033[0m %s\n' "$*"; }

kill_pidfile() {
  local f="$1"
  if [[ -f "$f" ]]; then
    local pid
    pid="$(cat "$f" 2>/dev/null || true)"
    if [[ -n "${pid:-}" ]] && kill -0 "$pid" 2>/dev/null; then
      log "kill $pid ($f)"
      kill "$pid" 2>/dev/null || true
      # 杀进程组子进程（vite/npm）
      pkill -P "$pid" 2>/dev/null || true
    fi
    rm -f "$f"
  fi
}

kill_pidfile "$PID_DIR/api.pid"
kill_pidfile "$PID_DIR/web.pid"

for port in "$API_PORT" "$WEB_PORT"; do
  pids="$(lsof -tiTCP:"$port" -sTCP:LISTEN 2>/dev/null || true)"
  if [[ -n "$pids" ]]; then
    log "释放端口 $port"
    kill $pids 2>/dev/null || true
  fi
done

log "已停止"
