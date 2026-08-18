"""
MES Agent API 服务 — FastAPI 入口。

启动:
  仓库根目录: ./scripts/dev.sh
  或本目录:   python main.py

端口默认: 8765
"""
import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from routes.chat import router as chat_router
from routes.history import router as history_router
from routes.convert import router as convert_router
from routes.auth import router as auth_router
from routes.writes import router as writes_router
from routes.ide_bridge import router as ide_bridge_router
from routes.settings import router as settings_router
from routes.mes_profile import router as mes_profile_router
from routes_config import DATA_DIR, SERVER_PORT

try:
    from routes.cursor_dev import router as cursor_dev_router
except Exception as _cursor_dev_import_err:  # noqa: BLE001 — 写码旁路失败不得拖垮登录/MES
    cursor_dev_router = None
    print(f"[warn] cursor_dev router disabled: {_cursor_dev_import_err}")

try:
    from routes.local_dev import router as local_dev_router
except Exception as _local_dev_import_err:  # noqa: BLE001
    local_dev_router = None
    print(f"[warn] local_dev router disabled: {_local_dev_import_err}")

# 确保数据目录存在
for sub in (
    "history",
    "uploads",
    "exports",
    "converted",
    "writes",
    "writes/pending",
    "api_calls",
    "ide_bridge",
    "cursor_dev",
    "local_dev",
    "local_dev/jobs",
    "local_dev/sandboxes",
    "user_prefs",
    ".locks",
):
    os.makedirs(DATA_DIR / sub, exist_ok=True)

app = FastAPI(
    title="MES Agent API",
    description="PCB MES 自然语言运维助手 API",
    version="1.0.0",
)

_cors_raw = os.getenv("CORS_ALLOW_ORIGINS", "*").strip()
_cors_origins = [o.strip() for o in _cors_raw.split(",") if o.strip()] or ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(chat_router)
app.include_router(history_router)
app.include_router(convert_router)
app.include_router(writes_router)
app.include_router(ide_bridge_router)
app.include_router(settings_router)
app.include_router(mes_profile_router)
if cursor_dev_router is not None:
    app.include_router(cursor_dev_router)
if local_dev_router is not None:
    app.include_router(local_dev_router)

app.mount("/exports", StaticFiles(directory=str(DATA_DIR / "exports")), name="exports")


@app.get("/health")
async def health():
    """存活探针（负载均衡可只看此接口）。"""
    from ha.fs_lock import instance_id

    return {
        "status": "ok",
        "service": "MES Agent API",
        "data_dir": str(DATA_DIR),
        "instance_id": instance_id(),
        "pid": os.getpid(),
    }


@app.get("/health/ready")
async def health_ready():
    """就绪探针：共享 DATA_DIR 可写 + 跨进程锁可用。"""
    from ha.fs_lock import InterProcessLock, instance_id

    errors: list[str] = []
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        probe = DATA_DIR / ".locks" / f"ready-{os.getpid()}.tmp"
        probe.parent.mkdir(parents=True, exist_ok=True)
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
    except Exception as e:
        errors.append(f"data_dir: {e}")
    try:
        lock = InterProcessLock("ready-probe")
        if not lock.acquire(True, timeout=5):
            errors.append("lock: timeout")
        else:
            lock.release()
    except Exception as e:
        errors.append(f"lock: {e}")

    if errors:
        from fastapi import Response
        import json as _json

        return Response(
            content=_json.dumps(
                {"status": "not_ready", "errors": errors, "instance_id": instance_id()},
                ensure_ascii=False,
            ),
            status_code=503,
            media_type="application/json",
        )
    return {"status": "ready", "instance_id": instance_id(), "data_dir": str(DATA_DIR)}


@app.get("/api/debug/llm")
async def debug_llm():
    """诊断本进程能否解析/访问大模型（不消耗对话，便于区分 DNS vs Key）。"""
    import socket
    from urllib.request import getproxies

    from config import Config

    host = "api.deepseek.com"
    out: dict = {
        "provider": Config.LLM_PROVIDER,
        "model": Config.MODEL_NAME,
        "base_url": Config.DEEPSEEK_BASE_URL,
        "has_api_key": bool(Config.DEEPSEEK_API_KEY),
        "proxies": getproxies(),
        "pid": os.getpid(),
    }
    try:
        infos = socket.getaddrinfo(host, 443)
        out["dns"] = {"ok": True, "addr": infos[0][4]}
    except Exception as e:
        out["dns"] = {"ok": False, "error": f"{type(e).__name__}: {e}"}
        return out

    try:
        import httpx

        url = Config.DEEPSEEK_BASE_URL.rstrip("/") + "/models"
        async with httpx.AsyncClient(timeout=20.0, trust_env=True) as client:
            r = await client.get(
                url,
                headers={"Authorization": f"Bearer {Config.DEEPSEEK_API_KEY}"},
            )
        out["models"] = {"ok": r.status_code == 200, "status_code": r.status_code}
        if r.status_code != 200:
            out["models"]["body"] = (r.text or "")[:200]
    except Exception as e:
        root = e
        cur: BaseException | None = e
        seen: set[int] = set()
        while cur is not None and id(cur) not in seen:
            seen.add(id(cur))
            nxt = cur.__cause__ or cur.__context__
            if nxt is None:
                break
            cur = nxt
            root = nxt
        out["models"] = {
            "ok": False,
            "error": f"{type(e).__name__}: {e}",
            "root": f"{type(root).__name__}: {root}",
        }
    return out


def _mount_web_dist_if_configured(application: FastAPI) -> None:
    """仅当 WEB_DIST_DIR 指向有效 dist 时挂载静态前端（桌面同 origin；dev.sh 不设此变量）。

    约束：必须在全部 API 路由注册之后调用，保证 /api、/health、/exports、/docs 优先。
    """
    raw = (os.getenv("WEB_DIST_DIR") or "").strip()
    if not raw:
        return
    dist = Path(raw).expanduser().resolve()
    index_file = dist / "index.html"
    if not dist.is_dir() or not index_file.is_file():
        print(f"[warn] WEB_DIST_DIR 无效，跳过静态托管: {dist}")
        return

    from fastapi import HTTPException
    from fastapi.responses import FileResponse

    assets = dist / "assets"
    if assets.is_dir():
        application.mount("/assets", StaticFiles(directory=str(assets)), name="web-assets")

    # SPA 常见根文件（favicon 等）；不在此列的路径回落 index.html
    _spa_root_files = {
        "favicon.ico",
        "robots.txt",
        "manifest.webmanifest",
        "manifest.json",
    }

    def _safe_file_under_dist(rel: str) -> Path | None:
        if not rel or "\x00" in rel:
            return None
        parts = [p for p in rel.replace("\\", "/").split("/") if p not in ("", ".")]
        if any(p == ".." for p in parts):
            return None
        # 禁止从 dist 直接吐出敏感文件名（即使被误打进包）
        base_name = parts[-1].lower() if parts else ""
        if base_name in {".env", ".env.local", ".env.production", ".pem", ".key"} or base_name.endswith(
            (".pem", ".key")
        ):
            return None
        if base_name.startswith(".env"):
            return None
        candidate = (dist.joinpath(*parts)).resolve()
        try:
            candidate.relative_to(dist)
        except ValueError:
            return None
        return candidate if candidate.is_file() else None

    @application.get(
        "/",
        include_in_schema=False,
        summary="桌面/打包前端首页",
        description="仅 WEB_DIST_DIR 启用时提供；开发态请用 Vite :5180。",
    )
    async def spa_index():
        return FileResponse(index_file)

    @application.get(
        "/{full_path:path}",
        include_in_schema=False,
        summary="SPA 路由回落",
        description="非 API/静态资源路径返回 index.html，供 Vue Router history 模式。",
    )
    async def spa_fallback(full_path: str):
        # 绝不可吞掉已有服务路径（即便路由表未命中也应 404，勿回落 HTML）
        first = (full_path or "").split("/", 1)[0]
        if first in {
            "api",
            "health",
            "exports",
            "docs",
            "redoc",
            "openapi.json",
            "assets",
        } or full_path in {"openapi.json", "docs", "redoc"}:
            raise HTTPException(status_code=404, detail="Not Found")

        if full_path in _spa_root_files or "/" not in full_path:
            hit = _safe_file_under_dist(full_path)
            if hit is not None:
                return FileResponse(hit)

        # 子路径若真实存在（如 public 拷贝），直接返回文件
        hit = _safe_file_under_dist(full_path)
        if hit is not None:
            return FileResponse(hit)

        return FileResponse(index_file)

    flag = "desktop" if os.getenv("WORKBUDDY_DESKTOP", "").strip() in ("1", "true", "yes") else "packaged"
    print(f"[info] WEB_DIST_DIR 已挂载 ({flag}): {dist}")


_mount_web_dist_if_configured(app)


if __name__ == "__main__":
    import uvicorn

    # 桌面壳默认关闭 uvicorn reload，避免子进程双开抢端口
    _reload_default = "false" if os.getenv("WORKBUDDY_DESKTOP", "").lower() in ("1", "true", "yes") else "true"
    uvicorn.run(
        "main:app",
        host=os.getenv("MES_SERVER_HOST", "0.0.0.0"),
        port=SERVER_PORT,
        reload=os.getenv("MES_RELOAD", _reload_default).lower() in ("1", "true", "yes"),
        # 监听 agent 变更以便开发热重载
        reload_dirs=[
            str(Path(__file__).resolve().parent),
            str(Path(__file__).resolve().parents[1] / "agent"),
            str(Path(__file__).resolve().parents[1] / "cursor_dev"),
            str(Path(__file__).resolve().parents[1] / "local_dev"),
        ],
    )
