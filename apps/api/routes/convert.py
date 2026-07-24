"""
文档格式互转：上传后生成多种常用格式供下载。
支持：CSV / TSV / Excel(xlsx) / JSON / Markdown / TXT / HTML
"""
import json
import os
import re
import time
from io import StringIO
from pathlib import Path

import pandas as pd
from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import FileResponse

import sys

_parent = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _parent not in sys.path:
    sys.path.insert(0, _parent)
from routes_config import UPLOAD_DIR, CONVERT_DIR

router = APIRouter(prefix="/api", tags=["convert"])

CONVERT_PATH = Path(CONVERT_DIR)
os.makedirs(CONVERT_PATH, exist_ok=True)
os.makedirs(UPLOAD_DIR, exist_ok=True)

TARGET_FORMATS = ("csv", "xlsx", "json", "tsv", "md", "txt", "html")
SUPPORTED_INPUT = set(TARGET_FORMATS) | {"xls"}

FORMAT_META = {
    "csv": {"label": "CSV", "mime": "text/csv", "desc": "逗号分隔表格"},
    "xlsx": {"label": "Excel", "mime": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "desc": "Excel 工作簿"},
    "json": {"label": "JSON", "mime": "application/json", "desc": "结构化数据"},
    "tsv": {"label": "TSV", "mime": "text/tab-separated-values", "desc": "制表符分隔"},
    "md": {"label": "Markdown", "mime": "text/markdown", "desc": "Markdown 表格"},
    "txt": {"label": "TXT", "mime": "text/plain", "desc": "纯文本"},
    "html": {"label": "HTML", "mime": "text/html", "desc": "网页表格"},
}

MAX_SIZE = 50 * 1024 * 1024


def _safe_stem(name: str) -> str:
    stem = Path(name).stem
    stem = re.sub(r"[^\w\u4e00-\u9fff\-]+", "_", stem).strip("_")
    return stem[:80] or "document"


def _ext(filename: str) -> str:
    return Path(filename).suffix.lower().lstrip(".")


def _df_to_markdown(df: pd.DataFrame) -> str:
    cols = [str(c) for c in df.columns]
    header = "| " + " | ".join(cols) + " |"
    sep = "| " + " | ".join("---" for _ in cols) + " |"
    rows = []
    for _, row in df.iterrows():
        cells = [str(row[c]).replace("|", "\\|").replace("\n", " ") for c in df.columns]
        rows.append("| " + " | ".join(cells) + " |")
    return "\n".join([header, sep, *rows])


def _df_to_html(df: pd.DataFrame, title: str) -> str:
    table = df.to_html(index=False, border=0, justify="left")
    return (
        "<!DOCTYPE html><html><head><meta charset='utf-8'>"
        f"<title>{title}</title>"
        "<style>body{font-family:-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif;padding:24px;}"
        "table{border-collapse:collapse;width:100%;}"
        "th,td{border:1px solid #e2e8f0;padding:8px 12px;text-align:left;}"
        "th{background:#f8fafc;}</style></head><body>"
        f"<h1>{title}</h1>{table}</body></html>"
    )


def _df_to_txt(df: pd.DataFrame) -> str:
    return df.to_string(index=False)


def _plain_to_df(text: str) -> pd.DataFrame:
    text = text.strip()
    if not text:
        return pd.DataFrame({"content": []})

    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if len(lines) >= 2 and lines[0].startswith("|") and "---" in lines[1]:
        try:
            rows = []
            for ln in lines:
                cleaned = ln.replace("|", "").replace("-", "").replace(":", "").strip()
                if cleaned == "":
                    continue
                if not ln.startswith("|"):
                    continue
                cells = [c.strip() for c in ln.strip("|").split("|")]
                rows.append(cells)
            if len(rows) >= 2:
                header, body = rows[0], rows[1:]
                width = len(header)
                body = [(r + [""] * (width - len(r)))[:width] for r in body]
                return pd.DataFrame(body, columns=header)
        except Exception:
            pass

    for sep in (",", "\t", "|", ";"):
        try:
            df = pd.read_csv(StringIO(text), sep=sep)
            if df.shape[1] > 1:
                return df
        except Exception:
            continue

    return pd.DataFrame({"content": lines})


def load_as_dataframe(path: Path, ext: str) -> pd.DataFrame:
    ext = ext.lower()
    if ext == "csv":
        return pd.read_csv(path)
    if ext == "tsv":
        return pd.read_csv(path, sep="\t")
    if ext in ("xlsx", "xls"):
        return pd.read_excel(path)
    if ext == "json":
        raw = path.read_text(encoding="utf-8")
        data = json.loads(raw)
        if isinstance(data, list):
            return pd.json_normalize(data)
        if isinstance(data, dict):
            if data and all(isinstance(v, list) for v in data.values()):
                return pd.DataFrame(data)
            return pd.json_normalize(data)
        return pd.DataFrame({"value": [data]})
    if ext in ("md", "txt", "html"):
        text = path.read_text(encoding="utf-8", errors="ignore")
        if ext == "html":
            try:
                tables = pd.read_html(StringIO(text))
                if tables:
                    return tables[0]
            except Exception:
                pass
            text = re.sub(r"<[^>]+>", " ", text)
            text = re.sub(r"\s+", "\n", text).strip()
        return _plain_to_df(text)
    raise HTTPException(status_code=400, detail=f"暂不支持的格式: .{ext}")


def write_format(df: pd.DataFrame, out_path: Path, fmt: str, title: str) -> None:
    fmt = fmt.lower()
    if fmt == "csv":
        df.to_csv(out_path, index=False, encoding="utf-8-sig")
    elif fmt == "tsv":
        df.to_csv(out_path, index=False, sep="\t", encoding="utf-8-sig")
    elif fmt == "xlsx":
        df.to_excel(out_path, index=False, engine="openpyxl")
    elif fmt == "json":
        records = json.loads(df.to_json(orient="records", force_ascii=False))
        out_path.write_text(
            json.dumps(records, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    elif fmt == "md":
        out_path.write_text(_df_to_markdown(df), encoding="utf-8")
    elif fmt == "txt":
        out_path.write_text(_df_to_txt(df), encoding="utf-8")
    elif fmt == "html":
        out_path.write_text(_df_to_html(df, title), encoding="utf-8")
    else:
        raise ValueError(f"unsupported format: {fmt}")


@router.post("/convert")
async def convert_document(file: UploadFile = File(...)):
    """上传文档并转换为多种常用格式，返回可下载列表。"""
    if not file.filename:
        raise HTTPException(status_code=400, detail="未选择文件")

    src_ext = _ext(file.filename)
    if src_ext not in SUPPORTED_INPUT:
        raise HTTPException(
            status_code=400,
            detail="支持格式：CSV、TSV、Excel(.xlsx/.xls)、JSON、Markdown、TXT、HTML",
        )

    content = await file.read()
    if len(content) > MAX_SIZE:
        raise HTTPException(status_code=400, detail="文件不能超过 50MB")

    ts = int(time.time())
    stem = _safe_stem(file.filename)
    job_id = f"{stem}_{ts}"
    job_dir = CONVERT_PATH / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    original_path = job_dir / f"original.{src_ext}"
    original_path.write_bytes(content)

    try:
        df = load_as_dataframe(original_path, src_ext)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"无法解析文件：{e}") from e

    if df is None:
        df = pd.DataFrame({"content": []})

    conversions = []
    for fmt in TARGET_FORMATS:
        if fmt == src_ext:
            continue

        out_name = f"{stem}.{fmt}"
        out_path = job_dir / out_name
        try:
            write_format(df, out_path, fmt, stem)
            conversions.append(
                {
                    "format": fmt,
                    "label": FORMAT_META[fmt]["label"],
                    "desc": FORMAT_META[fmt]["desc"],
                    "status": "ok",
                    "filename": out_name,
                    "size": out_path.stat().st_size,
                    "download_url": f"/api/convert/download/{job_id}/{out_name}",
                }
            )
        except Exception as e:
            conversions.append(
                {
                    "format": fmt,
                    "label": FORMAT_META[fmt]["label"],
                    "desc": FORMAT_META[fmt]["desc"],
                    "status": "error",
                    "error": str(e),
                }
            )

    ok_list = [c for c in conversions if c.get("status") == "ok"]
    return {
        "status": "ok",
        "job_id": job_id,
        "original": {
            "filename": file.filename,
            "extension": src_ext,
            "size": len(content),
            "rows": int(len(df)),
            "columns": [str(c) for c in df.columns.tolist()],
        },
        "conversions": conversions,
        "converted_count": len(ok_list),
    }


@router.get("/convert/download/{job_id}/{filename}")
async def download_converted(job_id: str, filename: str):
    """下载转换后的文件（触发浏览器本地下载）。"""
    safe_job = Path(job_id).name
    safe_name = Path(filename).name
    job_dir = (CONVERT_PATH / safe_job).resolve()
    target = (job_dir / safe_name).resolve()

    if not str(target).startswith(str(job_dir)):
        raise HTTPException(status_code=400, detail="非法文件路径")
    if not job_dir.exists() or not target.exists() or not target.is_file():
        raise HTTPException(status_code=404, detail="文件不存在")

    ext = _ext(safe_name)
    media = FORMAT_META.get(ext, {}).get("mime", "application/octet-stream")
    return FileResponse(
        path=str(target),
        filename=safe_name,
        media_type=media,
        headers={"Content-Disposition": f'attachment; filename="{safe_name}"'},
    )
