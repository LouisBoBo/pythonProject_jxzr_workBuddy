"""
桌面/冻结运行时的仓库根与 Agent 根解析。

优先级：
1. 环境变量 WORKBUDDY_REPO_ROOT（Electron / 打包脚本可注入）
2. PyInstaller 冻结：sys._MEIPASS（需含 apps/agent 数据目录）
3. 源码开发：本文件向上两级（仓库根）
"""
from __future__ import annotations

import os
import sys
from pathlib import Path


def resolve_repo_root() -> Path:
    env = (os.getenv("WORKBUDDY_REPO_ROOT") or "").strip()
    if env:
        return Path(env).expanduser().resolve()

    if getattr(sys, "frozen", False):
        meipass = Path(getattr(sys, "_MEIPASS", "") or Path(sys.executable).resolve().parent)
        if (meipass / "apps" / "agent").is_dir():
            return meipass.resolve()
        exe_dir = Path(sys.executable).resolve().parent
        if (exe_dir / "apps" / "agent").is_dir():
            return exe_dir
        # onedir：可执行文件旁的 _internal
        internal = exe_dir / "_internal"
        if (internal / "apps" / "agent").is_dir():
            return internal.resolve()
        return meipass.resolve()

    return Path(__file__).resolve().parents[2]


def resolve_agent_root() -> Path:
    root = resolve_repo_root()
    candidate = root / "apps" / "agent"
    if candidate.is_dir():
        return candidate
    # 兼容扁平冻结（skills 直接在根）
    if (root / "skills").is_dir():
        return root
    return candidate
