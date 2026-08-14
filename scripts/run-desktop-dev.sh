#!/usr/bin/env bash
# 桌面壳开发启动（不打包）：先确保 web dist，再 Electron 拉起系统 Python API。
# 不影响 scripts/dev.sh 网页联调（端口默认 18765 / 18001）。
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

log() { printf '\033[1;34m[desktop-dev]\033[0m %s\n' "$*"; }
err() { printf '\033[1;31m[desktop-dev]\033[0m %s\n' "$*" >&2; }

need_cmd() {
  command -v "$1" >/dev/null 2>&1 || { err "缺少命令: $1"; exit 1; }
}

need_cmd python3
need_cmd npm

export WORKBUDDY_REPO_ROOT="$ROOT"

if [[ ! -f "$ROOT/apps/web/dist/index.html" ]]; then
  log "构建前端 dist..."
  (cd "$ROOT/apps/web" && npm install && npm run build)
else
  log "已有 apps/web/dist，跳过 build（强制重建: FORCE_WEB_BUILD=1）"
  if [[ "${FORCE_WEB_BUILD:-0}" == "1" ]]; then
    (cd "$ROOT/apps/web" && npm run build)
  fi
fi

if [[ ! -d "$ROOT/desktop/node_modules/electron" ]]; then
  log "安装 desktop 依赖..."
  (cd "$ROOT/desktop" && npm install)
fi

log "启动 Electron（优先 desktop/runtime 冻结二进制；否则系统 python3）"
cd "$ROOT/desktop"
exec npm start
