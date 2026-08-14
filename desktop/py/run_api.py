#!/usr/bin/env python3
"""
桌面安装包 API 入口（PyInstaller 目标）。

不读取开发机密钥；DATA_DIR / WEB_DIST_DIR / 端口由 Electron 注入。
"""
from __future__ import annotations

import os
import sys
from pathlib import Path


def _prepare_sys_path() -> None:
    if getattr(sys, "frozen", False):
        return
    here = Path(__file__).resolve().parent
    repo = here.parents[1]
    for p in (
        repo / "apps" / "api",
        repo / "apps" / "agent",
        repo / "apps",
    ):
        s = str(p)
        if s not in sys.path:
            sys.path.insert(0, s)


def main() -> None:
    os.environ.setdefault("WORKBUDDY_DESKTOP", "1")
    os.environ.setdefault("MES_RELOAD", "false")
    os.environ.setdefault("MES_SERVER_HOST", "127.0.0.1")

    _prepare_sys_path()

    import uvicorn
    from routes_config import SERVER_PORT

    # 延迟 import，确保 path / DATA_DIR 已就绪
    from main import app  # noqa: WPS433

    host = os.getenv("MES_SERVER_HOST", "127.0.0.1")
    port = int(os.getenv("MES_SERVER_PORT", str(SERVER_PORT)))
    print(f"[workbuddy-api] http://{host}:{port}/health  DATA_DIR={os.getenv('DATA_DIR', '')}")
    uvicorn.run(app, host=host, port=port, reload=False, log_level="info")


if __name__ == "__main__":
    main()
