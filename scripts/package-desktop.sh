#!/usr/bin/env bash
# 产出完整桌面安装包：前端 dist + 内嵌 Python 运行时 + Electron 安装包。
# 安装后同事只需在「系统配置」填写 Key / ERP，无需本机 Python / 克隆仓库。
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

log() { printf '\033[1;34m[package-desktop]\033[0m %s\n' "$*"; }
err() { printf '\033[1;31m[package-desktop]\033[0m %s\n' "$*" >&2; }

need_cmd() {
  command -v "$1" >/dev/null 2>&1 || { err "缺少命令: $1"; exit 1; }
}

need_cmd npm
need_cmd python3

if [[ -f "$ROOT/.env" ]]; then
  log "提醒：不会把 .env 打进安装包；Key/ERP 由用户在界面配置"
fi

SKIP_RUNTIME="${SKIP_RUNTIME:-0}"
SKIP_WEB="${SKIP_WEB:-0}"

if [[ "$SKIP_WEB" != "1" ]]; then
  log "1/3 构建前端 apps/web/dist ..."
  (cd "$ROOT/apps/web" && npm install && npm run build)
fi
test -f "$ROOT/apps/web/dist/index.html" || { err "缺少 apps/web/dist/index.html"; exit 1; }

if [[ "$SKIP_RUNTIME" != "1" ]]; then
  log "2/3 构建内嵌运行时（standalone CPython + venv + apps）→ desktop/runtime/ ..."
  python3 "$ROOT/desktop/py/build_runtime.py"
fi

API_BIN="$ROOT/desktop/runtime/bin/workbuddy-api"
SANDBOX_BIN="$ROOT/desktop/runtime/bin/workbuddy-sandbox"
if [[ -f "${API_BIN}.cmd" ]]; then API_BIN="${API_BIN}.cmd"; fi
if [[ -f "${SANDBOX_BIN}.cmd" ]]; then SANDBOX_BIN="${SANDBOX_BIN}.cmd"; fi

test -e "$API_BIN" || { err "缺少 $API_BIN（先跑 build_runtime）"; exit 1; }
test -e "$SANDBOX_BIN" || { err "缺少 $SANDBOX_BIN"; exit 1; }
test -d "$ROOT/desktop/runtime/python" || { err "缺少 desktop/runtime/python"; exit 1; }
test -d "$ROOT/desktop/runtime/app/apps/api" || { err "缺少 desktop/runtime/app"; exit 1; }

log "3/3 electron-builder ..."
# 国内网络下 Electron 官方源易中断，默认走 npmmirror（可 export 覆盖）
export ELECTRON_MIRROR="${ELECTRON_MIRROR:-https://npmmirror.com/mirrors/electron/}"
export ELECTRON_BUILDER_BINARIES_MIRROR="${ELECTRON_BUILDER_BINARIES_MIRROR:-https://npmmirror.com/mirrors/electron-builder-binaries/}"
(cd "$ROOT/desktop" && npm install)
TARGET="${1:-}"
(
  cd "$ROOT/desktop"
  if [[ -n "$TARGET" ]]; then
    npx electron-builder --"$TARGET"
  else
    npx electron-builder
  fi
)

log "完成。安装包目录: $ROOT/desktop/release"
log "产物名：ZR WorkBuddy（见 desktop/package.json productName）"
log "同事：安装 → 打开 → 系统配置填写 LLM Key（及可选 ERP）→ 登录使用"
log "macOS 未签名时：若拦截，请右键打开一次。"
