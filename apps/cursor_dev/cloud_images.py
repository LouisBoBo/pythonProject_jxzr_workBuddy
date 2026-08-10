"""把本地上传截图转成 Cursor SDK 的 images，供 Cloud agent.send 直接看图。"""
from __future__ import annotations

import logging
import mimetypes
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
_MIME_OK = {"image/png", "image/jpeg", "image/gif", "image/webp"}
_MAX_IMAGES = 5
_MAX_BYTES = 15 * 1024 * 1024  # Cloud Agents API 文档上限


def _mime_for(path: Path) -> str:
    guessed, _ = mimetypes.guess_type(str(path))
    if guessed in _MIME_OK:
        return guessed
    return {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
        ".gif": "image/gif",
    }.get(path.suffix.lower(), "image/png")


def _under_root(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def resolve_image_path(raw: str, *, data_dir: Path | None = None) -> Path | None:
    """解析上传路径：仅允许 data/uploads 下的文件，禁止任意绝对路径读盘。"""
    s = (raw or "").strip()
    if not s:
        return None

    roots: list[Path] = []
    if data_dir is not None:
        roots.append((Path(data_dir) / "uploads").resolve())
    try:
        roots.append((Path(__file__).resolve().parents[2] / "data" / "uploads").resolve())
    except Exception:
        pass
    uniq_roots: list[Path] = []
    for r in roots:
        if r not in uniq_roots:
            uniq_roots.append(r)
    if not uniq_roots:
        return None

    name = Path(s).name
    if not name or name in {".", ".."} or ".." in name:
        return None

    candidates: list[Path] = []
    for root in uniq_roots:
        try:
            candidates.append((root / name).resolve())
        except OSError:
            continue
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
        if full.suffix.lower() not in _IMAGE_EXTS:
            continue
        if not any(_under_root(full, root) for root in uniq_roots):
            logger.warning("reject image path outside uploads: %s", full)
            continue
        return full
    return None


def collect_image_paths(
    file_paths: list[str] | None,
    *,
    data_dir: Path | None = None,
    max_images: int = _MAX_IMAGES,
) -> tuple[list[Path], list[str]]:
    """返回 (可用图片路径, 跳过原因)。"""
    notes: list[str] = []
    if not file_paths:
        return [], notes
    out: list[Path] = []
    seen: set[str] = set()
    for raw in file_paths:
        if len(out) >= max_images:
            notes.append(f"已达上限 {max_images} 张，其余截图未附带")
            break
        path = resolve_image_path(str(raw), data_dir=data_dir)
        if path is None:
            notes.append(f"找不到或拒绝文件：{Path(str(raw)).name or raw}")
            continue
        key = str(path)
        if key in seen:
            continue
        try:
            size = path.stat().st_size
        except OSError as exc:
            notes.append(f"无法读取 {path.name}：{exc}")
            continue
        if size <= 0:
            notes.append(f"空文件已跳过：{path.name}")
            continue
        if size > _MAX_BYTES:
            notes.append(f"过大已跳过：{path.name}（{size} bytes，上限 {_MAX_BYTES}）")
            continue
        seen.add(key)
        out.append(path)
    return out, notes


def build_sdk_images(
    file_paths: list[str] | None,
    *,
    data_dir: Path | None = None,
) -> tuple[list[Any], list[str]]:
    """构造 cursor_sdk.SDKImage 列表；SDK 不可用时返回空列表。"""
    paths, notes = collect_image_paths(file_paths, data_dir=data_dir)
    if not paths:
        return [], notes
    try:
        from cursor_sdk import SDKImage
    except Exception as exc:
        logger.warning("cursor_sdk SDKImage unavailable: %s", exc)
        notes.append(f"无法加载 SDKImage：{exc}")
        return [], notes

    images: list[Any] = []
    for path in paths:
        try:
            images.append(SDKImage.from_file(path, mime_type=_mime_for(path)))
        except Exception as exc:
            logger.warning("SDKImage.from_file failed for %s: %s", path, exc)
            notes.append(f"附带失败 {path.name}：{exc}")
    return images, notes


def build_send_message(prompt: str, file_paths: list[str] | None, *, data_dir: Path | None = None):
    """若有图片则返回 UserMessage，否则返回纯文本 str（兼容旧 send）。"""
    images, notes = build_sdk_images(file_paths, data_dir=data_dir)
    text = (prompt or "").strip() or "请根据会话需求修改仓库代码"
    if not images:
        return text, notes, 0
    try:
        from cursor_sdk import UserMessage
    except Exception:
        return text, notes + ["UserMessage 不可用，已回退纯文本"], 0
    return UserMessage(text=text, images=images), notes, len(images)
