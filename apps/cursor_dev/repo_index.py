"""仓结构索引缓存：减少 Cloud 探索回合（P1）。

按 repo+ref(+sha) 落盘；新会话/同会话均可复用。不替代拉仓，只压缩「找文件」。
"""
from __future__ import annotations

import json
import re
import time
import urllib.parse
from pathlib import Path
from typing import Any

from .allowlist import normalize_repo
from .github_preflight import _get_json, resolve_starting_ref

_INDEX_TTL_SEC = 6 * 3600
_MAX_PATHS = 120
_KEEP_RE = re.compile(
    r"(^|/)(src|frontend|apps/web)/|"
    r"\.(vue|tsx?|jsx?|css|scss|sass|less)$|"
    r"(layout|layouts|views|pages|components|router)",
    re.I,
)
_SKIP_RE = re.compile(
    r"(^|/)(node_modules|dist|build|\.git|vendor|target|__pycache__|\.venv)/",
    re.I,
)


def _safe_repo_key(repo: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", normalize_repo(repo) or "unknown")


def index_dir(data_dir: Path) -> Path:
    d = Path(data_dir) / "cursor_dev" / "repo_index"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _index_path(data_dir: Path, repo: str, ref: str) -> Path:
    key = f"{_safe_repo_key(repo)}__{re.sub(r'[^A-Za-z0-9._/-]+', '_', ref or 'main').replace('/', '_')}"
    return index_dir(data_dir) / f"{key}.json"


def _filter_paths(paths: list[str], *, limit: int = _MAX_PATHS) -> list[str]:
    out: list[str] = []
    for p in paths:
        s = str(p or "").replace("\\", "/").strip()
        if not s or s.endswith("/"):
            continue
        if _SKIP_RE.search(s):
            continue
        if not _KEEP_RE.search(s):
            continue
        out.append(s)
        if len(out) >= limit:
            break
    return out


def build_repo_index(repo: str, ref: str) -> dict[str, Any]:
    """从 GitHub tree API 构建精简路径索引。"""
    repo_n = normalize_repo(repo)
    ref_s = (ref or "").strip() or "main"
    empty = {
        "ok": False,
        "repo": repo_n,
        "ref": ref_s,
        "sha": "",
        "paths": [],
        "built_at": int(time.time()),
        "error": "",
    }
    if not repo_n:
        empty["error"] = "invalid repo"
        return empty
    try:
        pre = resolve_starting_ref(repo_n, ref_s)
        sha = str(pre.get("sha") or "").strip()
        use_ref = str(pre.get("ref") or ref_s)
        if not sha:
            # 退化为分支 tip 树
            ref_meta = _get_json(
                f"https://api.github.com/repos/{repo_n}/git/ref/heads/{urllib.parse.quote(use_ref)}"
            )
            if isinstance(ref_meta, dict):
                sha = str((ref_meta.get("object") or {}).get("sha") or "")
        if not sha:
            empty["error"] = "no sha"
            empty["ref"] = use_ref
            return empty
        tree = _get_json(
            f"https://api.github.com/repos/{repo_n}/git/trees/{sha}?recursive=1"
        )
        raw_paths: list[str] = []
        if isinstance(tree, dict):
            for item in tree.get("tree") or []:
                if not isinstance(item, dict):
                    continue
                if item.get("type") != "blob":
                    continue
                path = str(item.get("path") or "")
                if path:
                    raw_paths.append(path)
        # 前端相关路径优先排序
        raw_paths.sort(
            key=lambda p: (
                0 if re.search(r"(views|pages|layouts|layout)/", p, re.I) else 1,
                0 if p.endswith((".vue", ".tsx", ".css", ".scss")) else 2,
                p,
            )
        )
        paths = _filter_paths(raw_paths)
        return {
            "ok": True,
            "repo": repo_n,
            "ref": use_ref,
            "sha": sha,
            "paths": paths,
            "built_at": int(time.time()),
            "error": "",
            "truncated": bool(isinstance(tree, dict) and tree.get("truncated")),
        }
    except Exception as exc:  # noqa: BLE001
        empty["error"] = f"{type(exc).__name__}: {exc}"
        return empty


def load_cached_index(data_dir: Path, repo: str, ref: str) -> dict[str, Any] | None:
    path = _index_path(data_dir, repo, ref)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict) or not data.get("ok"):
        return None
    age = int(time.time()) - int(data.get("built_at") or 0)
    if age > _INDEX_TTL_SEC:
        return None
    return data


def save_index(data_dir: Path, index: dict[str, Any]) -> None:
    if not index.get("ok"):
        return
    repo = str(index.get("repo") or "")
    ref = str(index.get("ref") or "main")
    path = _index_path(data_dir, repo, ref)
    path.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")


def get_or_refresh_repo_index(
    data_dir: Path | None,
    repo: str,
    ref: str,
    *,
    force: bool = False,
) -> dict[str, Any]:
    repo_n = normalize_repo(repo)
    ref_s = (ref or "").strip() or "main"
    if data_dir is not None and not force:
        cached = load_cached_index(data_dir, repo_n, ref_s)
        if cached:
            return cached
    index = build_repo_index(repo_n, ref_s)
    if data_dir is not None and index.get("ok"):
        try:
            save_index(data_dir, index)
        except OSError:
            pass
    return index


def format_index_for_prompt(index: dict[str, Any] | None, *, limit: int = 60) -> str:
    if not index or not index.get("ok"):
        return ""
    paths = [str(p) for p in (index.get("paths") or []) if str(p).strip()][:limit]
    if not paths:
        return ""
    lines = "\n".join(f"  - `{p}`" for p in paths)
    return (
        "【仓库结构索引 · 只读缓存】以下为前端相关路径精简列表（非全仓）。"
        "定位文件时优先对照本列表 / glob，勿盲目从根目录遍历：\n"
        f"{lines}\n"
    )


def match_paths_by_hints(index: dict[str, Any] | None, hints: list[str], *, limit: int = 8) -> list[str]:
    if not index or not index.get("ok"):
        return []
    hints_l = [h.lower() for h in hints if h]
    if not hints_l:
        return []
    out: list[str] = []
    for p in index.get("paths") or []:
        pl = str(p).lower()
        if any(h in pl for h in hints_l):
            out.append(str(p))
            if len(out) >= limit:
                break
    return out
