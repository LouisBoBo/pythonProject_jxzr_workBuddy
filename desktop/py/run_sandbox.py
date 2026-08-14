#!/usr/bin/env python3
"""桌面安装包探活沙箱入口（PyInstaller 目标）。"""
from __future__ import annotations

import os
import sys
from pathlib import Path


def main() -> None:
    os.environ.setdefault("WORKBUDDY_DESKTOP", "1")
    if not getattr(sys, "frozen", False):
        sandbox_dir = Path(__file__).resolve().parents[2] / "apps" / "sandbox"
        s = str(sandbox_dir)
        if s not in sys.path:
            sys.path.insert(0, s)
    from server import main as sandbox_main  # noqa: WPS433

    sandbox_main()


if __name__ == "__main__":
    main()
