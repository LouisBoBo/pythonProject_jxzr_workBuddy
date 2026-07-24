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
from routes_config import DATA_DIR, SERVER_PORT

# 确保数据目录存在
for sub in ("history", "uploads", "exports", "converted"):
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

app.include_router(chat_router)
app.include_router(history_router)
app.include_router(convert_router)

app.mount("/exports", StaticFiles(directory=str(DATA_DIR / "exports")), name="exports")


@app.get("/health")
async def health():
    """健康检查。"""
    return {"status": "ok", "service": "MES Agent API", "data_dir": str(DATA_DIR)}


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
