"""本机工作区安全读文件（供 Python Bridge 与冒烟复用）。"""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

# 单文件 / 总字节 / 文件数上限，避免撑爆 Agent 上下文
MAX_FILE_BYTES = int(os.getenv("IDE_BRIDGE_MAX_FILE_BYTES", str(80 * 1024)))
MAX_TOTAL_BYTES = int(os.getenv("IDE_BRIDGE_MAX_TOTAL_BYTES", str(240 * 1024)))
MAX_FILES = int(os.getenv("IDE_BRIDGE_MAX_FILES", "8"))

# 敏感文件名（basename）与后缀：拒绝读入审核上下文
_SENSITIVE_BASENAMES = {
    ".env",
    ".env.local",
    ".env.production",
    ".env.development",
    ".env.staging",
    "id_rsa",
    "id_dsa",
    "id_ecdsa",
    "id_ed25519",
    "credentials.json",
    "service-account.json",
    "secrets.json",
    ".npmrc",
    ".pypirc",
}
_SENSITIVE_SUFFIXES = {
    ".pem",
    ".key",
    ".p12",
    ".pfx",
    ".jks",
    ".keystore",
}
_SENSITIVE_NAME_RE = re.compile(
    r"(^|/)(\.env(\.|$)|.*\.(pem|key|p12|pfx|jks)|id_(rsa|dsa|ecdsa|ed25519)|credentials\.json)$",
    re.I,
)


def is_sensitive_rel(rel: str) -> str | None:
    """若敏感则返回拒绝原因，否则 None。"""
    r = (rel or "").replace("\\", "/").strip()
    if not r:
        return None
    base = Path(r).name
    if base in _SENSITIVE_BASENAMES:
        return f"拒绝读取敏感文件: {rel}"
    low = base.lower()
    for suf in _SENSITIVE_SUFFIXES:
        if low.endswith(suf):
            return f"拒绝读取敏感文件: {rel}"
    if _SENSITIVE_NAME_RE.search(r):
        return f"拒绝读取敏感文件: {rel}"
    return None


def to_workspace_relative(workspace_root: Path, raw: str) -> tuple[str | None, str | None]:
    """返回 (relative_posix, error)。允许相对路径或位于 workspace 下的绝对路径。"""
    root = workspace_root.resolve()
    s = (raw or "").strip()
    if not s:
        return None, "空路径"
    p = Path(s)
    if p.is_absolute():
        try:
            cand = p.resolve()
            rel = cand.relative_to(root)
        except Exception:
            return None, f"路径不在工作区内: {s}"
    else:
        if ".." in Path(s).parts:
            return None, f"拒绝路径穿越: {s}"
        cand = (root / s).resolve()
        try:
            rel = cand.relative_to(root)
        except Exception:
            return None, f"路径不在工作区内: {s}"
    rel_s = rel.as_posix()
    sens = is_sensitive_rel(rel_s)
    if sens:
        return None, sens
    return rel_s, None


def read_workspace_files(
    workspace_root: Path,
    paths: list[str] | None,
    *,
    max_files: int = MAX_FILES,
    max_file_bytes: int = MAX_FILE_BYTES,
    max_total_bytes: int = MAX_TOTAL_BYTES,
    audit_user_id: Any = None,
) -> dict[str, Any]:
    """安全读取工作区文件，返回 file_contents 结构。"""
    root = workspace_root.resolve()
    raw_paths = [p for p in (paths or []) if p and str(p).strip()]
    items: list[dict[str, Any]] = []
    errors: list[str] = []
    total = 0

    for raw in raw_paths[: max(1, max_files)]:
        rel, err = to_workspace_relative(root, str(raw))
        if err or not rel:
            errors.append(err or f"无效路径: {raw}")
            if err and ("穿越" in err or "敏感" in err or "不在工作区" in err):
                try:
                    from tools.ide_review.ide_audit import append_ide_audit

                    append_ide_audit(
                        {
                            "event": "ide_path_rejected",
                            "user_id": audit_user_id,
                            "path": str(raw)[:500],
                            "reason": err,
                            "workspace_root": str(root),
                        }
                    )
                except Exception:
                    pass
            continue
        abs_path = (root / rel).resolve()
        if not abs_path.is_file():
            errors.append(f"文件不存在: {rel}")
            continue
        try:
            data = abs_path.read_bytes()
        except OSError as e:
            errors.append(f"读取失败 {rel}: {e}")
            continue
        truncated = False
        if len(data) > max_file_bytes:
            data = data[:max_file_bytes]
            truncated = True
        if total + len(data) > max_total_bytes:
            errors.append(f"达到总字节上限，跳过后续文件（已读 {len(items)} 个）")
            break
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            text = data.decode("utf-8", errors="replace")
            truncated = True
        total += len(data)
        items.append(
            {
                "path": rel,
                "content": text,
                "bytes": len(data),
                "truncated": truncated,
            }
        )

    return {
        "status": "ok" if items else "error",
        "workspace_root": str(root),
        "file_contents": items,
        "files": [i["path"] for i in items],
        "errors": errors,
        "provider": "bridge",
        "raw_summary": f"已读取 {len(items)} 个文件（共 {total} 字节）",
    }
