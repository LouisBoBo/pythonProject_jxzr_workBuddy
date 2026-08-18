"""
对话接口：同步 / 流式 / 文件上传。
"""
import json
import os
from pathlib import Path

from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException, Request
from fastapi.responses import StreamingResponse, FileResponse
from pydantic import BaseModel

import sys, os
_parent = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _parent not in sys.path:
    sys.path.insert(0, _parent)
from routes_config import UPLOAD_DIR, AgentConfig, DATA_DIR
from agent_wrapper import AgentRunner
from routes.auth import require_auth
from middleware.request_context import set_request_agent_context, reset_request_agent_context

router = APIRouter(prefix="/api", tags=["chat"])


class ChatRequest(BaseModel):
    message: str
    thread_id: str = "default"
    file_paths: list[str] = []
    page_context: dict | None = None


class ChatResponse(BaseModel):
    reply: str
    thread_id: str


@router.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest, auth: tuple = Depends(require_auth)):
    """同步对话：发送消息，等待完整回复后返回。"""
    _token, user = auth
    thread_id = (req.thread_id or "").strip() or f"session-{(user.username or 'anon')}"
    if thread_id == "default" and user.username:
        thread_id = f"session-{user.username}"
    ctx = set_request_agent_context(
        thread_id=thread_id,
        user_id=user.user_id,
        username=user.username,
        page_context=req.page_context,
    )
    try:
        from tools.upload_paths import sanitize_client_file_paths

        safe_paths = sanitize_client_file_paths(req.file_paths, data_dir=Path(DATA_DIR))
        runner = AgentRunner()
        reply = await runner.chat(req.message, thread_id, safe_paths)
        return ChatResponse(reply=reply, thread_id=thread_id)
    finally:
        reset_request_agent_context(ctx)


@router.post("/chat/stream")
async def chat_stream(
    req: ChatRequest,
    request: Request,
    auth: tuple = Depends(require_auth),
):
    """流式对话：SSE 推送 status / step / token / confirm / done / error。"""
    import asyncio

    _token, user = auth
    thread_id = (req.thread_id or "").strip() or f"session-{(user.username or 'anon')}"
    if thread_id == "default" and user.username:
        thread_id = f"session-{user.username}"

    async def generate():
        runner = AgentRunner()
        ctx = set_request_agent_context(
            thread_id=thread_id,
            user_id=user.user_id,
            username=user.username,
            page_context=req.page_context,
        )
        cancel_event = asyncio.Event()
        try:
            from tools.upload_paths import sanitize_client_file_paths

            safe_paths = sanitize_client_file_paths(req.file_paths, data_dir=Path(DATA_DIR))
            # 先发一条带填充的 SSE 注释，冲掉代理/内核初始缓冲
            yield ": " + (" " * 2048) + "\n\n"
            async for event in runner.stream_chat(
                req.message,
                thread_id,
                safe_paths,
                cancel_event=cancel_event,
            ):
                if await request.is_disconnected():
                    cancel_event.set()
                    break
                if not isinstance(event, dict):
                    event = {"type": "token", "text": str(event), "token": str(event)}
                payload = json.dumps(event, ensure_ascii=False)
                yield f"data: {payload}\n\n"
                et = event.get("type") if isinstance(event, dict) else None
                # status/step/confirm：填充 + 短间隔，确保过程事件不会和后续 token 被攒成一包
                if et in ("status", "step", "confirm"):
                    yield ": " + (" " * 2048) + "\n\n"
                    await asyncio.sleep(0.04)
                else:
                    await asyncio.sleep(0)
            if not cancel_event.is_set() and not await request.is_disconnected():
                yield f"data: {json.dumps({'type': 'done', 'done': True, 'thread_id': thread_id}, ensure_ascii=False)}\n\n"
                await asyncio.sleep(0)
        except asyncio.CancelledError:
            cancel_event.set()
            raise
        except Exception as e:
            import logging
            import traceback

            logging.getLogger("mes.chat").exception("chat_stream failed: %s", e)
            # 同时写入 api 标准错误，便于 .run/api.log 排查
            print(f"[chat_stream] {type(e).__name__}: {e}\n{traceback.format_exc()}", flush=True)

            # 展开底层原因（如 DNS errno 8），避免只看到模糊的 Connection error.
            root = e
            cause_parts: list[str] = [f"{type(e).__name__}: {e}"]
            cur: BaseException | None = e
            seen: set[int] = set()
            while cur is not None and id(cur) not in seen:
                seen.add(id(cur))
                nxt = cur.__cause__ or cur.__context__
                if nxt is None or id(nxt) in seen:
                    break
                cause_parts.append(f"{type(nxt).__name__}: {nxt}")
                cur = nxt
                root = nxt

            err_msg = str(e) or e.__class__.__name__
            root_txt = str(root)
            low = (err_msg + " " + root_txt).lower()
            # DNS/连接失败后丢掉 Agent 单例，避免坏客户端一直复用
            if "nodename nor servname" in low or "connection error" in low or "connecterror" in low.replace(" ", ""):
                try:
                    runner.reset_agent()
                except Exception:
                    pass
            if "nodename nor servname" in low or "name or service not known" in low or "errno 8" in low:
                err_msg = (
                    "DNS 解析失败，本机暂时无法解析大模型域名（api.deepseek.com）。"
                    "这通常是网络/DNS/VPN 问题，不是 API Key 余额问题。"
                    "可尝试：重启 API（./scripts/stop.sh && ./scripts/dev.sh）、"
                    "关闭错误 VPN、换网络或刷新 DNS 后重试。"
                    f" 明细：{root_txt}"
                )
            elif "connection error" in low or "connecterror" in low.replace(" ", ""):
                err_msg = (
                    f"{err_msg}（无法连接大模型服务。若 Key 仍有余额，多为网络/DNS/VPN；"
                    f"底层：{root_txt}）"
                )
            err = json.dumps({"type": "error", "error": err_msg, "message": err_msg}, ensure_ascii=False)
            yield f"data: {err}\n\n"
        finally:
            cancel_event.set()
            reset_request_agent_context(ctx)

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "Content-Type": "text/event-stream; charset=utf-8",
        },
    )


@router.post("/upload")
async def upload_file(file: UploadFile = File(...), _auth: tuple = Depends(require_auth)):
    """上传文件（CSV/Excel/JSON/日志/截图等），保存到 uploads 目录并返回预览。"""
    import time
    os.makedirs(UPLOAD_DIR, exist_ok=True)

    content = await file.read()
    safe_name = Path(file.filename or "upload.bin").name
    timestamp = int(time.time())
    stem = Path(safe_name).stem or "upload"
    ext = safe_name.rsplit(".", 1)[-1].lower() if "." in safe_name else ""
    # 剪贴板粘贴常无扩展名，按 content-type 补
    image_exts = {"png", "jpg", "jpeg", "webp", "gif", "bmp"}
    ctype = (file.content_type or "").lower()
    if not ext and ctype.startswith("image/"):
        ext = ctype.split("/", 1)[-1].replace("jpeg", "jpg")
        if ext == "jpg":
            pass
        elif ext not in image_exts:
            ext = "png"
    saved_name = f"{stem}_{timestamp}.{ext}" if ext else f"{stem}_{timestamp}"
    file_path = Path(UPLOAD_DIR) / saved_name

    is_image = ext in image_exts or ctype.startswith("image/")
    max_image = 8 * 1024 * 1024
    if is_image and len(content) > max_image:
        raise HTTPException(status_code=400, detail="截图过大（上限 8MB）")

    file_path.write_bytes(content)
    stat = file_path.stat()

    # 简单预览
    preview = ""
    try:
        if is_image:
            preview = f"[image {ext or 'bin'} {stat.st_size} bytes]"
        elif ext == "csv":
            text = content.decode("utf-8-sig")
            lines = text.strip().split("\n")
            preview = "\n".join(lines[:8])
        elif ext in ("xlsx", "xls"):
            import pandas as pd
            df = pd.read_excel(file_path)
            preview = df.head(5).to_csv(index=False)
        elif ext == "json":
            data = json.loads(content.decode("utf-8"))
            preview = json.dumps(data[:3] if isinstance(data, list) else data, ensure_ascii=False, indent=2)
        elif ext in ("jsonl", "log", "txt", "yaml", "yml", "md"):
            text = content.decode("utf-8", errors="ignore")
            preview = "\n".join(text.splitlines()[:12])
    except Exception:
        preview = content.decode("utf-8", errors="ignore")[:500]

    return {
        "status": "ok",
        "filename": file.filename or saved_name,
        "saved_name": saved_name,
        # 不回传本机绝对路径，避免泄露服务器目录结构；客户端请用 saved_name
        "path": saved_name,
        "size": stat.st_size,
        "preview": preview,
        "extension": ext,
        "kind": "image" if is_image else "file",
        "mime": ctype or (f"image/{ext}" if is_image else "application/octet-stream"),
        "preview_url": f"/api/uploads/{saved_name}" if is_image else "",
    }


@router.get("/uploads/{filename}")
async def get_uploaded_file(filename: str, _auth: tuple = Depends(require_auth)):
    """读取 uploads 目录中的文件（用于截图预览；需登录）。"""
    safe = Path(filename).name
    if safe != filename or ".." in filename:
        raise HTTPException(status_code=400, detail="非法文件名")
    upload_root = Path(UPLOAD_DIR).resolve()
    try:
        target = (upload_root / safe).resolve()
        target.relative_to(upload_root)
    except ValueError:
        raise HTTPException(status_code=400, detail="非法文件路径")
    if not target.exists() or not target.is_file():
        raise HTTPException(status_code=404, detail="文件不存在")
    media = "application/octet-stream"
    ext = target.suffix.lower()
    media = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
        ".gif": "image/gif",
        ".bmp": "image/bmp",
    }.get(ext, media)
    return FileResponse(path=str(target), filename=safe, media_type=media)


@router.get("/download/{filename}")
async def download_file(filename: str, _auth: tuple = Depends(require_auth)):
    """下载导出目录中的文件（需登录；仅允许 EXPORT_DIR，防止路径遍历）。"""
    safe = Path(filename).name
    if safe != filename or ".." in filename:
        raise HTTPException(status_code=400, detail="非法文件名")
    export_dir = Path(AgentConfig.EXPORT_DIR).resolve()
    try:
        target = (export_dir / safe).resolve()
        target.relative_to(export_dir)
    except ValueError:
        raise HTTPException(status_code=400, detail="非法文件路径")

    if not target.exists() or not target.is_file():
        raise HTTPException(status_code=404, detail="文件不存在")

    return FileResponse(
        path=str(target),
        filename=safe,
        media_type="application/octet-stream",
    )
