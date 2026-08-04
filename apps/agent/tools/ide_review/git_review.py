"""服务端/同机 Git 或本地目录只读审核。

公开 HTTPS 仓库审核为一等公民车道；支持按 thread 缓存 clone，
走 list → read_batch 全仓分批（对齐 IDE），也保留单次抽样 request_git_review。
一期仅支持公开 https://（及本机 http 开发），不支持 SSH / 私有仓凭证。
"""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import threading
import time
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

# 单次抽样上限（仅 request_git_review 一次性路径；分批走 list_workspace_source_files）
_DEFAULT_FILE_LIMIT = int(os.getenv("IDE_GIT_REVIEW_FILE_LIMIT", "30") or "30")
_WORKSPACE_TTL_SEC = float(os.getenv("IDE_GIT_WORKSPACE_TTL_SEC", "3600") or "3600")

_HTTPS_ONLY_HINT = (
    "一期仅支持公开 HTTPS 仓库（https://…）。"
    "不支持 SSH（git@ / ssh://）、私有仓 Token，也不接受任意 http。"
)

_ws_lock = threading.Lock()
# thread_id -> {root, cleanup, repo_url, ref, local_path, mode, saved_at, meta}
_WORKSPACES: dict[str, dict[str, Any]] = {}


def _normalize_repo_url(repo_url: str) -> str:
    """去掉尾部中文/标点等粘连字符，保留干净的 https 仓库地址。"""
    url = (repo_url or "").strip()
    url = url.rstrip(".,;:)+]}>\"'`")
    # 「.git仓库代码」→ 截到 .git
    lower = url.lower()
    git_idx = lower.find(".git")
    if git_idx >= 0:
        url = url[: git_idx + 4]
    else:
        # 从首个非 URL 安全字符截断（常见：中文说明粘在末尾）
        cleaned: list[str] = []
        for ch in url:
            o = ord(ch)
            if ch.isascii() and (
                ch.isalnum() or ch in "-._~:/?#[]@!$&'()*+,;=%"
            ):
                cleaned.append(ch)
            elif o > 127:
                break
            else:
                break
        url = "".join(cleaned).rstrip("/")
    return url.rstrip("/")


def validate_public_https_repo_url(repo_url: str) -> str:
    """校验并返回规范化的公开 HTTPS repo_url；非法则抛 ValueError。"""
    url = _normalize_repo_url(repo_url)
    if not url:
        raise ValueError("请提供 repo_url（公开 HTTPS Git 地址）")

    lower = url.lower()
    if lower.startswith("git@") or lower.startswith("ssh://"):
        raise ValueError(f"不支持 SSH 地址。{_HTTPS_ONLY_HINT}")

    if url.startswith("http://127.") or url.startswith("http://localhost"):
        return url

    if not url.startswith("https://"):
        raise ValueError(f"repo_url 非法。{_HTTPS_ONLY_HINT}")

    # 拒绝 URL 内嵌凭证（https://user:token@host/...）
    rest = url[len("https://") :]
    if "@" in rest.split("/", 1)[0]:
        raise ValueError("请勿在 URL 中嵌入账号或 Token。" + _HTTPS_ONLY_HINT)

    # 路径中不允许非 ASCII（防止规范化后仍混入异常字符）
    if any(ord(c) > 127 for c in url):
        raise ValueError(
            "仓库地址含非法字符。请只粘贴纯 HTTPS 链接，例如 "
            "https://github.com/org/repo.git"
        )
    return url


def _discover_files(
    root: Path, paths: list[str] | None, limit: int | None = None
) -> list[str]:
    if limit is None:
        limit = max(1, _DEFAULT_FILE_LIMIT)
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

    url = validate_public_https_repo_url(repo_url)

    td = tempfile.mkdtemp(prefix="wb-git-review-")
    root = Path(td)
    timeout_sec = float(os.getenv("IDE_GIT_CLONE_TIMEOUT_SEC", "300") or "300")
    # 浅克隆 + 单分支，加快公开仓拉取；禁止交互式要密码（避免假死）
    cmd = [
        "git",
        "-c",
        "credential.helper=",
        "-c",
        "http.version=HTTP/1.1",
        "clone",
        "--depth",
        "1",
        "--single-branch",
    ]
    if ref.strip():
        cmd.extend(["--branch", ref.strip()])
    cmd.extend([url, str(root)])
    env = os.environ.copy()
    env["GIT_TERMINAL_PROMPT"] = "0"
    env["GIT_ASKPASS"] = "echo"
    env["GCM_INTERACTIVE"] = "never"

    last_err: BaseException | None = None
    for attempt in range(2):
        try:
            subprocess.run(
                cmd,
                check=True,
                capture_output=True,
                text=True,
                timeout=timeout_sec,
                env=env,
            )
            last_err = None
            break
        except subprocess.TimeoutExpired as e:
            last_err = e
            shutil.rmtree(td, ignore_errors=True)
            if attempt == 0:
                td = tempfile.mkdtemp(prefix="wb-git-review-")
                root = Path(td)
                cmd[-1] = str(root)
                continue
            raise RuntimeError(
                f"克隆公开仓库超时（>{int(timeout_sec)}s）。"
                "请检查本机到 GitHub 的网络/代理/VPN，或稍后点「重新开始审核」。"
                f"仓库：{url}"
            ) from e
        except subprocess.CalledProcessError as e:
            shutil.rmtree(td, ignore_errors=True)
            err = (e.stderr or e.stdout or str(e)).strip()[:500]
            low = err.lower()
            if any(
                k in low
                for k in (
                    "authentication failed",
                    "could not read username",
                    "permission denied",
                    "repository not found",
                    "access denied",
                    "403",
                    "401",
                )
            ):
                raise RuntimeError(
                    f"无法克隆仓库（可能是私有仓或不存在）。{_HTTPS_ONLY_HINT} 详情: {err}"
                ) from e
            # 网络类错误：重试一次
            if attempt == 0 and any(
                k in low
                for k in (
                    "could not resolve",
                    "failed to connect",
                    "connection timed out",
                    "ssl",
                    "network",
                    "early eof",
                    "rpc failed",
                )
            ):
                last_err = e
                td = tempfile.mkdtemp(prefix="wb-git-review-")
                root = Path(td)
                cmd[-1] = str(root)
                continue
            raise RuntimeError(f"git clone 失败: {err}") from e
        except Exception:
            shutil.rmtree(td, ignore_errors=True)
            raise

    if last_err is not None:
        # 防御：循环应已 raise；避免留下空临时目录
        shutil.rmtree(td, ignore_errors=True)
        raise RuntimeError(f"git clone 失败: {last_err}") from last_err

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


def _ws_key(thread_id: str) -> str:
    return str(thread_id or "").strip() or "_default"


def _release_workspace_unlocked(key: str) -> None:
    entry = _WORKSPACES.pop(key, None)
    if not entry:
        return
    cleanup = entry.get("cleanup")
    if callable(cleanup):
        try:
            cleanup()
        except Exception:
            pass


def release_git_workspace(thread_id: str) -> None:
    """释放某会话缓存的 clone 目录。"""
    with _ws_lock:
        _release_workspace_unlocked(_ws_key(thread_id))


def ensure_git_workspace(
    thread_id: str,
    *,
    local_path: str = "",
    repo_url: str = "",
    ref: str = "",
) -> dict[str, Any]:
    """按 thread 缓存工作区：同 url/ref/local_path 复用，变更则重新 clone。

    返回 {workspace_root, mode, repo_url, ref, reused}。
    """
    key = _ws_key(thread_id)
    local = (local_path or "").strip()
    url = validate_public_https_repo_url(repo_url) if (repo_url or "").strip() else ""
    ref_n = (ref or "").strip()
    if not local and not url:
        raise ValueError("请提供 local_path 或 repo_url")

    now = time.time()
    with _ws_lock:
        # 清理过期
        expired = [
            k
            for k, v in _WORKSPACES.items()
            if now - float(v.get("saved_at") or 0) > _WORKSPACE_TTL_SEC
        ]
        for k in expired:
            _release_workspace_unlocked(k)

        cur = _WORKSPACES.get(key)
        if cur:
            same = (
                str(cur.get("local_path") or "") == local
                and str(cur.get("repo_url") or "") == url
                and str(cur.get("ref") or "") == ref_n
            )
            root_ok = Path(str(cur.get("root") or "")).is_dir()
            if same and root_ok and now - float(cur.get("saved_at") or 0) <= _WORKSPACE_TTL_SEC:
                cur["saved_at"] = now
                meta = dict(cur.get("meta") or {})
                return {
                    "workspace_root": str(cur["root"]),
                    "reused": True,
                    **meta,
                }
            _release_workspace_unlocked(key)

    root, meta, cleanup = _prepare_workspace(
        local_path=local, repo_url=url, ref=ref_n
    )
    with _ws_lock:
        _WORKSPACES[key] = {
            "root": str(root),
            "cleanup": cleanup,
            "local_path": local,
            "repo_url": url,
            "ref": ref_n,
            "mode": meta.get("mode"),
            "meta": meta,
            "saved_at": time.time(),
        }
    return {"workspace_root": str(root), "reused": False, **meta}


def get_git_workspace_root(thread_id: str) -> str:
    """取当前会话已缓存的工作区根路径；无则空串。"""
    key = _ws_key(thread_id)
    now = time.time()
    with _ws_lock:
        cur = _WORKSPACES.get(key)
        if not cur:
            return ""
        if now - float(cur.get("saved_at") or 0) > _WORKSPACE_TTL_SEC:
            _release_workspace_unlocked(key)
            return ""
        root = str(cur.get("root") or "")
        if not root or not Path(root).is_dir():
            _release_workspace_unlocked(key)
            return ""
        cur["saved_at"] = now
        return root


def run_git_or_local_review(
    *,
    local_path: str = "",
    repo_url: str = "",
    ref: str = "",
    paths: list[str] | None = None,
    prompt: str = "",
) -> dict[str, Any]:
    """一次性抽样审核（兼容旧路径）。全仓请用 list → read_batch。"""
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
                "hint": (
                    "全仓请改走 request_git_list_source_files → "
                    "request_git_read_batch；或传 paths 限制范围"
                ),
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
            "raw_summary": f"git/local 抽样审核：扫描 {len(files)} 个文件",
            "hint": (
                "此为单次抽样。全仓核心功能代码请走 "
                "request_git_list_source_files → request_git_read_batch(0..N-1) → 终稿。"
            ),
            "next_step": (
                "若用户要审整个公开仓库，请改用分批流程，勿仅用本工具结案。"
            ),
            **meta,
        }
        result = augment_findings_from_contents(result)
        n = len(result.get("findings") or [])
        result["raw_summary"] = (
            f"git/local 抽样：{len(files)} 个文件，规则发现 {n} 条；"
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
