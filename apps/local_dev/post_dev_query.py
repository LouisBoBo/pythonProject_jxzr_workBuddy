"""本机写码成功后，对数据侧变更做一次轻量自动查数（D→B）。

设计约束（不挡正常写码）：
- 默认只在「像数据/字段变更」或「同步了 API 文件」时触发
- 纯 CSS / 视觉复刻不跑
- 任何异常只写入摘要，绝不抛出、不改 job 成功状态
- MES_POST_DEV_QUERY=0 可关
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Any

from .mes_profile_sync import synced_touches_api
from .stack_chain import looks_like_data_ui_change

logger = logging.getLogger(__name__)

_AGENT_DIR = Path(__file__).resolve().parents[1] / "agent"
_DEFAULT_LIMIT = 5
_MAX_TABLE_CHARS = 1200
_MAX_ROWS_IN_SUMMARY = 3


def _ensure_agent_path() -> bool:
    try:
        if str(_AGENT_DIR) not in sys.path:
            sys.path.insert(0, str(_AGENT_DIR))
        import tools.query_tool.platform_query  # noqa: F401

        return True
    except Exception:  # noqa: BLE001
        return False


def should_run_post_dev_query(
    requirement: str,
    synced_files: list[str] | None = None,
) -> tuple[bool, str]:
    """是否应自动查数。返回 (要跑, 原因)。"""
    if looks_like_data_ui_change(requirement or ""):
        return True, "需求涉及数据/字段/列表变更"
    if synced_touches_api(synced_files or []):
        return True, "本次同步包含 API 相关文件"
    return False, "非数据侧变更，跳过自动查数"


def resolve_query_target(requirement: str) -> dict[str, Any] | None:
    """从需求话术解析当前资料包中的实体；解析不到返回 None。"""
    if not _ensure_agent_path():
        return None
    from tools.query_tool.entity_catalog import get_entity, resolve_entity_id

    intent = (requirement or "").strip()
    if not intent:
        return None
    eid = resolve_entity_id(intent)
    if not eid:
        return None
    ent = get_entity(eid)
    if not ent:
        return {"id": eid, "label": eid}
    return {
        "id": str(ent.get("id") or eid),
        "label": str(ent.get("label") or eid),
        "path": str(ent.get("path") or ""),
    }


def run_post_dev_query(
    *,
    requirement: str,
    synced_files: list[str] | None = None,
    enabled: bool = True,
    limit: int = _DEFAULT_LIMIT,
) -> dict[str, Any]:
    """写码成功后调用：轻量 query，失败也返回结构化结果。"""
    result: dict[str, Any] = {
        "skipped": True,
        "ok": True,
        "entity": None,
        "label": None,
        "returned": None,
        "total": None,
        "error": None,
        "markdown_table": "",
        "notes": [],
    }
    if not enabled:
        result["reason"] = "MES_POST_DEV_QUERY 已关闭"
        return result

    want, reason = should_run_post_dev_query(requirement, synced_files)
    if not want:
        result["reason"] = reason
        return result

    if not _ensure_agent_path():
        result["skipped"] = False
        result["ok"] = False
        result["error"] = "agent 查数模块不可用"
        return result

    target = resolve_query_target(requirement)
    if not target:
        result["reason"] = "未能从需求匹配到资料包实体，跳过自动查数（可在对话里手动查）"
        result["notes"].append(reason)
        return result

    eid = target["id"]
    label = target.get("label") or eid
    result["skipped"] = False
    result["entity"] = eid
    result["label"] = label
    result["notes"].append(reason)
    result["notes"].append(f"自动查「{label}」(`{eid}`)，limit={max(1, min(int(limit or 5), 20))}")

    try:
        from tools.query_tool.platform_query import query_platform_data

        cap = max(1, min(int(limit or _DEFAULT_LIMIT), 20))
        raw = query_platform_data(eid, filters=None, limit=cap)
    except Exception as exc:  # noqa: BLE001
        logger.warning("post_dev_query failed: %s", exc)
        result["ok"] = False
        result["error"] = f"{type(exc).__name__}: {exc}"
        return result

    if not isinstance(raw, dict):
        result["ok"] = False
        result["error"] = "查数返回格式异常"
        return result

    if raw.get("error"):
        result["ok"] = False
        result["error"] = str(raw.get("error"))
        # 附带少量上下文，便于排障，不泄露密钥
        for k in ("hint", "status_code", "message"):
            if raw.get(k):
                result["notes"].append(f"{k}={raw[k]}")
        return result

    result["ok"] = True
    result["returned"] = raw.get("returned")
    result["total"] = raw.get("total")
    table = str(raw.get("markdown_table") or "").strip()
    if len(table) > _MAX_TABLE_CHARS:
        table = table[: _MAX_TABLE_CHARS] + "\n…（已截断）"
    result["markdown_table"] = table
    rows = raw.get("display_rows")
    if isinstance(rows, list) and rows:
        result["sample_rows"] = rows[:_MAX_ROWS_IN_SUMMARY]
    return result


def format_post_dev_query_summary(result: dict[str, Any] | None) -> str:
    """写入写码成功摘要的 Markdown；跳过且无原因时返回空串。"""
    if not result:
        return ""
    if result.get("skipped"):
        reason = str(result.get("reason") or "").strip()
        if not reason:
            return ""
        # 非数据侧跳过不打扰用户；仅当显式关闭或「匹配不到实体」时提示
        if reason.startswith("非数据侧"):
            return ""
        return f"### 改后自动查数\n\n- 已跳过：{reason}\n\n"

    lines = ["### 改后自动查数", ""]
    for note in result.get("notes") or []:
        lines.append(f"- {note}")
    label = result.get("label") or result.get("entity") or "?"
    eid = result.get("entity") or "?"
    if result.get("ok"):
        returned = result.get("returned")
        total = result.get("total")
        lines.append(f"- 结果：`{label}` (`{eid}`) 返回 {returned} 条" + (f"（接口共 {total}）" if total is not None else ""))
        table = str(result.get("markdown_table") or "").strip()
        if table:
            lines.append("")
            lines.append(table)
            lines.append("")
        lines.append("- 说明：此为写码后自动抽检，不替代对话里完整验收。")
    else:
        err = str(result.get("error") or "未知错误")
        lines.append(f"- 自动查数未成功（**不影响本次写码结果**）：{err}")
        lines.append("- 请在对话里手动查相关列表，或检查 MES 是否可达 / 接口账号。")
    lines.append("")
    return "\n".join(lines)
