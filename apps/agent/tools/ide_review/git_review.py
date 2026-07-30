"""服务端/同机 Git 或本地目录只读审核（Bridge 离线时的降级路径）。"""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Callable

from tools.ide_review.enrich import augment_findings_from_contents
from tools.ide_review.local_files import read_workspace_files

_SOURCE_SUFFIXES = {".java", ".js", ".ts", ".tsx", ".py", ".go", ".kt", ".vue"}
_SKIP_DIRS = {
    ".git",
    "node_modules",
    "target",
    "dist",
    "build",
    ".idea",
    ".vscode",
    "__pycache__",
    "venv",
    ".venv",
}


def _discover_files(root: Path, paths: list[str] | None, limit: int = 12) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()

    def add(rel: str) -> None:
        if not rel or rel in seen or len(out) >= limit:
            return
        abs_path = root / rel
        if abs_path.is_file():
            seen.add(rel)
            out.append(rel)

    raw = [str(p).strip() for p in (paths or []) if p and str(p).strip()]
    for item in raw:
        p = Path(item)
        if p.is_absolute():
            try:
                rel = p.resolve().relative_to(root.resolve()).as_posix()
            except ValueError:
                continue
        else:
            rel = Path(item).as_posix()
        cand = root / rel
        if cand.is_file():
            add(rel)
        elif cand.is_dir():
            for f in cand.rglob("*"):
                if not f.is_file():
                    continue
                if f.suffix.lower() not in _SOURCE_SUFFIXES:
                    continue
                if any(part in _SKIP_DIRS for part in f.parts):
                    continue
                add(f.relative_to(root).as_posix())
                if len(out) >= limit:
                    return out

    if out:
        return out

    for seed in ("src/main/java", "src", "app", "apps", "."):
        base = root if seed == "." else root / seed
        if not base.is_dir():
            continue
        for f in base.rglob("*"):
            if not f.is_file():
                continue
            if f.suffix.lower() not in _SOURCE_SUFFIXES:
                continue
            if any(part in _SKIP_DIRS for part in f.relative_to(root).parts):
                continue
            add(f.relative_to(root).as_posix())
            if len(out) >= limit:
                return out
        if out:
            break
    return out


def _prepare_workspace(
    *,
    local_path: str = "",
    repo_url: str = "",
    ref: str = "",
) -> tuple[Path, dict[str, Any], Callable[[], None] | None]:
    """返回 (workspace_root, meta, cleanup)。cleanup 可为 None。"""
    local = (local_path or "").strip()
    if local:
        root = Path(local).expanduser().resolve()
        if not root.is_dir():
            raise FileNotFoundError(f"本地目录不存在: {local}")
        return (
            root,
            {"mode": "local_path", "workspace_root": str(root), "ref": ref or ""},
            None,
        )

    url = (repo_url or "").strip()
    if not url:
        raise ValueError("请提供 local_path（本机目录）或 repo_url（Git 地址）")

    # 安全：仅允许常见 git URL 形态，避免任意 shell
    if not (
        url.startswith("https://")
        or url.startswith("git@")
        or url.startswith("ssh://")
        or url.startswith("http://127.")
        or url.startswith("http://localhost")
    ):
        raise ValueError("repo_url 仅支持 https/ssh 或本机 http")

    td = tempfile.mkdtemp(prefix="wb-git-review-")
    root = Path(td)
    cmd = ["git", "clone", "--depth", "1"]
    if ref.strip():
        cmd.extend(["--branch", ref.strip()])
    cmd.extend([url, str(root)])
    try:
        subprocess.run(
            cmd,
            check=True,
            capture_output=True,
            text=True,
            timeout=float(os.getenv("IDE_GIT_CLONE_TIMEOUT_SEC", "90") or "90"),
        )
    except subprocess.CalledProcessError as e:
        shutil.rmtree(td, ignore_errors=True)
        err = (e.stderr or e.stdout or str(e)).strip()[:500]
        raise RuntimeError(f"git clone 失败: {err}") from e
    except Exception:
        shutil.rmtree(td, ignore_errors=True)
        raise

    def cleanup() -> None:
        shutil.rmtree(td, ignore_errors=True)

    return (
        root,
        {
            "mode": "git_clone",
            "repo_url": url,
            "ref": ref or "default",
            "workspace_root": str(root),
        },
        cleanup,
    )


def run_git_or_local_review(
    *,
    local_path: str = "",
    repo_url: str = "",
    ref: str = "",
    paths: list[str] | None = None,
    prompt: str = "",
) -> dict[str, Any]:
    cleanup = None
    try:
        root, meta, cleanup = _prepare_workspace(
            local_path=local_path, repo_url=repo_url, ref=ref
        )
        files = _discover_files(root, paths)
        if not files:
            return {
                "status": "error",
                "provider": "git_review",
                "message": "未找到可审源码文件",
                "findings": [],
                "file_contents": [],
                "files": [],
                "hint": "请传 paths，或确认目录下有 .java/.js/.py 等源文件",
                **meta,
            }
        packed = read_workspace_files(root, files)
        result: dict[str, Any] = {
            "status": "ok",
            "provider": "git_review",
            "findings": [],
            "file_contents": packed.get("file_contents") or [],
            "files": packed.get("files") or files,
            "errors": packed.get("errors") or [],
            "prompt": (prompt or "")[:200],
            "raw_summary": f"git/local 审核：扫描 {len(files)} 个文件",
            "hint": "请基于 file_contents 与 findings 按固定模板写报告；Bridge 在线时优先 request_ide_review。",
            **meta,
        }
        result = augment_findings_from_contents(result)
        n = len(result.get("findings") or [])
        result["raw_summary"] = (
            f"git/local 审核：{len(files)} 个文件，规则发现 {n} 条；"
            f"模式={meta.get('mode')}"
        )
        result["diagnostics_count"] = result.get("diagnostics_count") or {
            "P0": 0,
            "P1": 0,
            "P2": 0,
        }
        return result
    finally:
        if cleanup:
            cleanup()
