"""
文件管理：上传、列表、下载与预览。
存储目录：data/file-manager/
"""
from __future__ import annotations

import json
import os
import re
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse

_parent = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _parent not in sys.path:
    sys.path.insert(0, _parent)
from routes_config import FILE_MANAGER_DIR, MAX_UPLOAD_SIZE_MB  # noqa: E402
from routes.auth import require_auth  # noqa: E402

router = APIRouter(prefix="/api/files", tags=["文件管理"])

MAX_SIZE = MAX_UPLOAD_SIZE_MB * 1024 * 1024
FILE_ID_RE = re.compile(r"^[a-f0-9]{32}$")
EXT_RE = re.compile(r"^[a-z0-9]{1,16}$")
PREVIEW_MAX_BYTES = 100 * 1024

ALLOWED_EXTENSIONS = {
    # 文档
    "pdf",
    "doc",
    "docx",
    "dot",
    "dotx",
    "rtf",
    "odt",
    "txt",
    "md",
    "markdown",
    # 表格
    "xls",
    "xlsx",
    "xlsm",
    "csv",
    "tsv",
    "ods",
    # 演示
    "ppt",
    "pptx",
    "odp",
    # 图片
    "png",
    "jpg",
    "jpeg",
    "gif",
    "webp",
    "bmp",
    "tif",
    "tiff",
    "svg",
    # 数据 / 网页
    "json",
    "xml",
    "yaml",
    "yml",
    "html",
    "htm",
    # 压缩包
    "zip",
    "rar",
    "7z",
}

TYPE_CATEGORIES: dict[str, set[str]] = {
    "document": {"pdf", "doc", "docx", "dot", "dotx", "rtf", "odt", "txt", "md", "markdown"},
    "spreadsheet": {"xls", "xlsx", "xlsm", "csv", "tsv", "ods"},
    "presentation": {"ppt", "pptx", "odp"},
    "image": {"png", "jpg", "jpeg", "gif", "webp", "bmp", "tif", "tiff", "svg"},
    "archive": {"zip", "rar", "7z"},
    "data": {"json", "xml", "yaml", "yml", "html", "htm"},
}

PREVIEW_EXTENSIONS = {
    "txt",
    "md",
    "markdown",
    "json",
    "csv",
    "tsv",
    "xml",
    "yaml",
    "yml",
    "html",
    "htm",
    "log",
}

MIME_MAP = {
    "pdf": "application/pdf",
    "doc": "application/msword",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "dot": "application/msword",
    "dotx": "application/vnd.openxmlformats-officedocument.wordprocessingml.template",
    "rtf": "application/rtf",
    "odt": "application/vnd.oasis.opendocument.text",
    "txt": "text/plain",
    "md": "text/markdown",
    "markdown": "text/markdown",
    "xls": "application/vnd.ms-excel",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "xlsm": "application/vnd.ms-excel.sheet.macroEnabled.12",
    "csv": "text/csv",
    "tsv": "text/tab-separated-values",
    "ods": "application/vnd.oasis.opendocument.spreadsheet",
    "ppt": "application/vnd.ms-powerpoint",
    "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "odp": "application/vnd.oasis.opendocument.presentation",
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "gif": "image/gif",
    "webp": "image/webp",
    "bmp": "image/bmp",
    "tif": "image/tiff",
    "tiff": "image/tiff",
    "svg": "image/svg+xml",
    "json": "application/json",
    "xml": "application/xml",
    "yaml": "text/yaml",
    "yml": "text/yaml",
    "html": "text/html",
    "htm": "text/html",
    "zip": "application/zip",
    "rar": "application/vnd.rar",
    "7z": "application/x-7z-compressed",
}


def _root() -> Path:
    path = Path(FILE_MANAGER_DIR)
    path.mkdir(parents=True, exist_ok=True)
    return path.resolve()


def _ext(filename: str) -> str:
    return Path(filename).suffix.lower().lstrip(".")


def _normalize_extension(ext: str) -> str | None:
    """仅允许白名单内的纯字母数字扩展名，防止 meta 篡改导致路径穿越。"""
    raw = (ext or "").strip().lower().lstrip(".")
    if not raw or not EXT_RE.match(raw):
        return None
    if raw not in ALLOWED_EXTENSIONS:
        return None
    return raw


def _safe_download_filename(name: str, ext: str) -> str:
    base = Path(name or "").name or f"file.{ext}"
    base = re.sub(r'[\r\n"\\]', "_", base).strip("._ ") or f"file.{ext}"
    return base[:200]


def _is_allowed_extension(ext: str) -> bool:
    return ext.lower() in ALLOWED_EXTENSIONS


def _type_category(ext: str) -> str:
    ext = ext.lower()
    for name, items in TYPE_CATEGORIES.items():
        if ext in items:
            return name
    return "other"


def _mime(ext: str) -> str:
    return MIME_MAP.get(ext.lower(), "application/octet-stream")


def _valid_file_id(file_id: str) -> bool:
    return bool(FILE_ID_RE.match(file_id or ""))


def _record_dir(file_id: str) -> Path:
    if not _valid_file_id(file_id):
        raise HTTPException(status_code=400, detail="非法文件 ID")
    return _root() / file_id


def _meta_path(file_id: str) -> Path:
    return _record_dir(file_id) / "meta.json"


def _data_path(file_id: str, ext: str) -> Path:
    safe_ext = _normalize_extension(ext)
    if not safe_ext:
        raise HTTPException(status_code=400, detail="非法文件扩展名")
    return _record_dir(file_id) / f"file.{safe_ext}"


async def _read_upload_limited(upload: UploadFile, max_bytes: int) -> bytes:
    """分块读取并限制大小，避免超大文件占满内存。"""
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await upload.read(1024 * 1024)
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            raise HTTPException(
                status_code=400,
                detail=f"文件不能超过 {MAX_UPLOAD_SIZE_MB}MB",
            )
        chunks.append(chunk)
    return b"".join(chunks)


def _read_meta(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def _write_meta_atomic(meta_path: Path, payload: dict[str, Any]) -> None:
    tmp = meta_path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(meta_path)


def _write_bytes_atomic(target: Path, content: bytes) -> None:
    tmp = target.with_suffix(target.suffix + ".tmp")
    tmp.write_bytes(content)
    tmp.replace(target)


def _load_record(file_id: str) -> dict[str, Any] | None:
    meta = _read_meta(_meta_path(file_id))
    if not meta:
        return None
    ext = _normalize_extension(str(meta.get("extension") or ""))
    if not ext:
        return None
    try:
        data_file = _data_path(file_id, ext)
    except HTTPException:
        return None
    if not data_file.is_file():
        return None
    meta.setdefault("id", file_id)
    meta["extension"] = ext
    meta["category"] = _type_category(ext)
    meta["download_url"] = f"/api/files/{file_id}/download"
    meta["previewable"] = ext in PREVIEW_EXTENSIONS
    return meta


def _list_records() -> list[dict[str, Any]]:
    root = _root()
    records: list[dict[str, Any]] = []
    for child in root.iterdir():
        if not child.is_dir():
            continue
        file_id = child.name
        if not _valid_file_id(file_id):
            continue
        rec = _load_record(file_id)
        if rec:
            records.append(rec)
    records.sort(key=lambda r: str(r.get("uploaded_at") or ""), reverse=True)
    return records


def _matches_query(record: dict[str, Any], q: str) -> bool:
    if not q:
        return True
    needle = q.strip().lower()
    if not needle:
        return True
    hay = str(record.get("filename") or "").lower()
    return needle in hay


def _matches_type(record: dict[str, Any], type_filter: str) -> bool:
    if not type_filter or type_filter == "all":
        return True
    ext = str(record.get("extension") or "").lower()
    if type_filter == "other":
        return _type_category(ext) == "other"
    return _type_category(ext) == type_filter


def _matches_status(record: dict[str, Any], status: str) -> bool:
    if not status or status == "all":
        return True
    return str(record.get("status") or "") == status


def _to_public_record(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": record.get("id"),
        "filename": record.get("filename"),
        "extension": record.get("extension"),
        "category": record.get("category"),
        "size": record.get("size"),
        "status": record.get("status"),
        "uploaded_at": record.get("uploaded_at"),
        "mime": record.get("mime"),
        "previewable": record.get("previewable"),
        "download_url": record.get("download_url"),
    }


@router.get(
    "/summary",
    summary="文件管理统计",
    description="返回文件总数与正常状态数量，供文件管理页统计卡使用。",
)
async def file_manager_summary(_auth: tuple = Depends(require_auth)):
    records = _list_records()
    ok_count = sum(1 for r in records if str(r.get("status")) == "ok")
    return {
        "total": len(records),
        "ok": ok_count,
        "failed": 0,
    }


@router.get(
    "",
    summary="文件列表",
    description="分页查询已上传文件，支持文件名搜索、状态与类型筛选。",
)
async def list_files(
    q: str | None = Query(None, description="文件名关键词（模糊匹配）"),
    status: str | None = Query(None, description="状态：all / ok"),
    type: str | None = Query(None, description="类型：all / document / spreadsheet / presentation / image / archive / data / other"),
    page: int = Query(1, ge=1, description="页码，从 1 开始"),
    page_size: int = Query(20, ge=1, le=100, description="每页条数"),
    _auth: tuple = Depends(require_auth),
):
    records = _list_records()
    q_val = (q or "").strip()
    status_val = (status or "all").strip().lower()
    type_val = (type or "all").strip().lower()

    filtered = [
        r
        for r in records
        if _matches_query(r, q_val)
        and _matches_status(r, status_val)
        and _matches_type(r, type_val)
    ]
    total = len(filtered)
    start = (page - 1) * page_size
    end = start + page_size
    items = [_to_public_record(r) for r in filtered[start:end]]
    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.post(
    "/upload",
    summary="上传文件",
    description="上传常见办公文档到 file-manager 目录，单文件最大 50MB。",
)
async def upload_file(file: UploadFile = File(...), _auth: tuple = Depends(require_auth)):
    if not file.filename:
        raise HTTPException(status_code=400, detail="未选择文件")

    ext = _ext(file.filename)
    if not ext or not _normalize_extension(ext):
        raise HTTPException(
            status_code=400,
            detail="不支持该文件类型，请上传常见办公文档（Word/Excel/PPT/PDF/图片/压缩包等）",
        )

    content = await _read_upload_limited(file, MAX_SIZE)
    if not content:
        raise HTTPException(status_code=400, detail="文件内容为空")

    file_id = uuid.uuid4().hex
    record_dir = _record_dir(file_id)
    record_dir.mkdir(parents=True, exist_ok=True)

    data_file = _data_path(file_id, ext)
    meta_file = _meta_path(file_id)
    uploaded_at = datetime.now(timezone.utc).isoformat()
    safe_name = _safe_download_filename(file.filename, ext)
    meta = {
        "id": file_id,
        "filename": safe_name,
        "extension": ext,
        "size": len(content),
        "status": "ok",
        "uploaded_at": uploaded_at,
        "mime": _mime(ext),
    }

    try:
        _write_bytes_atomic(data_file, content)
        _write_meta_atomic(meta_file, meta)
    except OSError as exc:
        import shutil

        shutil.rmtree(record_dir, ignore_errors=True)
        raise HTTPException(status_code=500, detail=f"保存文件失败：{exc}") from exc

    rec = _load_record(file_id)
    if not rec:
        raise HTTPException(status_code=500, detail="文件已保存但读取失败")
    return {"status": "ok", "file": _to_public_record(rec)}


@router.get(
    "/{file_id}/download",
    summary="下载文件",
    description="下载指定文件到本地（需登录）。",
)
async def download_file(file_id: str, _auth: tuple = Depends(require_auth)):
    rec = _load_record(file_id)
    if not rec:
        raise HTTPException(status_code=404, detail="文件不存在")

    ext = str(rec.get("extension") or "")
    data_file = _data_path(file_id, ext).resolve()
    record_dir = _record_dir(file_id).resolve()
    try:
        data_file.relative_to(record_dir)
    except ValueError:
        raise HTTPException(status_code=400, detail="非法文件路径")

    if not data_file.is_file():
        raise HTTPException(status_code=404, detail="文件不存在")

    filename = _safe_download_filename(str(rec.get("filename") or ""), ext)
    return FileResponse(
        path=str(data_file),
        filename=filename,
        media_type=str(rec.get("mime") or _mime(ext)),
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get(
    "/{file_id}/preview",
    summary="预览文本内容",
    description="预览可读的文本类文件（Markdown/JSON/CSV 等），最多返回 100KB。",
)
async def preview_file(file_id: str, _auth: tuple = Depends(require_auth)):
    rec = _load_record(file_id)
    if not rec:
        raise HTTPException(status_code=404, detail="文件不存在")

    ext = str(rec.get("extension") or "").lower()
    if ext not in PREVIEW_EXTENSIONS:
        raise HTTPException(status_code=400, detail="该文件类型不支持在线预览")

    data_file = _data_path(file_id, ext).resolve()
    record_dir = _record_dir(file_id).resolve()
    try:
        data_file.relative_to(record_dir)
    except ValueError:
        raise HTTPException(status_code=400, detail="非法文件路径")

    if not data_file.is_file():
        raise HTTPException(status_code=404, detail="文件不存在")

    raw = data_file.read_bytes()
    truncated = len(raw) > PREVIEW_MAX_BYTES
    snippet = raw[:PREVIEW_MAX_BYTES]
    content = snippet.decode("utf-8", errors="replace")
    return {
        "id": file_id,
        "filename": rec.get("filename"),
        "extension": ext,
        "content": content,
        "truncated": truncated,
    }
