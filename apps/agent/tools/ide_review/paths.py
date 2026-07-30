"""仓库相对路径校验：拒绝穿越与绝对路径。"""
from __future__ import annotations

from pathlib import Path


def resolve_repo_paths(
    repo_root: Path,
    paths: list[str] | None,
    *,
    default_paths: list[str],
) -> tuple[list[Path], list[str]]:
    """返回 (resolved_files, errors)。

    允许 repo_root 下的相对路径，或位于 repo_root 内的绝对路径；拒绝 ``..`` 穿越。
    """
    root = repo_root.resolve()
    raw = [p.strip() for p in (paths or []) if p and str(p).strip()]
    if not raw:
        raw = list(default_paths)

    resolved: list[Path] = []
    errors: list[str] = []
    for item in raw:
        p = Path(item)
        if p.is_absolute():
            candidate = p.resolve()
            try:
                candidate.relative_to(root)
            except ValueError:
                errors.append(f"路径不在仓库内: {item}")
                continue
        else:
            if ".." in Path(item).parts:
                errors.append(f"拒绝路径穿越: {item}")
                continue
            candidate = (root / item).resolve()
            try:
                candidate.relative_to(root)
            except ValueError:
                errors.append(f"路径不在仓库内: {item}")
                continue
        if not candidate.is_file():
            errors.append(f"文件不存在: {item}")
            continue
        resolved.append(candidate)
    return resolved, errors


def rel_posix(repo_root: Path, path: Path) -> str:
    return path.resolve().relative_to(repo_root.resolve()).as_posix()
