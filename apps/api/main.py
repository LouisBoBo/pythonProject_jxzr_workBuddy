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
from routes_config import DATA_DIR, SERVER_PORT

# 确保数据目录存在
for sub in ("history", "uploads", "exports", "converted", "writes", "writes/pending"):
    os.makedirs(DATA_DIR / sub, exist_ok=True)

app = FastAPI(
    title="MES Agent API",
    description="PCB MES 自然语言运维助手 API",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(chat_router)
app.include_router(history_router)
app.include_router(convert_router)
app.include_router(writes_router)

app.mount("/exports", StaticFiles(directory=str(DATA_DIR / "exports")), name="exports")


@app.get("/health")
async def health():
    """健康检查。"""
    return {"status": "ok", "service": "MES Agent API", "data_dir": str(DATA_DIR)}


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


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=os.getenv("MES_SERVER_HOST", "0.0.0.0"),
        port=SERVER_PORT,
        reload=os.getenv("MES_RELOAD", "true").lower() in ("1", "true", "yes"),
        # 监听 agent 变更以便开发热重载
        reload_dirs=[
            str(Path(__file__).resolve().parent),
            str(Path(__file__).resolve().parents[1] / "agent"),
        ],
    )
