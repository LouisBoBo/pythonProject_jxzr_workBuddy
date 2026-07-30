"""IDE Bridge 会话 / 任务存储（DATA_DIR/ide_bridge）。

供 API 路由与 Agent tool 同进程调用；按 user_id 隔离。
"""
from __future__ import annotations

import json
import os
import time
import uuid
from pathlib import Path
from typing import Any

from ha.fs_lock import InterProcessLock

_HEARTBEAT_TTL = float(os.getenv("IDE_BRIDGE_HEARTBEAT_TTL_SEC", "45") or "45")
_TASK_WAIT_DEFAULT = float(os.getenv("IDE_BRIDGE_TASK_TIMEOUT_SEC", "120") or "120")
_lock = InterProcessLock("ide-bridge")

_HINT_CONNECT_VSCODE = (
    "请在网页侧栏点「配对 VS Code」，记下 6 位配对码；"
    "VS Code 命令面板执行「WorkBuddy: Pair」输入配对码。"
    "或安装扩展后执行「WorkBuddy: Connect」。"
    "Bridge 离线时也可用 request_git_review 审本机目录/Git 仓。"
)
_HINT_OPEN_FOLDER = (
    "VS Code 已连接，但当前没有打开文件夹。请在 VS Code 中：文件 → 打开文件夹，"
    "选择要审核的项目后再发起审核。"
)


def _root() -> Path:
    from config import Config

    d = Path(Config.DATA_DIR) / "ide_bridge"
    d.mkdir(parents=True, exist_ok=True)
    (d / "sessions").mkdir(exist_ok=True)
    (d / "pending").mkdir(exist_ok=True)
    (d / "results").mkdir(exist_ok=True)
    (d / "pairing").mkdir(exist_ok=True)
    (d / "tasks").mkdir(exist_ok=True)
    return d


def _pairing_path(code: str) -> Path:
    safe = "".join(c for c in code.upper() if c.isalnum())[:12]
    return _root() / "pairing" / f"{safe}.json"


_PAIRING_TTL_SEC = float(os.getenv("IDE_BRIDGE_PAIRING_TTL_SEC", "120") or "120")


def create_pairing_code(
    *,
    user_id: Any,
    username: str,
    access_token: str = "",
) -> dict[str, Any]:
    """网页已登录用户签发短时配对码；扩展凭码兑换「长期 Bridge 凭证」（非网页 JWT）。"""
    import random
    import string

    if user_id is None:
        raise ValueError("user_id 不能为空")

    alphabet = string.ascii_uppercase + string.digits
    alphabet = alphabet.replace("O", "").replace("0", "").replace("I", "").replace("1", "")
    now = time.time()
    expires_at = now + max(30.0, _PAIRING_TTL_SEC)

    with _lock:
        for _ in range(20):
            code = "".join(random.choice(alphabet) for _ in range(6))
            path = _pairing_path(code)
            if path.is_file():
                continue
            body = {
                "code": code,
                "user_id": user_id,
                "username": username or "",
                # 不再把会过期的网页 JWT 塞进配对；兑换时签发长期 bridge token
                "created_at": now,
                "expires_at": expires_at,
            }
            _write_json(path, body)
            return {
                "code": code,
                "expires_in": int(expires_at - now),
                "expires_at": expires_at,
                "hint": "VS Code 执行 WorkBuddy: Pair 输入配对码（只需一次，约 90 天自动连）",
            }
    raise RuntimeError("无法生成配对码，请重试")


def redeem_pairing_code(code: str) -> dict[str, Any]:
    """扩展用配对码兑换长期 Bridge 凭证（一次性）。"""
    from tools.ide_review.bridge_token import issue_bridge_token

    raw = (code or "").strip().upper()
    if len(raw) < 4:
        raise KeyError("invalid_code")
    path = _pairing_path(raw)
    with _lock:
        data = _read_json(path)
        if not data:
            raise KeyError("invalid_code")
        try:
            path.unlink(missing_ok=True)
        except Exception:
            pass
    exp = float(data.get("expires_at") or 0)
    if time.time() > exp:
        raise PermissionError("expired")
    issued = issue_bridge_token(
        user_id=data.get("user_id"),
        username=str(data.get("username") or ""),
    )
    return issued


def _uid_key(user_id: Any) -> str:
    raw = "anon" if user_id is None else str(user_id)
    return "".join(c if c.isalnum() or c in "-_" else "_" for c in raw)[:120] or "anon"


def _session_path(user_id: Any) -> Path:
    return _root() / "sessions" / f"{_uid_key(user_id)}.json"


def _pending_dir(user_id: Any) -> Path:
    p = _root() / "pending" / _uid_key(user_id)
    p.mkdir(parents=True, exist_ok=True)
    return p


def _result_path(task_id: str) -> Path:
    return _root() / "results" / f"{task_id}.json"


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def feature_enabled() -> bool:
    from config import Config

    return bool(getattr(Config, "IDE_REVIEW_ENABLED", False))


def _normalize_workspace(workspace_root: str, workspace_ready: bool | None) -> tuple[str, bool]:
    root = (workspace_root or "").strip()
    if workspace_ready is None:
        ready = bool(root)
    else:
        ready = bool(workspace_ready) and bool(root)
    if not ready:
        root = ""
    return root, ready


def _normalize_recent_workspaces(raw: Any) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        return []
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in raw:
        if not isinstance(item, dict):
            continue
        p = str(item.get("path") or "").strip()
        if not p or p in seen:
            continue
        seen.add(p)
        name = str(item.get("name") or "").strip() or Path(p).name
        out.append(
            {
                "path": p,
                "name": name,
                "current": bool(item.get("current")),
            }
        )
        if len(out) >= 12:
            break
    return out


def register_bridge(
    *,
    user_id: Any,
    username: str,
    bridge_id: str,
    workspace_root: str = "",
    carrier: str = "vscode",
    workspace_ready: bool | None = None,
    recent_workspaces: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    now = time.time()
    root, ready = _normalize_workspace(workspace_root, workspace_ready)
    session = {
        "user_id": user_id,
        "username": username or "",
        "bridge_id": bridge_id,
        "workspace_root": root,
        "workspace_ready": ready,
        "carrier": carrier or "vscode",
        "registered_at": now,
        "last_heartbeat": now,
        "recent_workspaces": _normalize_recent_workspaces(recent_workspaces),
    }
    with _lock:
        _write_json(_session_path(user_id), session)
    return session


def heartbeat(
    user_id: Any,
    bridge_id: str,
    *,
    workspace_root: str | None = None,
    workspace_ready: bool | None = None,
    recent_workspaces: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    with _lock:
        path = _session_path(user_id)
        session = _read_json(path)
        if not session:
            raise KeyError("bridge_not_registered")
        if str(session.get("bridge_id") or "") != str(bridge_id):
            raise PermissionError("bridge_id_mismatch")
        session["last_heartbeat"] = time.time()
        if workspace_root is not None or workspace_ready is not None:
            cur_root = (
                workspace_root
                if workspace_root is not None
                else str(session.get("workspace_root") or "")
            )
            cur_ready = (
                workspace_ready
                if workspace_ready is not None
                else bool(session.get("workspace_ready"))
            )
            root, ready = _normalize_workspace(cur_root, cur_ready)
            session["workspace_root"] = root
            session["workspace_ready"] = ready
        if recent_workspaces is not None:
            session["recent_workspaces"] = _normalize_recent_workspaces(recent_workspaces)
        _write_json(path, session)
        return session


def is_online(user_id: Any) -> bool:
    with _lock:
        session = _read_json(_session_path(user_id))
    if not session:
        return False
    last = float(session.get("last_heartbeat") or 0)
    return (time.time() - last) <= _HEARTBEAT_TTL


def get_status(user_id: Any) -> dict[str, Any]:
    with _lock:
        session = _read_json(_session_path(user_id))
    payload: dict[str, Any] = {
        "feature_enabled": feature_enabled(),
        "online": False,
        "workspace_ready": False,
        "carrier": None,
        "workspace_root": None,
        "bridge_id": None,
        "last_heartbeat": None,
        "heartbeat_ttl_sec": _HEARTBEAT_TTL,
    }
    if session:
        last = float(session.get("last_heartbeat") or 0)
        online = (time.time() - last) <= _HEARTBEAT_TTL
        ready = bool(session.get("workspace_ready")) and bool(
            session.get("workspace_root")
        )
        payload.update(
            {
                "online": online,
                "workspace_ready": ready if online else False,
                "carrier": session.get("carrier") if online else None,
                "workspace_root": session.get("workspace_root") if online and ready else None,
                "bridge_id": session.get("bridge_id") if online else None,
                "last_heartbeat": last,
                "recent_workspaces": (
                    _normalize_recent_workspaces(session.get("recent_workspaces"))
                    if online
                    else []
                ),
            }
        )
    return payload


def _task_meta_path(task_id: str) -> Path:
    safe = "".join(c for c in str(task_id) if c.isalnum() or c in "-_")
    if not safe or safe != str(task_id):
        raise ValueError("非法 task_id")
    return _root() / "tasks" / f"{safe}.json"


def enqueue_task(user_id: Any, payload: dict[str, Any]) -> str:
    task_id = str(uuid.uuid4())
    task = {
        "task_id": task_id,
        "user_id": user_id,
        "created_at": time.time(),
        "status": "pending",
        **payload,
    }
    meta = {
        "task_id": task_id,
        "user_id": user_id,
        "created_at": task["created_at"],
        "intent": str(payload.get("intent") or ""),
        "paths": list(payload.get("paths") or [])[:40],
        "thread_id": str(payload.get("thread_id") or ""),
        "workspace_root": str(payload.get("workspace_root") or ""),
    }
    with _lock:
        path = _pending_dir(user_id) / f"{task_id}.json"
        _write_json(path, task)
        _write_json(_task_meta_path(task_id), meta)
    try:
        from tools.ide_review.ide_audit import append_ide_audit

        append_ide_audit(
            {
                "event": "ide_task_enqueued",
                "user_id": user_id,
                "task_id": task_id,
                "intent": meta["intent"],
                "paths": meta["paths"],
                "workspace_root": meta["workspace_root"],
                "thread_id": meta["thread_id"],
            }
        )
    except Exception:
        pass
    return task_id


def claim_pending_task(user_id: Any, bridge_id: str) -> dict[str, Any] | None:
    """非阻塞取出一条 pending（供本机 Bridge 扫盘，避免 HTTP 长轮询死锁）。"""
    with _lock:
        session = _read_json(_session_path(user_id))
        if not session or str(session.get("bridge_id") or "") != str(bridge_id):
            raise PermissionError("bridge_id_mismatch")
        session["last_heartbeat"] = time.time()
        _write_json(_session_path(user_id), session)

        pending = _pending_dir(user_id)
        files = sorted(pending.glob("*.json"), key=lambda p: p.stat().st_mtime)
        if not files:
            return None
        path = files[0]
        task = _read_json(path)
        try:
            path.unlink(missing_ok=True)
        except Exception:
            pass
        if task:
            task["status"] = "dispatched"
            task["dispatched_at"] = time.time()
        return task


def poll_task(user_id: Any, bridge_id: str, wait_sec: float = 25.0) -> dict[str, Any] | None:
    """长轮询：有任务则取出（删除 pending），否则等到 wait_sec。"""
    deadline = time.time() + max(0.0, wait_sec)
    while True:
        task = claim_pending_task(user_id, bridge_id)
        if task:
            return task
        if time.time() >= deadline:
            return None
        time.sleep(0.35)


def put_result(user_id: Any, task_id: str, result: dict[str, Any]) -> dict[str, Any]:
    """回传结果；必须与任务归属 user_id 一致。"""
    tid = str(task_id or "").strip()
    if not tid:
        raise ValueError("task_id 为空")
    with _lock:
        meta = _read_json(_task_meta_path(tid))
        if not meta:
            try:
                from tools.ide_review.ide_audit import append_ide_audit

                append_ide_audit(
                    {
                        "event": "ide_result_rejected",
                        "reason": "unknown_task",
                        "user_id": user_id,
                        "task_id": tid,
                    }
                )
            except Exception:
                pass
            raise PermissionError("unknown_task")
        if str(meta.get("user_id")) != str(user_id):
            try:
                from tools.ide_review.ide_audit import append_ide_audit

                append_ide_audit(
                    {
                        "event": "ide_result_rejected",
                        "reason": "task_owner_mismatch",
                        "user_id": user_id,
                        "task_id": tid,
                        "owner_user_id": meta.get("user_id"),
                    }
                )
            except Exception:
                pass
            raise PermissionError("task_owner_mismatch")
        body = {
            "task_id": tid,
            "user_id": user_id,
            "finished_at": time.time(),
            **result,
        }
        # 不落盘过大的审计字段；结果文件可含 file_contents
        _write_json(_result_path(tid), body)
    try:
        from tools.ide_review.ide_audit import append_ide_audit

        append_ide_audit(
            {
                "event": "ide_result_submitted",
                "user_id": user_id,
                "task_id": tid,
                "status": body.get("status"),
                "files": (body.get("files") or [])[:40],
                "workspace_root": body.get("workspace_root") or meta.get("workspace_root"),
            }
        )
    except Exception:
        pass
    return body


def wait_result(
    task_id: str,
    timeout_sec: float | None = None,
    *,
    user_id: Any = None,
) -> dict[str, Any] | None:
    """等待结果；若传入 user_id 则校验任务归属。"""
    tid = str(task_id or "").strip()
    if user_id is not None:
        with _lock:
            meta = _read_json(_task_meta_path(tid))
        if meta and str(meta.get("user_id")) != str(user_id):
            raise PermissionError("task_owner_mismatch")
        if not meta:
            # 无 meta 的旧任务：拒绝跨用户盲等
            raise PermissionError("unknown_task")
    timeout = _TASK_WAIT_DEFAULT if timeout_sec is None else float(timeout_sec)
    deadline = time.time() + max(1.0, timeout)
    path = _result_path(tid)
    while time.time() < deadline:
        with _lock:
            data = _read_json(path)
        if data:
            if user_id is not None and str(data.get("user_id")) != str(user_id):
                raise PermissionError("task_owner_mismatch")
            return data
        time.sleep(0.25)
    return None


def submit_bridge_task(
    user_id: Any,
    *,
    intent: str,
    paths: list[str] | None = None,
    prompt: str = "",
    thread_id: str = "",
    timeout_sec: float | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """通用：入队并等待 Bridge 回传（code_review / read_files）。"""
    status = get_status(user_id)
    if not status.get("online"):
        return {
            "status": "offline",
            "provider": "bridge",
            "message": "未检测到 VS Code / 本地代码载体连接",
            "hint": _HINT_CONNECT_VSCODE,
            "findings": [],
            "file_contents": [],
            "diagnostics_count": {"P0": 0, "P1": 0, "P2": 0},
        }

    payload: dict[str, Any] = {
        "intent": intent,
        "paths": paths or [],
        "prompt": prompt or "",
        "thread_id": thread_id or "",
        "workspace_root": status.get("workspace_root") or "",
    }
    if extra:
        payload.update(extra)

    preferred = str(payload.get("workspace_root") or "").strip()
    if preferred:
        payload["workspace_root"] = preferred
    elif not status.get("workspace_ready"):
        # 无选定工程且当前未开文件夹
        return {
            "status": "no_workspace",
            "provider": "bridge",
            "carrier": status.get("carrier"),
            "message": "已连接载体，但 VS Code 未打开项目文件夹",
            "hint": _HINT_OPEN_FOLDER,
            "findings": [],
            "file_contents": [],
            "diagnostics_count": {"P0": 0, "P1": 0, "P2": 0},
        }

    task_id = enqueue_task(user_id, payload)
    result = wait_result(task_id, timeout_sec=timeout_sec, user_id=user_id)
    if not result:
        return {
            "status": "timeout",
            "provider": "bridge",
            "task_id": task_id,
            "message": "等待 VS Code Bridge 超时，请确认扩展仍连接且窗口未休眠",
            "findings": [],
            "file_contents": [],
            "diagnostics_count": {"P0": 0, "P1": 0, "P2": 0},
        }
    out = dict(result)
    out.setdefault("provider", "bridge")
    out.setdefault("task_id", task_id)
    return out


def submit_review_task(
    user_id: Any,
    *,
    paths: list[str] | None,
    prompt: str = "",
    thread_id: str = "",
    timeout_sec: float | None = None,
    workspace_root: str | None = None,
) -> dict[str, Any]:
    """代码审核：要求 Bridge 带回 file_contents，避免服务端 read_file 读本机路径。"""
    extra: dict[str, Any] = {"include_file_contents": True}
    root = (workspace_root or "").strip()
    if root:
        extra["workspace_root"] = root
    return submit_bridge_task(
        user_id,
        intent="code_review",
        paths=paths,
        prompt=prompt,
        thread_id=thread_id,
        timeout_sec=timeout_sec,
        extra=extra,
    )


def submit_read_files_task(
    user_id: Any,
    *,
    paths: list[str],
    thread_id: str = "",
    timeout_sec: float | None = None,
    workspace_root: str | None = None,
) -> dict[str, Any]:
    """按相对路径（或工作区内绝对路径）经 Bridge 读取本机文件内容。"""
    if not paths:
        return {
            "status": "error",
            "message": "paths 不能为空",
            "hint": "请传入工作区相对路径，如 src/main/java/.../Foo.java",
            "file_contents": [],
            "files": [],
        }
    extra: dict[str, Any] = {}
    root = (workspace_root or "").strip()
    if root:
        extra["workspace_root"] = root
    return submit_bridge_task(
        user_id,
        intent="read_files",
        paths=paths,
        thread_id=thread_id,
        timeout_sec=timeout_sec,
        extra=extra or None,
    )
