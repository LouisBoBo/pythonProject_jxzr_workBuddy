"""目录沙箱：创建、受限拷贝、闸门、同步到目标。"""
from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any, Callable

from .config import (
    COPY_SKIP_DIR_NAMES,
    LocalDevConfig,
    SENSITIVE_BASENAMES,
    SENSITIVE_PATH_PARTS,
    SENSITIVE_SUFFIXES,
    get_config,
)


def sandboxes_dir(data_dir: Path) -> Path:
    d = Path(data_dir) / "local_dev" / "sandboxes"
    d.mkdir(parents=True, exist_ok=True)
    return d


def sandbox_root(data_dir: Path, job_id: str) -> Path:
    safe = "".join(c for c in job_id if c.isalnum() or c in "-_")
    if not safe or safe != job_id:
        raise ValueError("invalid job_id")
    root = sandboxes_dir(data_dir) / safe
    root.mkdir(parents=True, exist_ok=True)
    return root.resolve()


def is_sensitive_rel(rel: str) -> bool:
    parts = Path(rel.replace("\\", "/")).parts
    if not parts:
        return False
    for part in parts:
        if part in SENSITIVE_PATH_PARTS:
            return True
        if part in SENSITIVE_BASENAMES:
            return True
        lower = part.lower()
        if any(lower.endswith(suf) for suf in SENSITIVE_SUFFIXES):
            return True
    return False


def resolve_in_sandbox(sandbox: Path, rel: str) -> Path:
    """相对路径解析到沙箱内；防 ../ 逃逸。"""
    raw = (rel or "").strip().replace("\\", "/")
    if not raw or raw.startswith("/") or raw.startswith("~"):
        raise ValueError("只允许沙箱内相对路径")
    if ".." in Path(raw).parts:
        raise ValueError("路径不允许包含 ..")
    target = (sandbox / raw).resolve()
    root = sandbox.resolve()
    try:
        target.relative_to(root)
    except ValueError as e:
        raise ValueError("路径逃逸出沙箱") from e
    return target


def prepare_sandbox(
    data_dir: Path,
    job_id: str,
    target_workspace: Path,
    *,
    empty_target: bool,
    cfg: LocalDevConfig | None = None,
    on_progress: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    """创建沙箱：空目标 → 空仓；非空 → 受限拷贝。"""
    cfg = cfg or get_config()
    root = sandbox_root(data_dir, job_id)
    # 清空旧内容
    if root.exists():
        for child in root.iterdir():
            if child.is_dir():
                shutil.rmtree(child, ignore_errors=True)
            else:
                try:
                    child.unlink()
                except OSError:
                    pass
    root.mkdir(parents=True, exist_ok=True)

    if empty_target:
        if on_progress:
            on_progress("沙箱已就绪（空项目）")
        return {"sandbox": str(root), "copied_files": 0, "mode": "empty"}

    copied = 0
    total_bytes = 0
    skipped_dirs = 0
    if on_progress:
        on_progress("正在将目标工程受限拷贝到沙箱…")

    for dirpath, dirnames, filenames in os_walk_filtered(target_workspace):
        rel_dir = Path(dirpath).relative_to(target_workspace)
        # 原地过滤 dirnames
        keep: list[str] = []
        for d in list(dirnames):
            if d in COPY_SKIP_DIR_NAMES or d.startswith(".git"):
                skipped_dirs += 1
                continue
            keep.append(d)
        dirnames[:] = keep

        dest_dir = root / rel_dir if str(rel_dir) != "." else root
        dest_dir.mkdir(parents=True, exist_ok=True)

        for name in filenames:
            if copied >= cfg.copy_max_files:
                raise RuntimeError(
                    f"工程文件过多（>{cfg.copy_max_files}），请缩小目录或排除依赖后再试"
                )
            src = Path(dirpath) / name
            rel = str((rel_dir / name).as_posix() if str(rel_dir) != "." else name)
            if is_sensitive_rel(rel):
                continue
            try:
                size = src.stat().st_size
            except OSError:
                continue
            if size > cfg.max_file_bytes:
                continue
            if total_bytes + size > cfg.copy_max_total_bytes:
                raise RuntimeError("工程体积过大，无法完整拷入沙箱")
            dest = root / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            try:
                shutil.copy2(src, dest)
            except OSError:
                continue
            copied += 1
            total_bytes += size

    if on_progress:
        on_progress(f"沙箱拷贝完成：{copied} 个文件")
    return {
        "sandbox": str(root),
        "copied_files": copied,
        "skipped_dir_hits": skipped_dirs,
        "mode": "copy",
        "total_bytes": total_bytes,
    }


def os_walk_filtered(root: Path):
    import os

    yield from os.walk(root)


def sync_changed_to_target(
    sandbox: Path,
    target: Path,
    changed_rels: list[str],
    *,
    cfg: LocalDevConfig | None = None,
) -> list[str]:
    """将变更相对路径从沙箱同步到目标；返回实际写入列表。

    - 先校验再写入；单文件先写临时文件再 replace，降低半截文件风险
    - 应同步却缺失的非敏感文件会抛错，避免静默丢变更
    """
    import os

    cfg = cfg or get_config()
    sandbox = sandbox.resolve()
    target = target.resolve()
    if not target.is_dir():
        raise RuntimeError("目标目录无效")

    requested: list[str] = []
    for rel in changed_rels:
        rel_n = str(rel or "").strip().replace("\\", "/")
        if not rel_n or is_sensitive_rel(rel_n):
            continue
        requested.append(rel_n)

    planned: list[tuple[str, Path, Path]] = []
    missing: list[str] = []
    for rel_n in requested:
        try:
            src = resolve_in_sandbox(sandbox, rel_n)
        except ValueError as e:
            raise RuntimeError(f"同步路径非法：{rel_n}") from e
        if not src.is_file():
            missing.append(rel_n)
            continue
        size = src.stat().st_size
        if size > cfg.max_file_bytes:
            raise RuntimeError(f"文件过大，拒绝同步：{rel_n}")
        dest = (target / rel_n).resolve()
        try:
            dest.relative_to(target)
        except ValueError as e:
            raise RuntimeError(f"同步路径逃逸：{rel_n}") from e
        planned.append((rel_n, src, dest))

    if missing:
        sample = "、".join(missing[:5])
        more = f" 等 {len(missing)} 个" if len(missing) > 5 else ""
        raise RuntimeError(f"沙箱中缺少待同步文件：{sample}{more}")

    if not planned:
        raise RuntimeError("没有可同步的有效文件")

    written: list[str] = []
    for rel_n, src, dest in planned:
        dest.parent.mkdir(parents=True, exist_ok=True)
        tmp = dest.with_name(dest.name + ".wb-sync-tmp")
        try:
            if tmp.exists():
                tmp.unlink()
            shutil.copy2(src, tmp)
            os.replace(tmp, dest)
        except OSError as e:
            try:
                if tmp.exists():
                    tmp.unlink()
            except OSError:
                pass
            raise RuntimeError(f"同步写入失败：{rel_n}（{e}）") from e
        written.append(rel_n)

    if len(written) != len(planned):
        raise RuntimeError(
            f"同步不完整：计划 {len(planned)} 个，实际 {len(written)} 个"
        )
    return written
