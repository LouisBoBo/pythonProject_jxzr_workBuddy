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

# 工具 → 中文短标题（过程区只显示这些，不 dump 原始内容）
_TOOL_LABELS = {
    "query_platform_data": "查询平台数据",
    "list_platform_entities": "列出可查实体",
    "get_platform_summary": "汇总平台数据",
    "read_file": "查阅技能说明",
    "write_file": "写入文件",
    "edit_file": "编辑文件",
    "ls": "浏览目录",
    "glob": "搜索文件",
    "grep": "检索内容",
    "execute": "执行命令",
    "import_platform_data": "导入平台数据",
    "export_platform_data": "导出平台数据",
}

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
                return s
        return s
    return obj


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
    elif name in ("import_platform_data", "export_platform_data"):
        for k in ("entity", "target_entity", "file_path", "output_format"):
            if data.get(k):
                lines.append(f"{k}：{data[k]}")
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
            return f"失败：{data.get('error')}", []

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
    if name == "read_file" or text.lstrip().startswith("---") or "name:" in text[:200]:
        skill = ""
        desc = ""
        for line in text.splitlines()[:40]:
            if line.startswith("name:"):
                skill = line.split(":", 1)[1].strip().strip("'\"")
            elif line.startswith("description:"):
                desc = line.split(":", 1)[1].strip().strip("'\"")
            # 行号已剥离后的 description 可能跨多行，取首段即可
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
    if isinstance(data, dict) and data.get("error"):
        return True
    if isinstance(data, str):
        s = data.strip()
        if s.startswith("实体守卫") or s.startswith("[错误]"):
            return True
        if len(s) <= 240 and (s.lower().startswith("error") or "失败" in s[:40]):
            return True
    return False


def _tool_name(event: dict) -> str:
    name = event.get("name") or ""
    if name:
        return str(name)
    data = event.get("data") or {}
    return str(data.get("name") or data.get("tool") or "tool")


def _tool_label(name: str, inp: Any = None) -> str:
    base = _TOOL_LABELS.get(name, name)
    hint = _entity_hint(inp)
    if hint and name in ("query_platform_data", "import_platform_data", "export_platform_data"):
        return f"{base} · {hint}"
    if hint and name == "read_file":
        if "SKILL" in hint or "skill" in hint.lower():
            return "查阅技能说明"
        return f"读取 {hint}"
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

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._agent = None
            cls._instance._model = None
        return cls._instance

    @property
    def agent(self):
        if self._agent is None:
            self._model = build_model()
            self._agent = create_agent(model=self._model)
        return self._agent

    def _build_message(self, message: str, file_paths: list[str] | None = None) -> str:
        if not file_paths:
            return message
        file_note = "\n".join([f"[附件路径]: {p}" for p in file_paths])
        return f"{message}\n\n用户已上传以下文件，请按需读取或导入：\n{file_note}"

    def chat(self, message: str, thread_id: str = "default", file_paths: list[str] | None = None) -> str:
        final_message = self._build_message(message, file_paths)
        result = self.agent.invoke(
            {"messages": [{"role": "user", "content": final_message}]},
            config={"configurable": {"thread_id": thread_id}},
        )
        return result["messages"][-1].content

    async def stream_chat(
        self,
        message: str,
        thread_id: str = "default",
        file_paths: list[str] | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        """异步流式事件：status / step / token。"""
        import asyncio

        final_message = self._build_message(message, file_paths)
        yield {"type": "status", "text": "正在分析问题…"}
        await asyncio.sleep(0)

        saw_tool = False
        tool_ended = False
        generating_sent = False
        active_runs: set[str] = set()

        async for event in self.agent.astream_events(
            {"messages": [{"role": "user", "content": final_message}]},
            config={"configurable": {"thread_id": thread_id}},
            version="v2",
        ):
            kind = event.get("event", "")

            if kind == "on_tool_start":
                saw_tool = True
                generating_sent = False  # 新工具轮次，取消生成态
                name = _tool_name(event)
                data = event.get("data") or {}
                inp = data.get("input")
                run_id = str(event.get("run_id") or uuid.uuid4())
                active_runs.add(run_id)
                yield {
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
                await asyncio.sleep(0.02)
                continue

            if kind == "on_tool_end":
                saw_tool = True
                tool_ended = True
                name = _tool_name(event)
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
                yield {
                    "type": "step",
                    "id": run_id,
                    "tool": name,
                    "phase": "end",
                    "state": "done" if ok else "error",
                    "title": title,
                    "args": _input_detail(name, data.get("input")) if data.get("input") else "",
                    "detail": summary,
                    "preview": preview,
                    "ok": ok,
                }
                # 工具间隙：提示仍在推进（可能还有下一轮工具），不要过早宣称「生成回答」
                if not active_runs:
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

                if not generating_sent:
                    generating_sent = True
                    yield {"type": "status", "text": "正在组织最终回答…", "phase": "generating"}

                yield {"type": "token", "text": text, "token": text}
                continue
