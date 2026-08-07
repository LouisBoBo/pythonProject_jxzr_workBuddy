"""
Agent 包装器 — 将 apps/agent 的 Agent 封装为服务端可调用接口。

stream_chat 产出结构化事件（面向流畅 UI）：
  status  — 短状态文案
  step    — 可更新步骤（同一 tool 的 start/end 共用 run_id）
  token   — 正文
"""
from __future__ import annotations

import json
import re
import sys
import uuid
from pathlib import Path
from typing import Any, AsyncIterator

REPO_ROOT = Path(__file__).resolve().parents[2]
AGENT_PATH = REPO_ROOT / "apps" / "agent"
if str(AGENT_PATH) not in sys.path:
    sys.path.insert(0, str(AGENT_PATH))

from agents.agent import create_agent, build_model  # noqa: E402
from checkpoint_store import ensure_thread_messages, get_acheckpointer  # noqa: E402
from middleware.request_context import get_thread_id, get_user_id, get_username  # noqa: E402

# 核心双路由：code_dev（写码）与 code_review（审核）对等互斥，按意图分叉，无优先级
LANE_CODE_DEV = "code_dev"
LANE_CODE_REVIEW = "code_review"

_CODE_DEV_MARKERS = (
    "【写码需求讨论",
    "【写码仓库已确认】",
    ":::cursor_dev_options",
    ":::cursor_dev_propose",
    "【系统强制路由·Cursor 写码】",
)

_CODE_REVIEW_MARKERS = (
    "【Git仓库已确认】",
    "【本机工程已确认】",
    "【系统强制路由·公开 Git 全仓审核】",
    "【系统强制路由·本机代码审核】",
)


def resolve_workbuddy_lane(message: str = "", ctx: dict | None = None) -> str | None:
    """根据本轮显式车道声明 / 确认标记解析意图分支。

    返回 LANE_CODE_DEV | LANE_CODE_REVIEW | None。
    不使用「谁优先」：前端按用户意图选分支后写入 workbuddy_lane；
    若缺失则仅认对应确认标记，两路互不抢占。
    """
    ctx = ctx or {}
    explicit = str(ctx.get("workbuddy_lane") or "").strip()
    if explicit in (LANE_CODE_DEV, LANE_CODE_REVIEW):
        return explicit

    m = message or ""
    # 确认标记互斥：同一条消息不应同时带两套标记；若冲突则两边都不猜，交给前端重试
    has_dev = any(x in m for x in _CODE_DEV_MARKERS) or bool(
        ctx.get("cursor_dev_lane")
    ) or bool(str(ctx.get("cursor_dev_repo") or "").strip())
    has_review = any(x in m for x in _CODE_REVIEW_MARKERS) or bool(
        str(ctx.get("git_repo_url") or "").strip()
    ) or bool(str(ctx.get("ide_workspace_root") or "").strip())

    if has_dev and has_review:
        # 冲突时：以显式确认标记为准——写码讨论标记与审核确认标记同时出现极少见
        if any(x in m for x in _CODE_DEV_MARKERS) and not any(
            x in m for x in ("【Git仓库已确认】", "【本机工程已确认】")
        ):
            return LANE_CODE_DEV
        if any(x in m for x in ("【Git仓库已确认】", "【本机工程已确认】")):
            return LANE_CODE_REVIEW
        return None
    if has_dev:
        return LANE_CODE_DEV
    if has_review:
        return LANE_CODE_REVIEW
    return None


def _is_cursor_dev_coding_lane(message: str = "", ctx: dict | None = None) -> bool:
    """兼容旧调用：是否为写码分支。"""
    return resolve_workbuddy_lane(message, ctx) == LANE_CODE_DEV


# 工具 → 中文短标题（过程区只显示这些，不 dump 原始内容）
_TOOL_LABELS = {
    "query_platform_data": "查询平台数据",
    "list_platform_entities": "列出可查实体",
    "get_platform_summary": "汇总平台数据",
    "describe_entity": "查看实体结构",
    "read_file": "读取文件",
    "write_file": "写入文件",
    "edit_file": "编辑文件",
    "ls": "浏览目录",
    "glob": "搜索文件",
    "grep": "检索内容",
    "execute": "执行命令",
    "import_file_to_platform": "导入平台数据",
    "export_platform_data": "导出平台数据",
    "preview_file": "预览文件",
    "transform_file": "转换文件",
    "query_write_audit": "查询导入审计",
    "list_schema_domains": "列出表结构业务域",
    "list_schema_tables": "检索表结构",
    "describe_schema_table": "查看表结构详情",
    "analyze_schema_capabilities": "分析业务能力",
    "rebuild_schema_index": "重建表结构索引",
    "list_business_scenarios": "列出业务场景表包",
    "get_scenario_table_pack": "获取场景相关表",
    "export_schema_survey_report": "导出摸底报告",
    "list_platform_capabilities": "人话能力地图",
    "describe_platform_capability": "能力模块详情",
    "list_platform_glossary": "术语小抄",
    "build_api_catalog": "构建接口目录",
    "list_api_catalog": "列出接口目录",
    "query_api_call_log": "查询接口调用日志",
    "summarize_api_doc_vs_logs": "汇总接口健康",
    "rank_problematic_apis": "问题接口排行",
    "inspect_api_path": "抽查接口路径",
    "probe_api_catalog": "沙箱探活接口",
    "render_api_health_report": "生成接口测试报告",
    "import_external_api_logs": "导入外部访问日志",
    "analyze_api_errors_from_logs": "分析接口错误",
    "request_ide_review": "本地代码审核",
    "request_ide_list_source_files": "筛选功能源码",
    "request_ide_read_batch": "分批读取功能代码",
    "request_ide_read_files": "按路径读取本机工程文件",
    # 与本机 IDE 过程卡文案对齐，便于 Git 全仓审观感一致
    "request_git_list_source_files": "筛选功能源码",
    "request_git_read_batch": "分批读取功能代码",
    "request_git_review": "Git/本地抽样审核",
}

_IDE_BATCH_TOOLS = frozenset(
    {
        "request_ide_list_source_files",
        "request_ide_read_batch",
        "request_ide_read_files",
        "request_git_list_source_files",
        "request_git_read_batch",
    }
)

_IDE_REPORT_MARKERS = (
    "## 🔍 代码审核报告",
    "🔍 代码审核报告",
    "## 代码审核报告",
    "代码审核报告",
)


def _find_ide_report_start(buf: str) -> int:
    best = -1
    for m in _IDE_REPORT_MARKERS:
        i = buf.find(m)
        if i >= 0 and (best < 0 or i < best):
            best = i
    return best


def _drop_leading_english_aside(buf: str) -> str:
    """丢掉终稿前的英文旁白行，保留从中文/报告标题起的内容。"""
    if not buf:
        return buf
    idx = _find_ide_report_start(buf)
    if idx >= 0:
        return buf[idx:]
    lines = buf.splitlines(keepends=True)
    kept: list[str] = []
    started = False
    for line in lines:
        raw = line.strip()
        if not started:
            if not raw:
                continue
            # 纯 ASCII / 常见英文过渡句 → 丢弃
            letters = [c for c in raw if c.isalpha()]
            ascii_letters = [c for c in letters if ord(c) < 128]
            if letters and len(ascii_letters) / max(1, len(letters)) > 0.85:
                continue
            if re.match(
                r"^(Now |Let me |I have |Here is |I'll |I will |Compiling |Based on )",
                raw,
                re.I,
            ):
                continue
            started = True
        kept.append(line)
    return "".join(kept) if kept else ""

_LINE_PREFIX = re.compile(r"(?m)^\s*\d+\|")


def _unwrap_content(obj: Any) -> Any:
    if obj is None:
        return None
    if hasattr(obj, "content") and not isinstance(obj, (str, dict, list)):
        return _unwrap_content(getattr(obj, "content", None))
    if isinstance(obj, list):
        # multimodal / content blocks
        texts = []
        for block in obj:
            if isinstance(block, str):
                texts.append(block)
            elif isinstance(block, dict) and block.get("type") == "text":
                texts.append(str(block.get("text") or ""))
        if texts:
            return "\n".join(texts)
    return obj


def _as_text(obj: Any) -> str:
    obj = _unwrap_content(obj)
    if obj is None:
        return ""
    if isinstance(obj, str):
        return obj
    if isinstance(obj, dict):
        try:
            return json.dumps(obj, ensure_ascii=False, default=str)
        except Exception:
            return str(obj)
    return str(obj)


def _strip_line_numbers(text: str) -> str:
    """FilesystemBackend 常返回 `1|content` 行号前缀。"""
    if not text:
        return text
    if _LINE_PREFIX.search(text[:200]):
        return _LINE_PREFIX.sub("", text)
    return text


def _parse_jsonish(obj: Any) -> Any:
    obj = _unwrap_content(obj)
    if isinstance(obj, (dict, list)):
        return obj
    if isinstance(obj, str):
        s = _strip_line_numbers(obj).strip()
        if s.startswith("{") or s.startswith("["):
            try:
                return json.loads(s)
            except Exception:
                pass
        # Tool 输出偶发夹带前后缀，尝试截取首个 JSON 对象
        extracted = _extract_json_object(s)
        if extracted is not None:
            return extracted
        return s
    return obj


def _extract_json_object(text: str) -> Any | None:
    if not text or "__write_confirm__" not in text and "pending_confirmation" not in text:
        # 仍尝试通用截取
        start = text.find("{") if text else -1
    else:
        start = text.find("{")
    if start < 0:
        return None
    # 从第一个 { 起做括号匹配
    depth = 0
    in_str = False
    esc = False
    for i in range(start, len(text)):
        ch = text[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                chunk = text[start : i + 1]
                try:
                    return json.loads(chunk)
                except Exception:
                    return None
    return None


def _entity_hint(inp: Any) -> str:
    data = _parse_jsonish(inp)
    if isinstance(data, dict):
        entity = data.get("entity") or data.get("target_entity") or ""
        if entity:
            return str(entity)
        path = data.get("file_path") or data.get("path") or ""
        if path:
            name = str(path).rstrip("/").split("/")[-1]
            return name
    return ""


def _input_detail(name: str, inp: Any) -> str:
    """调用参数：多行可读说明。"""
    data = _parse_jsonish(inp)
    if not isinstance(data, dict):
        text = _as_text(inp).strip()
        return text[:240] + ("…" if len(text) > 240 else "") if text else ""

    lines: list[str] = []
    if name == "query_platform_data":
        if data.get("entity"):
            lines.append(f"实体：{data['entity']}")
        if data.get("filters"):
            try:
                lines.append(f"筛选：{json.dumps(data['filters'], ensure_ascii=False)}")
            except Exception:
                lines.append(f"筛选：{data['filters']}")
        if data.get("limit") is not None:
            lines.append(f"条数上限：{data['limit']}")
        if data.get("output_format"):
            lines.append(f"格式：{data['output_format']}")
    elif name == "read_file":
        path = data.get("file_path") or data.get("path") or ""
        if path:
            lines.append(f"路径：{path}")
        if data.get("limit") is not None:
            lines.append(f"读取行数：{data['limit']}")
    elif name in ("import_file_to_platform", "export_platform_data"):
        for k in ("entity", "target_entity", "file_path", "output_format"):
            if data.get(k):
                lines.append(f"{k}：{data[k]}")
    elif name in (
        "request_ide_read_batch",
        "request_git_read_batch",
        "request_ide_list_source_files",
        "request_git_list_source_files",
    ):
        if data.get("batch_index") is not None:
            lines.append(f"batch_index：{data['batch_index']}")
        # 与 IDE 图二严格一致：第二行固定为 workspace_root（本机/克隆根绝对路径）
        root = str(data.get("workspace_root") or "").strip()
        if not root and name.startswith("request_git"):
            try:
                from middleware.request_context import get_thread_id
                from tools.ide_review.git_review import get_git_workspace_root

                root = get_git_workspace_root(get_thread_id())
            except Exception:
                root = ""
        if not root and name.startswith("request_ide"):
            try:
                from middleware.request_context import get_page_context

                ctx = get_page_context() or {}
                root = str(ctx.get("ide_workspace_root") or "").strip()
            except Exception:
                root = ""
        # 勿把 https URL 当成 workspace_root 展示
        if root.startswith("http://") or root.startswith("https://"):
            root = ""
            if name.startswith("request_git"):
                try:
                    from middleware.request_context import get_thread_id
                    from tools.ide_review.git_review import get_git_workspace_root

                    root = get_git_workspace_root(get_thread_id())
                except Exception:
                    root = ""
        if root:
            lines.append(f"workspace_root：{root}")
        for k, v in list(data.items())[:6]:
            if k in ("batch_index", "workspace_root", "repo_url") or v is None or v == "":
                continue
            sv = v if not isinstance(v, (dict, list)) else json.dumps(v, ensure_ascii=False)
            sv = str(sv)
            if len(sv) > 120:
                sv = sv[:120] + "…"
            lines.append(f"{k}：{sv}")
    else:
        for k, v in list(data.items())[:6]:
            if v is None or v == "":
                continue
            sv = v if not isinstance(v, (dict, list)) else json.dumps(v, ensure_ascii=False)
            sv = str(sv)
            if len(sv) > 120:
                sv = sv[:120] + "…"
            lines.append(f"{k}：{sv}")
    return "\n".join(lines)


def _result_detail(name: str, out: Any) -> tuple[str, list[str]]:
    """
    返回 (摘要, 预览行列表)。
    查询结果展示样例记录；Skill 展示 name/description；避免整文件 dump。
    """
    data = _parse_jsonish(out)
    preview: list[str] = []

    if isinstance(data, dict):
        if data.get("error"):
            return f"失败：{data.get('error')}", [str(data.get("hint") or data.get("next") or "")[:200]] if (data.get("hint") or data.get("next")) else []

        st = str(data.get("status") or "").strip().lower()
        if st in {
            "error",
            "timeout",
            "offline",
            "no_workspace",
            "denied",
            "failed",
        }:
            msg = str(
                data.get("message") or data.get("raw_summary") or st
            ).strip() or "工具失败"
            return f"失败：{msg[:280]}", []

        if data.get("_rerouted_from"):
            imported = data.get("imported")
            summary = (
                f"已自动导入访问日志 {imported} 条"
                if imported is not None
                else "已改走访问日志导入"
            )
            preview = []
            if data.get("note"):
                preview.append(str(data["note"])[:280])
            if data.get("next"):
                preview.append(f"下一步：{data['next']}")
            return summary, preview

        if data.get("status") == "pending_confirmation" or data.get("__write_confirm__"):
            summary = data.get("summary") or "等待确认写入"
            preview_rows = []
            pv = data.get("preview") if isinstance(data.get("preview"), dict) else {}
            for row in (pv.get("sample_rows") or [])[:3]:
                if isinstance(row, dict):
                    preview_rows.append(" · ".join(f"{k}={v}" for k, v in list(row.items())[:4]))
                else:
                    preview_rows.append(str(row)[:100])
            return f"待确认：{summary}", preview_rows

        if name in ("request_ide_list_source_files", "request_git_list_source_files"):
            total = data.get("total")
            bc = data.get("batch_count")
            filt = data.get("filter") or "functional_source_only"
            trunc = "（已达枚举上限）" if data.get("truncated") else ""
            summary = f"功能源码 {total} 个 / {bc} 批{trunc}"
            preview = [str(data.get("raw_summary") or "")[:200]]
            if filt:
                preview.append("已排除配置与非核心文件")
            return summary, [p for p in preview if p]

        if name in ("request_ide_read_batch", "request_git_read_batch"):
            bi = data.get("batch_index")
            bc = data.get("batch_count")
            # 优先用完整相对路径列表（含目录前缀）；勿只用 basename
            files = [
                str(p).replace("\\", "/").strip()
                for p in (data.get("files") or [])
                if str(p).strip()
            ]
            if not files:
                files = [
                    str(x.get("path") or "").replace("\\", "/").strip()
                    for x in (data.get("file_contents") or [])
                    if isinstance(x, dict) and str(x.get("path") or "").strip()
                ]
            nfiles = len(files) or len(data.get("file_contents") or [])
            if bi is not None and bc:
                summary = f"第 {int(bi) + 1}/{bc} 批 · 已读 {nfiles} 个文件"
            else:
                summary = f"本批已读 {nfiles} 个文件"
            if data.get("done_after"):
                summary += "（末批，即将汇总报告）"
            return summary, files[:8]

        if "total" in data or "records" in data:
            entity = data.get("entity") or ""
            total = data.get("total")
            records = data.get("records") if isinstance(data.get("records"), list) else []
            if total is None:
                total = len(records)
            summary = f"查询完成：{entity} 共 {total} 条" if entity else f"查询完成：共 {total} 条"
            for row in records[:4]:
                if not isinstance(row, dict):
                    preview.append(str(row)[:100])
                    continue
                bits = []
                for key in (
                    "plan_no",
                    "order_no",
                    "work_order_no",
                    "product_name",
                    "name",
                    "status",
                    "line_name",
                    "qty",
                    "plan_qty",
                    "id",
                ):
                    if key in row and row[key] is not None:
                        bits.append(f"{key}={row[key]}")
                if not bits:
                    bits = [f"{k}={v}" for k, v in list(row.items())[:4]]
                preview.append(" · ".join(bits))
            if total and total > len(preview):
                preview.append(f"… 其余 {total - len(preview)} 条已省略")
            return summary, preview

        if "entities" in data and isinstance(data["entities"], list):
            ents = data["entities"]
            summary = f"可用实体 {len(ents)} 个"
            for e in ents[:8]:
                if isinstance(e, dict):
                    preview.append(str(e.get("id") or e.get("name") or e))
                else:
                    preview.append(str(e))
            return summary, preview

    text = _strip_line_numbers(_as_text(out)).strip()
    # 虚拟 FS / 路径错误：不要误标成「已读取技能说明」
    if re.search(r"path_not_found|Error:\s*Path|文件不存在|FileNotFound", text, re.I):
        return f"失败：{text[:200]}", []

    looks_like_skill = (
        name == "read_file"
        and ("name:" in text[:200] and "description:" in text[:800])
        and ("analyze-" in text[:400] or "skill" in text[:400].lower())
    )
    if looks_like_skill or (
        text.lstrip().startswith("---")
        and "name:" in text[:200]
        and "description:" in text[:800]
        and name == "read_file"
    ):
        skill = ""
        desc = ""
        for line in text.splitlines()[:40]:
            if line.startswith("name:"):
                skill = line.split(":", 1)[1].strip().strip("'\"")
            elif line.startswith("description:"):
                desc = line.split(":", 1)[1].strip().strip("'\"")
        summary = f"已读取技能：{skill}" if skill else "已读取技能说明"
        if desc:
            preview.append(desc[:220] + ("…" if len(desc) > 220 else ""))
        return summary, preview

    if not text:
        return "完成", []
    if len(text) > 360:
        return "完成", [text[:360] + "…"]
    return "完成", [text]


def _is_tool_failure(detail_src: Any) -> bool:
    data = _parse_jsonish(detail_src)
    if isinstance(data, dict):
        if data.get("status") == "pending_confirmation" or data.get("__write_confirm__"):
            return False
        # 访问日志被中间件改走导入：原工具名虽是 read_file，但实际已成功
        if data.get("_rerouted_from") and not data.get("error"):
            return False
        if data.get("error"):
            return True
        # IDE/Git 工具以 status + message 表达失败（无 error 字段）
        st = str(data.get("status") or "").strip().lower()
        if st in {
            "error",
            "timeout",
            "offline",
            "no_workspace",
            "denied",
            "failed",
        }:
            return True
    if isinstance(data, str):
        s = data.strip()
        if s.startswith("实体守卫") or s.startswith("[错误]"):
            return True
        if len(s) <= 240 and (s.lower().startswith("error") or "失败" in s[:40]):
            return True
    return False


def _extract_write_confirm(detail_src: Any) -> dict[str, Any] | None:
    data = _parse_jsonish(detail_src)
    if isinstance(data, str):
        data = _extract_json_object(data) or data
    if not isinstance(data, dict):
        # 再扫一遍原始文本
        text = _as_text(detail_src)
        data = _extract_json_object(text) if text else None
    if not isinstance(data, dict):
        return None
    if not (data.get("__write_confirm__") or data.get("status") == "pending_confirmation"):
        return None
    if not data.get("action_id"):
        return None
    return data


def _confirm_from_pending_store(thread_id: str, tool_name: str | None = None) -> dict[str, Any] | None:
    """兼容旧调用：返回第一条 pending。"""
    items = _confirms_from_pending_store(thread_id, tool_name)
    return items[0] if items else None


def _confirms_from_pending_store(thread_id: str, tool_name: str | None = None) -> list[dict[str, Any]]:
    """从落盘 pending 回补全部确认事件（多笔排队）。"""
    try:
        from middleware.write_store import list_pending
        from middleware.write_tools import WRITE_TOOLS
    except Exception:
        return []
    if tool_name and tool_name not in WRITE_TOOLS and tool_name != "import_file_to_platform":
        return []
    items = list_pending(thread_id=thread_id or "default")
    out: list[dict[str, Any]] = []
    for action in items:
        preview = action.get("preview") if isinstance(action.get("preview"), dict) else {}
        out.append(
            {
                "__write_confirm__": True,
                "status": "pending_confirmation",
                "action_id": action.get("action_id"),
                "tool": action.get("tool") or tool_name,
                "thread_id": action.get("thread_id") or thread_id,
                "expires_at": action.get("expires_at"),
                "summary": preview.get("summary") or "待确认写入平台",
                "preview": preview,
                "message": "写操作已挂起，请在界面确认或取消。",
            }
        )
    return out


def _tool_name(event: dict) -> str:
    name = event.get("name") or ""
    if name:
        return str(name)
    data = event.get("data") or {}
    return str(data.get("name") or data.get("tool") or "tool")


def _tool_label(name: str, inp: Any = None) -> str:
    base = _TOOL_LABELS.get(name, name)
    hint = _entity_hint(inp)
    if hint and name in ("query_platform_data", "import_file_to_platform", "export_platform_data"):
        return f"{base} · {hint}"
    if hint and name == "read_file":
        low = hint.lower()
        if "skill" in low or hint.endswith(".md") and "skill" in low:
            return "查阅技能说明"
        if low.endswith((".jsonl", ".log")) or "/uploads/" in low.replace("\\", "/"):
            return f"读取附件 {Path(hint).name}"
        return f"读取 {hint}"
    if name == "import_external_api_logs":
        return "导入外部访问日志"
    if name == "analyze_api_errors_from_logs":
        return "分析接口错误"
    if name in ("request_ide_read_batch", "request_git_read_batch"):
        data = _parse_jsonish(inp) if inp is not None else {}
        if isinstance(data, dict) and data.get("batch_index") is not None:
            return f"{base} · 第 {int(data['batch_index']) + 1} 批"
    if name in ("request_ide_list_source_files", "request_git_list_source_files"):
        return "筛选功能源码（排除配置/非核心）"
    return base


def _chunk_text(chunk: Any) -> str:
    if chunk is None:
        return ""
    content = getattr(chunk, "content", None)
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict) and block.get("type") == "text":
                parts.append(str(block.get("text") or ""))
            else:
                text = getattr(block, "text", None)
                if text:
                    parts.append(str(text))
        return "".join(parts)
    return str(content)


class AgentRunner:
    """单例 Agent 运行器，避免每次请求重新创建 Deep Agent。"""

    _instance = None
    # 工具集变更时 bump，避免热更新后仍复用旧 Agent（缺 request_git_*_batch）
    _TOOLS_SIG = "ide+git-batch-v3-report-format"

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._agent = None
            cls._instance._model = None
            cls._instance._agent_lock = None
            cls._instance._stream_lock = None
            cls._instance._agent_sig = None
        return cls._instance

    def _get_agent_lock(self):
        import asyncio

        if self._agent_lock is None:
            self._agent_lock = asyncio.Lock()
        return self._agent_lock

    def _get_stream_lock(self):
        """同一进程内串行 astream：AsyncSqliteSaver 单连接，并发会直接空流/掐断。"""
        import asyncio

        if self._stream_lock is None:
            self._stream_lock = asyncio.Lock()
        return self._stream_lock

    async def _ensure_agent(self):
        """挂 AsyncSqliteSaver 后创建 Agent（流式必需）。"""
        if self._agent is not None and getattr(self, "_agent_sig", None) == self._TOOLS_SIG:
            return self._agent
        async with self._get_agent_lock():
            if self._agent is not None and getattr(self, "_agent_sig", None) == self._TOOLS_SIG:
                return self._agent
            cp = await get_acheckpointer()
            self._model = build_model()
            self._agent = create_agent(model=self._model, checkpointer=cp)
            self._agent_sig = self._TOOLS_SIG
            return self._agent

    @property
    def agent(self):
        if self._agent is None:
            raise RuntimeError("Agent 未初始化：请先 await AgentRunner()._ensure_agent()")
        return self._agent

    def reset_agent(self) -> None:
        """网络/DNS 异常后丢弃单例，下次请求重建客户端（保留 checkpointer 连接）。"""
        self._agent = None
        self._model = None
        self._agent_sig = None

    def _run_config(self, thread_id: str) -> dict[str, Any]:
        from config import Config

        return {
            "configurable": {
                "thread_id": thread_id or get_thread_id() or "default",
                "user_id": get_user_id(),
                "username": get_username(),
            },
            # Deep Agents + Skills + 多工具任务易超过默认 25
            "recursion_limit": Config.AGENT_RECURSION_LIMIT,
        }

    def _build_message(self, message: str, file_paths: list[str] | None = None) -> str:
        prefix = ""
        try:
            from middleware.request_context import get_page_context

            ctx = get_page_context() or {}
            bits: list[str] = []
            if ctx.get("entity"):
                bits.append(f"entity={ctx['entity']}")
            if ctx.get("plan_no"):
                bits.append(f"plan_no={ctx['plan_no']}")
            if ctx.get("order_no"):
                bits.append(f"order_no={ctx['order_no']}")
            lane = resolve_workbuddy_lane(message or "", ctx)
            if lane == LANE_CODE_DEV:
                bits.append("workbuddy_lane=code_dev")
                repo = str(ctx.get("cursor_dev_repo") or "").strip()
                if repo:
                    bits.append(f"cursor_dev_repo={repo}")
            elif lane == LANE_CODE_REVIEW:
                bits.append("workbuddy_lane=code_review")
                ide_root = str(ctx.get("ide_workspace_root") or "").strip()
                if ide_root:
                    bits.append(f"ide_workspace_root={ide_root}")
                git_url = str(ctx.get("git_repo_url") or "").strip()
                if git_url:
                    bits.append(f"git_repo_url={git_url}")
                git_ref = str(ctx.get("git_ref") or "").strip()
                if git_ref:
                    bits.append(f"git_ref={git_ref}")
            else:
                ide_root = str(ctx.get("ide_workspace_root") or "").strip()
                if ide_root:
                    bits.append(f"ide_workspace_root={ide_root}")
                git_url = str(ctx.get("git_repo_url") or "").strip()
                if git_url:
                    bits.append(f"git_repo_url={git_url}")
                git_ref = str(ctx.get("git_ref") or "").strip()
                if git_ref:
                    bits.append(f"git_ref={git_ref}")
            if bits:
                prefix = (
                    "[平台上下文] 用户从 MES 页面打开助手，当前页："
                    + "，".join(bits)
                    + "。若问题指「这个/当前」计划或工单，优先用上述字段查询对应实体。\n\n"
                )
        except Exception:
            prefix = ""

        body = message
        # 写码 / 审核：对等互斥分支。仅按本轮意图注入对应强制路由，无「谁优先」。
        try:
            from middleware.request_context import get_page_context as _gpc

            _ctx = _gpc() or {}
            _git = str(_ctx.get("git_repo_url") or "").strip()
            _ide = str(_ctx.get("ide_workspace_root") or "").strip()
        except Exception:
            _ctx = {}
            _git = ""
            _ide = ""
        lane = resolve_workbuddy_lane(message or "", _ctx)
        if lane == LANE_CODE_DEV:
            force_coding = (
                "\n\n【系统强制路由·Cursor 写码】\n"
                "本轮意图=写码/改功能（workbuddy_lane=code_dev），与代码审核是另一条路由。\n"
                "禁止调用：request_git_*、request_ide_*（含 list_source_files / read_batch / review）。\n"
                "禁止 clone 仓库、禁止输出「代码审核报告」、禁止「筛选功能源码」。\n"
                "只澄清需求并输出 :::cursor_dev_options 或 :::cursor_dev_propose；"
                "改远程仓须用户确认后由 Cursor Cloud 执行。\n"
                "消息里出现 GitHub 仓库名/分支仅表示要改哪个仓，不等于审核意图。\n"
            )
            body = f"{body}{force_coding}"
        elif lane == LANE_CODE_REVIEW and (
            _git or _ide or "【Git仓库已确认】" in (message or "") or "【本机工程已确认】" in (message or "")
        ):
            if _git or "【Git仓库已确认】" in (message or ""):
                force_git = (
                    "\n\n【系统强制路由·公开 Git 全仓审核】\n"
                    "本轮意图=代码审核（workbuddy_lane=code_review），与写码是另一条路由。\n"
                    f"仓库：{_git or '见消息【Git仓库已确认】'}\n"
                    "必须严格按序：\n"
                    "1) request_git_list_source_files\n"
                    "2) request_git_read_batch(batch_index=0)…直至 done_after=true\n"
                    "3) 仅此时输出「## 🔍 代码审核报告」\n"
                    "禁止：request_git_review 抽样结案；禁止 request_ide_*；"
                    "禁止 :::cursor_dev_* 写码确认卡；禁止中途输出报告或英文过渡句。\n"
                )
                body = f"{body}{force_git}"
            elif _ide or "【本机工程已确认】" in (message or ""):
                force_ide = (
                    "\n\n【系统强制路由·本机代码审核】\n"
                    "本轮意图=代码审核（workbuddy_lane=code_review），与写码是另一条路由。\n"
                    f"工程：{_ide or '见消息【本机工程已确认】'}\n"
                    "必须严格按序：request_ide_list_source_files → request_ide_read_batch → 终稿报告。\n"
                    "禁止 :::cursor_dev_*；禁止把本轮当成写功能/改界面。\n"
                )
                body = f"{body}{force_ide}"
        elif lane is None and (_git or "【Git仓库已确认】" in (message or "")):
            # 兼容未带 workbuddy_lane 的旧审核入口
            force_git = (
                "\n\n【系统强制路由·公开 Git 全仓审核】\n"
                f"仓库：{_git or '见消息【Git仓库已确认】'}\n"
                "必须严格按序：\n"
                "1) request_git_list_source_files\n"
                "2) request_git_read_batch(batch_index=0)…直至 done_after=true\n"
                "3) 仅此时输出「## 🔍 代码审核报告」\n"
                "禁止：request_git_review 抽样结案；禁止 request_ide_*；"
                "禁止中途输出报告或英文过渡句。\n"
            )
            body = f"{body}{force_git}"

        if not file_paths:
            return prefix + body
        file_note = "\n".join([f"[附件路径]: {p}" for p in file_paths])
        log_paths = [
            p
            for p in file_paths
            if (
                str(p).lower().endswith((".jsonl", ".log"))
                or "api_access" in str(p).lower()
                or (
                    "/uploads/" in str(p).replace("\\", "/").lower()
                    and str(p).lower().endswith((".jsonl", ".log", ".csv", ".txt"))
                )
            )
        ]
        if log_paths:
            paths_block = "\n".join(f"- `{p}`" for p in log_paths)
            return (
                f"{prefix}{body}\n\n"
                "【系统强制路由·访问日志】检测到日志类附件。\n"
                f"{paths_block}\n\n"
                "禁止：read_file、ls、glob、transform_file、preview_file、build_api_catalog（这些会失败或误用）。\n"
                "必须：\n"
                f"1) import_external_api_logs(file_path=\"{log_paths[0]}\")\n"
                "2) analyze_api_errors_from_logs(source_filter=\"import\")  "
                "（不要 with_catalog、不要 docs_url；报告只谈本次日志条数与错误/正常接口）\n"
                "3) 用 report_markdown 回复。禁止把历史接口文档的接口总数写进本报告；"
                "文档探活请另走 build→probe→render_api_health_report。\n"
                f"\n其他附件：\n{file_note}"
            )
        return (
            f"{prefix}{body}\n\n用户已上传以下文件，请按需读取或导入：\n{file_note}\n"
            "若为访问日志（.log/.jsonl）：请 "
            "import_external_api_logs(file_path=上方绝对路径) → analyze_api_errors_from_logs；"
            "不要用 read_file。"
        )

    async def chat(
        self, message: str, thread_id: str = "default", file_paths: list[str] | None = None
    ) -> str:
        final_message = self._build_message(message, file_paths)
        config = self._run_config(thread_id)
        agent = await self._ensure_agent()
        await ensure_thread_messages(agent, thread_id, run_config=config)
        result = await agent.ainvoke(
            {"messages": [{"role": "user", "content": final_message}]},
            config=config,
        )
        last = result["messages"][-1]
        content = getattr(last, "content", last)
        return content if isinstance(content, str) else _as_text(content)

    async def stream_chat(
        self,
        message: str,
        thread_id: str = "default",
        file_paths: list[str] | None = None,
        *,
        cancel_event: Any = None,
    ) -> AsyncIterator[dict[str, Any]]:
        """异步流式事件：status / step / token / confirm。

        cancel_event: 可选 asyncio.Event，set 后尽快结束 astream（客户端断开/停止）。
        """
        lock = self._get_stream_lock()
        await lock.acquire()
        try:
            async for event in self._stream_chat_locked(
                message, thread_id, file_paths, cancel_event=cancel_event
            ):
                yield event
        finally:
            lock.release()

    async def _stream_chat_locked(
        self,
        message: str,
        thread_id: str = "default",
        file_paths: list[str] | None = None,
        *,
        cancel_event: Any = None,
    ) -> AsyncIterator[dict[str, Any]]:
        import asyncio

        final_message = self._build_message(message, file_paths)
        config = self._run_config(thread_id)
        agent = await self._ensure_agent()
        await ensure_thread_messages(agent, thread_id, run_config=config)
        yield {"type": "status", "text": "正在分析问题…"}
        await asyncio.sleep(0)

        saw_tool = False
        tool_ended = False
        generating_sent = False
        active_runs: set[str] = set()
        emitted_confirm_ids: set[str] = set()
        saw_write_tool = False
        # 全仓分批期间：模型旁白不进输出区；末批后等到「代码审核报告」标题再放行（丢掉英文过渡句）
        suppress_ide_report_tokens = False
        ide_await_report_header = False
        ide_report_buf = ""

        # 与昨天 ab15a1e 相同：直接 async for。
        # 禁止对 __anext__ 使用 wait_for 超时——超时会 Cancel 底层读，
        # 导致 on_chat_model_start 之后流被掐断、前端只看到空报告。
        try:
            async for event in agent.astream_events(
                {"messages": [{"role": "user", "content": final_message}]},
                config=config,
                version="v2",
            ):
                if cancel_event is not None and cancel_event.is_set():
                    break

                kind = event.get("event", "")

                if kind == "on_tool_start":
                    saw_tool = True
                    generating_sent = False  # 新工具轮次，取消生成态
                    name = _tool_name(event)
                    if name in ("import_file_to_platform", "import_platform_data"):
                        saw_write_tool = True
                    if name in _IDE_BATCH_TOOLS or name == "request_git_review":
                        suppress_ide_report_tokens = True
                    data = event.get("data") or {}
                    inp = data.get("input")
                    run_id = str(event.get("run_id") or uuid.uuid4())
                    active_runs.add(run_id)
                    inp_obj = _parse_jsonish(inp) if inp is not None else {}
                    batch_idx = None
                    if isinstance(inp_obj, dict) and inp_obj.get("batch_index") is not None:
                        try:
                            batch_idx = int(inp_obj["batch_index"])
                        except (TypeError, ValueError):
                            batch_idx = None
                    step_ev = {
                        "type": "step",
                        "id": run_id,
                        "tool": name,
                        "phase": "start",
                        "state": "running",
                        "title": _tool_label(name, inp),
                        "args": _input_detail(name, inp),
                        "detail": "",
                        "preview": [],
                    }
                    if batch_idx is not None:
                        step_ev["batch_index"] = batch_idx
                    yield step_ev
                    await asyncio.sleep(0.02)
                    continue

                if kind == "on_tool_end":
                    saw_tool = True
                    tool_ended = True
                    name = _tool_name(event)
                    if name in ("import_file_to_platform", "import_platform_data"):
                        saw_write_tool = True
                    data = event.get("data") or {}
                    out = data.get("output")
                    detail_src = _unwrap_content(out)
                    ok = not _is_tool_failure(detail_src)
                    run_id = str(event.get("run_id") or "")
                    if run_id and run_id in active_runs:
                        active_runs.discard(run_id)
                    else:
                        active_runs.clear()
                    if not run_id:
                        run_id = str(uuid.uuid4())
                    title = _tool_label(name, data.get("input"))
                    parsed = _parse_jsonish(detail_src)
                    if isinstance(parsed, dict) and parsed.get("entity"):
                        title = _tool_label(name, {"entity": parsed.get("entity")})
                    summary, preview = _result_detail(name, detail_src)
                    confirm = _extract_write_confirm(detail_src)
                    confirms = []
                    if confirm and confirm.get("action_id"):
                        confirms = [confirm]
                    elif name in (
                        "import_file_to_platform",
                        "import_platform_data",
                    ):
                        confirms = _confirms_from_pending_store(thread_id, name)
                    step_state = "waiting" if confirms else ("done" if ok else "error")
                    batch_idx = None
                    inp_obj = _parse_jsonish(data.get("input")) if data.get("input") is not None else {}
                    if isinstance(inp_obj, dict) and inp_obj.get("batch_index") is not None:
                        try:
                            batch_idx = int(inp_obj["batch_index"])
                        except (TypeError, ValueError):
                            batch_idx = None
                    if batch_idx is None and isinstance(parsed, dict) and parsed.get("batch_index") is not None:
                        try:
                            batch_idx = int(parsed["batch_index"])
                        except (TypeError, ValueError):
                            batch_idx = None
                    end_ev = {
                        "type": "step",
                        "id": run_id,
                        "tool": name,
                        "phase": "end",
                        "state": step_state,
                        "title": title,
                        "args": _input_detail(name, data.get("input")) if data.get("input") else "",
                        "detail": summary,
                        "preview": preview,
                        "ok": ok if not confirms else None,
                    }
                    if batch_idx is not None:
                        end_ev["batch_index"] = batch_idx
                    yield end_ev
                    emitted_any = False
                    for confirm in confirms:
                        aid = str(confirm.get("action_id") or "")
                        if not aid or aid in emitted_confirm_ids:
                            continue
                        emitted_confirm_ids.add(aid)
                        emitted_any = True
                        pv = confirm.get("preview") if isinstance(confirm.get("preview"), dict) else {}
                        yield {
                            "type": "confirm",
                            "action_id": aid,
                            "tool": confirm.get("tool") or name,
                            "thread_id": confirm.get("thread_id") or thread_id,
                            "expires_at": confirm.get("expires_at"),
                            "summary": confirm.get("summary") or summary,
                            "preview": pv,
                            "message": confirm.get("message") or "请确认是否写入平台",
                        }
                    if emitted_any:
                        yield {"type": "status", "text": "等待你确认写入…", "phase": "waiting"}
                    elif name in _IDE_BATCH_TOOLS:
                        parsed_batch = parsed if isinstance(parsed, dict) else {}
                        if not ok:
                            suppress_ide_report_tokens = False
                            ide_await_report_header = False
                            fail_msg = (
                                str(
                                    parsed_batch.get("message")
                                    or parsed_batch.get("error")
                                    or "取码失败"
                                ).strip()
                                or "取码失败"
                            )
                            yield {
                                "type": "status",
                                "text": f"审核取码失败：{fail_msg[:180]}",
                                "phase": "waiting",
                            }
                        elif name in (
                            "request_ide_list_source_files",
                            "request_git_list_source_files",
                        ):
                            total = parsed_batch.get("total")
                            bc = parsed_batch.get("batch_count")
                            trunc = "（已达上限）" if parsed_batch.get("truncated") else ""
                            kind_label = (
                                "公开 Git 仓"
                                if name == "request_git_list_source_files"
                                else "本机工程"
                            )
                            yield {
                                "type": "status",
                                "text": (
                                    f"已筛选{kind_label}功能源码 {total} 个，"
                                    f"分 {bc} 批审核{trunc}…"
                                ),
                                "phase": "waiting",
                            }
                            suppress_ide_report_tokens = True
                        elif name in (
                            "request_ide_read_batch",
                            "request_git_read_batch",
                        ):
                            bi = parsed_batch.get("batch_index")
                            bc = parsed_batch.get("batch_count")
                            done = bool(parsed_batch.get("done_after"))
                            if bi is not None and bc:
                                yield {
                                    "type": "status",
                                    "text": f"正在审核功能代码：第 {int(bi) + 1}/{bc} 批…",
                                    "phase": "waiting",
                                }
                            if done:
                                suppress_ide_report_tokens = False
                                ide_await_report_header = True
                                ide_report_buf = ""
                                yield {
                                    "type": "status",
                                    "text": "各批已完成，正在汇总完整审核报告…",
                                    "phase": "generating",
                                }
                            else:
                                suppress_ide_report_tokens = True
                        else:
                            suppress_ide_report_tokens = True
                            if not active_runs:
                                yield {
                                    "type": "status",
                                    "text": "继续分批读取功能代码…",
                                    "phase": "waiting",
                                }
                    elif name == "request_git_review":
                        parsed_git = parsed if isinstance(parsed, dict) else {}
                        n_files = len(
                            parsed_git.get("files") or parsed_git.get("file_contents") or []
                        )
                        mode = parsed_git.get("mode") or "git"
                        if ok:
                            yield {
                                "type": "status",
                                "text": (
                                    f"已拉取公开仓库源码（{mode}，抽样 {n_files} 个文件），"
                                    "正在汇总审核报告…"
                                ),
                                "phase": "generating",
                            }
                            suppress_ide_report_tokens = False
                            ide_await_report_header = True
                            ide_report_buf = ""
                        else:
                            suppress_ide_report_tokens = False
                            ide_await_report_header = False
                    # 工具间隙：提示仍在推进（可能还有下一轮工具），不要过早宣称「生成回答」
                    elif not active_runs:
                        yield {"type": "status", "text": "继续分析与整理…", "phase": "waiting"}
                    await asyncio.sleep(0.02)
                    continue

                if kind == "on_tool_error":
                    saw_tool = True
                    tool_ended = True
                    name = _tool_name(event)
                    data = event.get("data") or {}
                    err = data.get("error") or data.get("message") or "工具执行失败"
                    run_id = str(event.get("run_id") or "")
                    if run_id and run_id in active_runs:
                        active_runs.discard(run_id)
                    else:
                        active_runs.clear()
                    if not run_id:
                        run_id = str(uuid.uuid4())
                    summary, preview = _result_detail(name, err)
                    yield {
                        "type": "step",
                        "id": run_id,
                        "tool": name,
                        "phase": "end",
                        "state": "error",
                        "title": _tool_label(name),
                        "detail": summary or str(err),
                        "preview": preview,
                        "ok": False,
                    }
                    if not active_runs:
                        yield {"type": "status", "text": "继续分析与整理…", "phase": "waiting"}
                    await asyncio.sleep(0.02)
                    continue

                if kind == "on_chat_model_stream":
                    chunk = (event.get("data") or {}).get("chunk")
                    text = _chunk_text(chunk)
                    if not text:
                        continue

                    # 首轮选工具时的模型输出丢弃；工具轮次之间也可能有空/碎片，仅在无活跃工具时收正文
                    if active_runs:
                        continue
                    if saw_tool and not tool_ended:
                        continue
                    # 分批审核过程中的「第 N 批纪要」等旁白不进输出区
                    if suppress_ide_report_tokens:
                        continue
                    # 终稿前丢掉英文过渡句，从「代码审核报告」起再输出
                    if ide_await_report_header:
                        ide_report_buf += text
                        idx = _find_ide_report_start(ide_report_buf)
                        if idx < 0:
                            if len(ide_report_buf) < 2500:
                                continue
                            text = _drop_leading_english_aside(ide_report_buf)
                            ide_report_buf = ""
                            ide_await_report_header = False
                            if not text:
                                continue
                        else:
                            text = ide_report_buf[idx:]
                            ide_report_buf = ""
                            ide_await_report_header = False

                    if not generating_sent:
                        generating_sent = True
                        yield {"type": "status", "text": "正在组织最终回答…", "phase": "generating"}

                    yield {"type": "token", "text": text, "token": text}
                    continue
        except asyncio.CancelledError:
            if cancel_event is not None:
                cancel_event.set()
            raise
        except Exception as e:
            name = type(e).__name__
            msg = str(e) or name
            if "Recursion" in name or "recursion" in msg.lower():
                yield {
                    "type": "token",
                    "text": (
                        "\n\n⚠️ 本轮步骤数已达上限，全仓分批审核中断。"
                        "请回复「继续审核」从下一未完成批次接着审，或缩小工程范围后重试。"
                    ),
                    "token": (
                        "\n\n⚠️ 本轮步骤数已达上限，全仓分批审核中断。"
                        "请回复「继续审核」从下一未完成批次接着审，或缩小工程范围后重试。"
                    ),
                }
            else:
                err_text = f"审核过程异常：{msg[:300]}"
                yield {
                    "type": "error",
                    "text": err_text,
                    "message": err_text,
                    "error": err_text,
                }
            return

        # 流结束兜底：本轮调用了写工具但未成功推送 confirm 时，从 pending 回补全部
        if saw_write_tool and not emitted_confirm_ids:
            try:
                for pending in _confirms_from_pending_store(thread_id):
                    aid = str(pending.get("action_id") or "")
                    if not aid or aid in emitted_confirm_ids:
                        continue
                    emitted_confirm_ids.add(aid)
                    pv = pending.get("preview") if isinstance(pending.get("preview"), dict) else {}
                    yield {
                        "type": "confirm",
                        "action_id": aid,
                        "tool": pending.get("tool") or "import_file_to_platform",
                        "thread_id": pending.get("thread_id") or thread_id,
                        "expires_at": pending.get("expires_at"),
                        "summary": pending.get("summary") or "待确认写入平台",
                        "preview": pv,
                        "message": pending.get("message") or "请确认是否写入平台",
                    }
            except Exception:
                pass
