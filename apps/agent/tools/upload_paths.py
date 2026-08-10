"""上传目录路径解析：仅允许 data/uploads（及可选 samples）下文件，禁止任意读盘。"""
from __future__ import annotations

import re
from pathlib import Path


def _under_root(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _glob_escape(s: str) -> str:
    """避免用户文件名里的 * ? [ 被当 glob 元字符。"""
    return re.sub(r"([*?\[\]{}])", r"[\1]", s)


def _default_data_dir() -> Path | None:
    try:
        from config import Config

        raw = getattr(Config, "DATA_DIR", None)
        if raw:
            return Path(raw)
    except Exception:
        pass
    try:
        # apps/agent/tools/upload_paths.py → repo/data
        return Path(__file__).resolve().parents[3] / "data"
    except Exception:
        return None


def upload_roots(*, data_dir: Path | None = None, include_samples: bool = False) -> list[Path]:
    roots: list[Path] = []
    base = data_dir if data_dir is not None else _default_data_dir()
    if base is not None:
        roots.append((Path(base) / "uploads").resolve())
        if include_samples:
            roots.append((Path(base) / "samples").resolve())
    uniq: list[Path] = []
    for r in roots:
        if r not in uniq:
            uniq.append(r)
    return uniq


def resolve_under_uploads(
    raw: str,
    *,
    data_dir: Path | None = None,
    include_samples: bool = False,
    allowed_suffixes: set[str] | None = None,
) -> Path | None:
    """将 saved_name / 相对名 / 落在 uploads 内的绝对路径解析为安全文件路径。"""
    s = (raw or "").strip().strip('"').strip("'")
    if not s:
        return None

    roots = upload_roots(data_dir=data_dir, include_samples=include_samples)
    if not roots:
        return None

    name = Path(s).name
    if not name or name in {".", ".."}:
        return None
    # 拒绝带路径穿越的 raw（即使 basename 看似正常）
    if ".." in Path(s).parts:
        return None

    candidates: list[Path] = []
    for root in roots:
        try:
            candidates.append((root / name).resolve())
        except OSError:
            continue
        # 上传名常为 stem_timestamp.ext：按前缀模糊匹配最新
        stem = Path(name).stem
        ext = Path(name).suffix
        try:
            if stem:
                safe_stem = _glob_escape(stem)
                safe_ext = _glob_escape(ext) if ext else ""
                pattern = f"{safe_stem}_*{safe_ext}" if safe_ext else f"{safe_stem}_*"
                matches = sorted(
                    root.glob(pattern),
                    key=lambda x: x.stat().st_mtime,
                    reverse=True,
                )
                candidates.extend(matches[:5])
        except OSError:
            pass
    try:
        candidates.append(Path(s).expanduser().resolve())
    except OSError:
        pass

    seen: set[str] = set()
    for full in candidates:
        key = str(full)
        if key in seen:
            continue
        seen.add(key)
        if not full.is_file():
            continue
        if allowed_suffixes is not None and full.suffix.lower() not in allowed_suffixes:
            continue
        if not any(_under_root(full, root) for root in roots):
            continue
        return full
    return None


def sanitize_client_file_paths(
    paths: list[str] | None,
    *,
    data_dir: Path | None = None,
    max_paths: int = 20,
) -> list[str]:
    """API 入口：只保留能解析到 uploads 的路径。"""
    if not paths:
        return []
    out: list[str] = []
    seen: set[str] = set()
    for raw in paths:
        if len(out) >= max_paths:
            break
        resolved = resolve_under_uploads(str(raw), data_dir=data_dir)
        if resolved is None:
            continue
        key = str(resolved)
        if key in seen:
            continue
        seen.add(key)
        out.append(key)
    return out
