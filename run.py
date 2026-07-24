#!/usr/bin/env python3
"""仓库根启动入口（兼容旧命令）。

用法:
  python run.py              # demo
  python run.py cli          # Agent CLI
  python run.py agent "..."  # 单次调用
  python run.py api          # 仅 API
  python run.py web          # 仅提示用 npm
  python run.py dev          # 一键开发（调用 scripts/dev.sh）
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
AGENT_RUN = ROOT / "apps" / "agent" / "run.py"


def main() -> None:
    if len(sys.argv) < 2:
        cmd = "demo"
        rest: list[str] = []
    else:
        cmd = sys.argv[1]
        rest = sys.argv[2:]

    if cmd == "dev":
        os.execv("/bin/bash", ["bash", str(ROOT / "scripts" / "dev.sh")])

    if cmd == "stop":
        os.execv("/bin/bash", ["bash", str(ROOT / "scripts" / "stop.sh")])

    if cmd == "api":
        os.chdir(ROOT / "apps" / "api")
        os.execv(sys.executable, [sys.executable, "main.py"])

    if cmd in ("demo", "agent", "cli"):
        env = os.environ.copy()
        env["PYTHONPATH"] = str(ROOT / "apps" / "agent") + os.pathsep + env.get("PYTHONPATH", "")
        raise SystemExit(
            subprocess.call([sys.executable, str(AGENT_RUN), cmd, *rest], env=env, cwd=str(ROOT))
        )

    if cmd == "web":
        print("请运行: cd apps/web && npm run dev")
        print("或一键: ./scripts/dev.sh")
        raise SystemExit(0)

    print(f"未知命令: {cmd}")
    print("用法: python run.py [demo|agent|cli|api|dev|stop]")
    raise SystemExit(1)


if __name__ == "__main__":
    main()
