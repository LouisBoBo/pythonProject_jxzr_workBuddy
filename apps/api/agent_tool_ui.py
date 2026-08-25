"""Agent 流式过程区：工具中文标题 / 入参摘要 / 结果预览（从 agent_wrapper 抽出）。

不依赖 AgentRunner；Git/IDE workspace 解析仍惰性 import middleware。
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

# FilesystemBackend 常返回 `1|content` 行号前缀
_LINE_PREFIX = re.compile(r"(?m)^\s*\d+\|")

# 工具 → 中文短标题（过程区只显示这些，不 dump 原始内容）
_TOOL_LABELS = {
    "query_platform_data": "查询平台数据",
    "summarize_platform_data": "汇总平台数据分组",
    "analyze_platform_brief": "平台轻量分析简报",
    "render_analysis_chart": "渲染分析图表",
    "render_analysis_dashboard": "渲染分析看板",
    "run_analysis_demo": "打开运营看板",
    "readonly_sql": "只读 SQL 查询",
    "list_query_metrics": "列出指标口径",
    "query_metric": "按指标口径查询",
    "list_ops_scenes": "列出运维场景",
    "run_ops_scene": "执行运维值班场景",
    "list_analysis_demos": "列出运营看板编排",
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
    "compare_schema_vs_catalog": "对照表结构与接口目录",
    "mes_change_preflight": "改功能前置清单",
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
    if name in ("query_platform_data", "summarize_platform_data", "analyze_platform_brief", "query_metric", "run_ops_scene", "render_analysis_chart", "render_analysis_dashboard", "run_analysis_demo", "readonly_sql"):
        if data.get("entity"):
            lines.append(f"实体：{data['entity']}")
        if data.get("name") and name == "query_metric":
            lines.append(f"口径：{data['name']}")
        if data.get("scene") and name == "run_ops_scene":
            lines.append(f"场景：{data['scene']}")
        if data.get("playbook") and name == "run_analysis_demo":
            lines.append(f"演示剧本：{data['playbook']}")
        if data.get("export") is not None and name == "run_ops_scene":
            lines.append(f"导出：{data['export']}")
        if data.get("group_by"):
            lines.append(f"分组：{data['group_by']}")
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

        # 按路径读文件（非分批）：勿落入下方文本正则，否则内容里的 FileNotFound 等会误标「失败」
        if name == "request_ide_read_files" or (
            isinstance(data.get("file_contents"), list) and data.get("status") == "ok"
        ):
            files = [
                str(x.get("path") or "").replace("\\", "/").strip()
                for x in (data.get("file_contents") or [])
                if isinstance(x, dict) and str(x.get("path") or "").strip()
            ]
            if not files:
                files = [
                    str(p).replace("\\", "/").strip()
                    for p in (data.get("files") or [])
                    if str(p).strip()
                ]
            nfiles = len(files) or len(data.get("file_contents") or [])
            summary = f"已读 {nfiles} 个文件"
            if data.get("local_fill"):
                summary += "（本机直读）"
            return summary, files[:8]

        if data.get("chart_option") or data.get("charts") or (
            name
            in (
                "render_analysis_chart",
                "render_analysis_dashboard",
                "run_analysis_demo",
            )
            and data.get("ok")
        ):
            title = str(data.get("title") or data.get("label") or "分析图")
            ctype = str(data.get("chart_type") or "bar")
            pts = data.get("point_count") or data.get("chart_count")
            if data.get("charts") and isinstance(data.get("charts"), list):
                summary = f"看板已生成：{title}（{len(data['charts'])} 图"
                gaps = data.get("gap_count")
                if gaps:
                    summary += f"，{gaps} 缺口"
                summary += "）"
            else:
                summary = f"图表已生成：{title}（{ctype}，{pts} 点）"
            preview = []
            for c in (data.get("caveats") or [])[:3]:
                if str(c).strip():
                    preview.append(f"说明：{c}")
            for g in (data.get("gaps") or [])[:4]:
                if isinstance(g, dict) and g.get("title"):
                    preview.append(f"缺口：{g.get('title')} — {g.get('reason') or ''}")
            cats = data.get("categories") or []
            vals = data.get("values") or []
            for i, cat in enumerate(cats[:6]):
                v = vals[i] if i < len(vals) else ""
                preview.append(f"{cat} = {v}")
            return summary, preview

        if "total" in data or "records" in data or data.get("markdown_table") or data.get("display_rows") or data.get("markdown_report"):
            if data.get("markdown_report") and not data.get("records") and not data.get("display_rows"):
                # 分析简报 / 值班简报：过程区直接露出报告前几行
                report = str(data.get("markdown_report") or "")
                summary = "分析/简报已生成"
                if data.get("label") or data.get("entity"):
                    summary = f"分析简报：「{data.get('label') or ''}」(`{data.get('entity') or ''}`)"
                for line in report.splitlines()[:12]:
                    if line.strip():
                        preview.append(line.strip())
                if report.count("\n") > 12:
                    preview.append("…（完整见助手回复 markdown_report）")
                return summary, preview
            entity = data.get("entity") or ""
            label = str(data.get("label") or data.get("metric_label") or "").strip()
            total = data.get("total")
            returned = data.get("returned")
            records = data.get("records") if isinstance(data.get("records"), list) else []
            display_rows = data.get("display_rows") if isinstance(data.get("display_rows"), list) else []
            if total is None:
                total = len(records) if records else len(display_rows)
            if returned is None:
                returned = len(display_rows) if display_rows else len(records)
            if label and entity:
                summary = f"查询完成：「{label}」(`{entity}`) MES 共 {total} 条，本次 {returned} 条"
            elif entity:
                summary = f"查询完成：`{entity}` MES 共 {total} 条，本次 {returned} 条"
            else:
                summary = f"查询完成：共 {total} 条，本次 {returned} 条"
            if data.get("metric_label"):
                summary = f"口径「{data.get('metric_label')}」· " + summary
            applied = data.get("filters_applied") if isinstance(data.get("filters_applied"), dict) else {}
            if applied:
                bits = [f"{k}={v}" for k, v in list(applied.items())[:6]]
                summary += "；筛选 " + "，".join(bits)
            caveats = data.get("caveats") if isinstance(data.get("caveats"), list) else []
            for c in caveats[:3]:
                s = str(c or "").strip()
                if s:
                    preview.append(f"说明：{s}")
            # 优先中文 display_rows / markdown_table，过程区不再只贴英文 key=value
            if display_rows:
                col_meta = data.get("columns") if isinstance(data.get("columns"), list) else []
                headers = [
                    str(c.get("label") or c.get("name") or "")
                    for c in col_meta
                    if isinstance(c, dict)
                ]
                if headers and all(isinstance(r, dict) for r in display_rows[:1]):
                    preview.append(" | ".join(headers))
                    preview.append(" | ".join("---" for _ in headers))
                    for row in display_rows[:5]:
                        preview.append(
                            " | ".join(str(row.get(h) or "")[:40] for h in headers)
                        )
                else:
                    for row in display_rows[:5]:
                        if isinstance(row, dict):
                            preview.append(
                                " · ".join(f"{k}={v}" for k, v in list(row.items())[:5])
                            )
                        else:
                            preview.append(str(row)[:100])
            else:
                md = str(data.get("markdown_table") or "").strip()
                if md:
                    for line in md.splitlines()[:8]:
                        if line.strip():
                            preview.append(line.strip())
                else:
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
            if int(returned or 0) > 5:
                preview.append(f"… 其余 {int(returned) - 5} 条已省略（完整表见助手回复）")
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

        # 已成功解析为 dict 且非错误态：勿再当纯文本扫 FileNotFound（文件内容易误伤）
        st_ok = str(data.get("status") or "").strip().lower()
        if st_ok in {"", "ok", "success", "done"} and not data.get("error"):
            msg = str(data.get("message") or data.get("raw_summary") or "").strip()
            if msg:
                return msg[:280], []
            keys = [k for k in data.keys() if not str(k).startswith("_")][:6]
            return "完成", [f"字段：{', '.join(keys)}"] if keys else []

    text = _strip_line_numbers(_as_text(out)).strip()
    # 虚拟 FS / 路径错误：不要误标成「已读取技能说明」
    # 仅匹配输出开头的工具错误，避免源码正文里的 FileNotFound 误报
    head = text[:240]
    if re.search(
        r"^(?:失败[:：]|Error:\s*|\[错误\])|path_not_found|Error:\s*Path|文件不存在",
        head,
        re.I,
    ):
        return f"失败：{head[:200]}", []

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


def _tool_name(event: dict) -> str:
    name = event.get("name") or ""
    if name:
        return str(name)
    data = event.get("data") or {}
    return str(data.get("name") or data.get("tool") or "tool")


def _tool_label(name: str, inp: Any = None) -> str:
    base = _TOOL_LABELS.get(name, name)
    hint = _entity_hint(inp)
    if hint and name in (
        "query_platform_data",
        "summarize_platform_data",
        "query_metric",
        "run_ops_scene",
        "import_file_to_platform",
        "export_platform_data",
    ):
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

