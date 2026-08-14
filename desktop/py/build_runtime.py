#!/usr/bin/env python3
"""
构建可分发的桌面运行时（内嵌 CPython + venv 依赖 + 业务源码）。

不使用 PyInstaller 冻结 deepagents/langchain（会误拉 torch/nltk 导致启动失败）。
产出目录：
  desktop/runtime/
    python/          # 基于 python-build-standalone 的 venv
    app/             # apps/* + 入口脚本 + 必要 docs
    bin/workbuddy-api
    bin/workbuddy-sandbox

用法（仓库根）:
  python3 desktop/py/build_runtime.py
"""
from __future__ import annotations

import os
import platform
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "desktop" / "runtime"
CACHE = OUT / "_cache"
STANDALONE_ROOT = OUT / "_cpython"
VENV = OUT / "python"
APP = OUT / "app"
BIN = OUT / "bin"

# 钉死版本，便于复现；升级时改这两处即可
CPYTHON_TAG = "20250317"
CPYTHON_VERSION = "3.12.9"


def _log(msg: str) -> None:
    print(f"[build-runtime] {msg}", flush=True)


def _run(cmd: list[str], **kwargs) -> None:
    _log("+ " + " ".join(cmd))
    subprocess.check_call(cmd, **kwargs)


def _platform_triplet() -> tuple[str, str]:
    """返回 (python-build-standalone 资产名片段, 说明)."""
    sysname = platform.system().lower()
    machine = platform.machine().lower()
    if sysname == "darwin":
        if machine in ("arm64", "aarch64"):
            return f"aarch64-apple-darwin", "macOS Apple Silicon"
        return f"x86_64-apple-darwin", "macOS Intel/Rosetta"
    if sysname == "windows":
        if machine in ("arm64", "aarch64"):
            return f"aarch64-pc-windows-msvc", "Windows ARM64"
        return f"x86_64-pc-windows-msvc", "Windows x64"
    if sysname == "linux":
        if machine in ("arm64", "aarch64"):
            return f"aarch64-unknown-linux-gnu", "Linux ARM64"
        return f"x86_64-unknown-linux-gnu", "Linux x64"
    raise RuntimeError(f"暂不支持打包平台: {sysname}/{machine}")


def _standalone_url() -> tuple[str, str]:
    triplet, _ = _platform_triplet()
    name = f"cpython-{CPYTHON_VERSION}+{CPYTHON_TAG}-{triplet}-install_only.tar.gz"
    url = (
        "https://github.com/astral-sh/python-build-standalone/releases/download/"
        f"{CPYTHON_TAG}/{name}"
    )
    return url, name


def ensure_standalone_python() -> Path:
    py = STANDALONE_ROOT / "python" / "bin" / ("python.exe" if os.name == "nt" else "python3")
    if py.is_file():
        _log(f"复用 standalone: {py}")
        return py

    url, name = _standalone_url()
    CACHE.mkdir(parents=True, exist_ok=True)
    tarball = CACHE / name
    if not tarball.is_file():
        _log(f"下载 {url}")
        urllib.request.urlretrieve(url, tarball)
    else:
        _log(f"使用缓存 {tarball}")

    if STANDALONE_ROOT.exists():
        shutil.rmtree(STANDALONE_ROOT)
    STANDALONE_ROOT.mkdir(parents=True, exist_ok=True)
    _log(f"解压 → {STANDALONE_ROOT}")
    with tarfile.open(tarball, "r:gz") as tf:
        tf.extractall(STANDALONE_ROOT)

    # install_only 解压后通常是 python/ 目录
    if not py.is_file():
        # 有的布局是顶层直接 bin/
        alt = STANDALONE_ROOT / "bin" / ("python.exe" if os.name == "nt" else "python3")
        if alt.is_file():
            return alt
        raise FileNotFoundError(f"解压后未找到 python: {py}")
    return py


def create_venv(standalone_py: Path) -> Path:
    if VENV.exists():
        shutil.rmtree(VENV)
    _run([str(standalone_py), "-m", "venv", str(VENV)])
    if os.name == "nt":
        return VENV / "Scripts" / "python.exe"
    return VENV / "bin" / "python"


def pip_install(venv_py: Path) -> None:
    req = REPO / "requirements.txt"
    _run([str(venv_py), "-m", "pip", "install", "-U", "pip", "wheel"])
    _run([str(venv_py), "-m", "pip", "install", "-r", str(req)])
    # 冒烟：干净环境不应依赖本机已装的 transformers/torch
    _run(
        [
            str(venv_py),
            "-c",
            "from deepagents import create_deep_agent; import fastapi, uvicorn; "
            "import importlib.util as u; "
            "assert u.find_spec('transformers') is None; print('runtime_import_ok')",
        ]
    )


def _copytree(src: Path, dst: Path) -> None:
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(
        src,
        dst,
        ignore=shutil.ignore_patterns(
            "__pycache__",
            "*.pyc",
            ".pytest_cache",
            "node_modules",
            ".venv",
            "large_tool_results",
            "conversation_history",
            "*.sqlite",
            "*.sqlite-*",
            ".env",
            ".env.*",
            "*.pem",
            "*.key",
        ),
    )


def sync_app_sources() -> None:
    if APP.exists():
        shutil.rmtree(APP)
    apps_dst = APP / "apps"
    apps_dst.mkdir(parents=True)
    for name in ("api", "agent", "local_dev", "cursor_dev", "sandbox"):
        src = REPO / "apps" / name
        if not src.is_dir():
            raise FileNotFoundError(src)
        _log(f"复制 apps/{name}")
        _copytree(src, apps_dst / name)

    # 入口
    py_dst = APP / "desktop" / "py"
    py_dst.mkdir(parents=True)
    for f in ("run_api.py", "run_sandbox.py"):
        shutil.copy2(REPO / "desktop" / "py" / f, py_dst / f)

    # schema 文档（可选）
    doc = REPO / "docs" / "中软MES数据库表结构.md"
    if doc.is_file():
        docs_dst = APP / "docs"
        docs_dst.mkdir(parents=True, exist_ok=True)
        shutil.copy2(doc, docs_dst / doc.name)

    # 冻结布局下让 WORKBUDDY_REPO_ROOT 指向 app/
    marker = APP / ".workbuddy_bundle"
    marker.write_text(f"repo_root={APP}\n", encoding="utf-8")


def write_launchers() -> None:
    BIN.mkdir(parents=True, exist_ok=True)
    if os.name == "nt":
        api = BIN / "workbuddy-api.cmd"
        sb = BIN / "workbuddy-sandbox.cmd"
        api.write_text(
            "@echo off\r\n"
            "set ROOT=%~dp0..\r\n"
            "set PYTHONPATH=%ROOT%\\app\\apps\\api;%ROOT%\\app\\apps\\agent;%ROOT%\\app\\apps\r\n"
            "set WORKBUDDY_REPO_ROOT=%ROOT%\\app\r\n"
            "\"%ROOT%\\python\\Scripts\\python.exe\" \"%ROOT%\\app\\desktop\\py\\run_api.py\" %*\r\n",
            encoding="utf-8",
        )
        sb.write_text(
            "@echo off\r\n"
            "set ROOT=%~dp0..\r\n"
            "set PYTHONPATH=%ROOT%\\app\\apps\\sandbox;%ROOT%\\app\\apps\r\n"
            "set WORKBUDDY_REPO_ROOT=%ROOT%\\app\r\n"
            "\"%ROOT%\\python\\Scripts\\python.exe\" \"%ROOT%\\app\\desktop\\py\\run_sandbox.py\" %*\r\n",
            encoding="utf-8",
        )
        return

    api = BIN / "workbuddy-api"
    sb = BIN / "workbuddy-sandbox"
    api.write_text(
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        'ROOT="$(cd "$(dirname "$0")/.." && pwd)"\n'
        'export PYTHONPATH="$ROOT/app/apps/api:$ROOT/app/apps/agent:$ROOT/app/apps${PYTHONPATH:+:$PYTHONPATH}"\n'
        'export WORKBUDDY_REPO_ROOT="$ROOT/app"\n'
        'exec "$ROOT/python/bin/python" "$ROOT/app/desktop/py/run_api.py" "$@"\n',
        encoding="utf-8",
    )
    sb.write_text(
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        'ROOT="$(cd "$(dirname "$0")/.." && pwd)"\n'
        'export PYTHONPATH="$ROOT/app/apps/sandbox:$ROOT/app/apps${PYTHONPATH:+:$PYTHONPATH}"\n'
        'export WORKBUDDY_REPO_ROOT="$ROOT/app"\n'
        'exec "$ROOT/python/bin/python" "$ROOT/app/desktop/py/run_sandbox.py" "$@"\n',
        encoding="utf-8",
    )
    for p in (api, sb):
        p.chmod(p.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def cleanup_old_pyinstaller() -> None:
    for name in ("workbuddy-api", "workbuddy-sandbox"):
        legacy = OUT / name
        if legacy.is_dir() and not (legacy / "bin").exists():
            # 旧 onedir 可执行文件布局
            exe = legacy / name
            if exe.exists() or (legacy / "_internal").exists():
                _log(f"移除旧 PyInstaller 产物 {legacy}")
                shutil.rmtree(legacy)


def main() -> None:
    triplet, label = _platform_triplet()
    _log(f"目标平台: {label} ({triplet})")
    OUT.mkdir(parents=True, exist_ok=True)
    cleanup_old_pyinstaller()

    standalone = ensure_standalone_python()
    venv_py = create_venv(standalone)
    pip_install(venv_py)
    sync_app_sources()
    write_launchers()

    # 体积提示
    def _du(path: Path) -> str:
        try:
            out = subprocess.check_output(["du", "-sh", str(path)], text=True)
            return out.split()[0]
        except Exception:
            return "?"

    _log(f"完成 → {OUT}")
    _log(f"  python={_du(VENV)}  app={_du(APP)}")
    _log("下一步: ./scripts/package-desktop.sh")


if __name__ == "__main__":
    main()
