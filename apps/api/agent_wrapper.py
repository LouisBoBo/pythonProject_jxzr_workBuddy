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

try:
    _boot = Path(__file__).resolve().parents[1] / "agent"
    if str(_boot) not in sys.path:
        sys.path.insert(0, str(_boot))
    from bundle_root import resolve_repo_root

    REPO_ROOT = resolve_repo_root()
except Exception:  # noqa: BLE001
    REPO_ROOT = Path(__file__).resolve().parents[2]

AGENT_PATH = REPO_ROOT / "apps" / "agent"
APPS_PATH = REPO_ROOT / "apps"
if not AGENT_PATH.is_dir():
    AGENT_PATH = Path(__file__).resolve().parents[1] / "agent"
if str(AGENT_PATH) not in sys.path:
    sys.path.insert(0, str(AGENT_PATH))
if APPS_PATH.is_dir() and str(APPS_PATH) not in sys.path:
    sys.path.insert(0, str(APPS_PATH))

from agents.agent import create_agent, build_model  # noqa: E402
from checkpoint_store import ensure_thread_messages, get_acheckpointer  # noqa: E402
from middleware.request_context import get_thread_id, get_user_id, get_username  # noqa: E402
from workbuddy_lanes import (  # noqa: E402
    LANE_CODE_DEV,
    LANE_CODE_REVIEW,
    LANE_PASTE_CODE,
    drop_leading_english_aside as _drop_leading_english_aside,
    find_ide_report_start as _find_ide_report_start,
    is_cursor_dev_coding_lane as _is_cursor_dev_coding_lane,
    resolve_workbuddy_lane,
    should_attach_shot_images_for_discuss as _should_attach_shot_images_for_discuss,
    user_utterance_for_vision_policy,
)
from stream_concurrency import stream_busy_event, try_acquire_stream_lock  # noqa: E402
from agent_lane_message import (  # noqa: E402
    append_lane_force_routes,
    format_platform_context_prefix,
    platform_context_bits,
)

from agent_tool_ui import (  # noqa: E402
    _IDE_BATCH_TOOLS,
    _as_text,
    _chunk_text,
    _entity_hint,
    _extract_json_object,
    _extract_write_confirm,
    _input_detail,
    _is_tool_failure,
    _parse_jsonish,
    _result_detail,
    _tool_label,
    _tool_name,
    _unwrap_content,
)

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


class AgentRunner:
    """单例 Agent 运行器，避免每次请求重新创建 Deep Agent。"""

    _instance = None
    # 工具集变更时 bump，避免热更新后仍复用旧 Agent（缺 request_git_*_batch）
    _TOOLS_SIG = "git-review-default-v7-no-resuppress-after-done"

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
        若进程内已有一路流式占用锁，短等后仍抢不到则立刻 error（不静默排队）。
        """
        lock = self._get_stream_lock()
        if not await try_acquire_stream_lock(lock):
            yield stream_busy_event()
            return
        try:
            async for event in self._stream_chat_locked(
                message, thread_id, file_paths, cancel_event=cancel_event
            ):
                yield event
        finally:
            lock.release()

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
            prefix = format_platform_context_prefix(
                platform_context_bits(message or "", ctx)
            )
        except Exception:
            prefix = ""

        try:
            from middleware.request_context import get_page_context as _gpc_mes

            _lane_mes = resolve_workbuddy_lane(message or "", _gpc_mes() or {})
            if _lane_mes not in (LANE_CODE_DEV, LANE_CODE_REVIEW, LANE_PASTE_CODE):
                from tools.schema_tool.profile_readiness import format_mes_context_block

                mes_block = (format_mes_context_block() or "").strip()
                if mes_block:
                    prefix = f"{prefix}{mes_block}\n\n" if prefix else f"{mes_block}\n\n"
        except Exception:
            pass

        try:
            from middleware.request_context import get_page_context as _gpc

            _ctx = _gpc() or {}
        except Exception:
            _ctx = {}
        # 写码 / 审核 / 贴码：对等互斥；仅按本轮意图注入强制路由。
        body = append_lane_force_routes(message or "", _ctx)

        if not file_paths:
            return prefix + body

        # 截图 → 视觉模型文字，再交给纯文本主模型
        # 重做/重新设计：跳过旧图视觉规格，避免讨论阶段又锁回五卡骨架
        image_block = ""
        non_image_paths: list[str] = list(file_paths)
        try:
            from tools.vision_describe import build_image_context_block, is_image_path

            image_paths = [p for p in file_paths if is_image_path(p)]
            non_image_paths = [p for p in file_paths if not is_image_path(p)]
            skip_vision = not _should_attach_shot_images_for_discuss(body)
            vision_hint = user_utterance_for_vision_policy(body) or body
            if image_paths and not skip_vision:
                image_block = build_image_context_block(
                    image_paths, user_hint=vision_hint
                )
                if len(image_block) > 6000:
                    image_block = image_block[:5980].rstrip() + "\n…(截图理解已截断)"
            elif image_paths and skip_vision:
                image_block = (
                    "【截图理解】本轮按「重做/重新设计」跳过旧图视觉规格注入"
                    "（避免锁回旧布局）。用户若指出红框/标注改动点，仍以用户原文为准。"
                )
            elif not image_paths and file_paths:
                image_block = (
                    "【截图理解】附件已收到但未识别为图片扩展名，无法调用视觉模型。"
                    f"附件数：{len(file_paths)}"
                )
        except Exception as vis_exc:
            import logging

            logging.getLogger(__name__).warning("vision inject failed: %s", vis_exc)
            # 不把异常原文（可能含 Key/路径）塞给模型
            image_block = (
                "【截图理解】视觉模型调用失败，未能生成画面描述。"
                f"（错误类型：{type(vis_exc).__name__}）"
                "请勿声称「本轮没有收到截图」；应提示用户重试或改用文字说明改动点。"
            )
            non_image_paths = list(file_paths)

        body_with_images = body
        if image_block:
            body_with_images = f"{body}\n\n{image_block}" if body.strip() else image_block

        if not non_image_paths:
            return prefix + body_with_images

        file_note = "\n".join([f"[附件路径]: {p}" for p in non_image_paths])
        log_paths = [
            p
            for p in non_image_paths
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
                f"{prefix}{body_with_images}\n\n"
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
            f"{prefix}{body_with_images}\n\n用户已上传以下文件，请按需读取或导入：\n{file_note}\n"
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

    async def _stream_chat_locked(
        self,
        message: str,
        thread_id: str = "default",
        file_paths: list[str] | None = None,
        *,
        cancel_event: Any = None,
    ) -> AsyncIterator[dict[str, Any]]:
        import asyncio

        has_images = False
        try:
            from tools.vision_describe import is_image_path

            has_images = any(is_image_path(p) for p in (file_paths or []))
        except Exception:
            has_images = False
        if has_images:
            yield {"type": "status", "text": "正在理解截图…"}
            await asyncio.sleep(0)

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
        # 末批 done_after 后置位：禁止后续 request_ide_read_files 再次压制终稿输出
        ide_batches_done = False
        # 本轮模型调用是否已通过 stream 吐出正文（用于 on_chat_model_end 去重兜底）
        model_streamed_chars = 0
        # 一旦向用户放出过审核终稿 token，就不再用「未生成报告」兜底（工具轮次会清 generating_sent）
        ide_report_emitted = False

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

                if kind == "on_chat_model_start":
                    model_streamed_chars = 0
                    continue

                if kind == "on_tool_start":
                    saw_tool = True
                    generating_sent = False  # 新工具轮次，取消生成态（勿清 ide_report_emitted）
                    name = _tool_name(event)
                    if name in ("import_file_to_platform", "import_platform_data"):
                        saw_write_tool = True
                    # 末批完成后勿再压制模型输出（常见误调：补读 pom/yml）
                    if (
                        not ide_batches_done
                        and (name in _IDE_BATCH_TOOLS or name == "request_git_review")
                    ):
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
                    # 分析图表：看板一次推送 / 单图或多图 SSE
                    chart_events: list[dict] = []
                    dashboard_event: dict | None = None
                    if isinstance(parsed, dict):
                        multi = parsed.get("charts")
                        as_board = (
                            name
                            in (
                                "render_analysis_dashboard",
                                "run_analysis_demo",
                            )
                            or bool(parsed.get("template_id"))
                            or bool(parsed.get("demo"))
                            or (
                                isinstance(multi, list)
                                and len(multi) >= 2
                                and parsed.get("ok")
                            )
                        )

                        def _norm_chart_item(ch: dict, idx: int) -> dict | None:
                            opt = ch.get("chart_option") or ch.get("option")
                            if not isinstance(opt, dict):
                                return None
                            layout = (
                                ch.get("layout")
                                if isinstance(ch.get("layout"), dict)
                                else None
                            ) or opt.get("_wb_layout") or {}
                            series = opt.get("series")
                            series_type = ""
                            if isinstance(series, list):
                                for s in series:
                                    if isinstance(s, dict) and s.get("type") in (
                                        "pie",
                                        "bar",
                                        "line",
                                    ):
                                        series_type = str(s["type"])
                                        break
                            return {
                                "id": str(ch.get("id") or f"{run_id}-{idx}"),
                                "title": str(
                                    ch.get("title") or parsed.get("title") or "分析图"
                                ),
                                "chart_type": series_type
                                or str(ch.get("chart_type") or "bar"),
                                "option": opt,
                                "definition": str(ch.get("definition") or "")[:300],
                                "caveats": list(ch.get("caveats") or [])[:5],
                                "layout": layout,
                                "drill": ch.get("drill")
                                if isinstance(ch.get("drill"), dict)
                                else None,
                                "entity": ch.get("entity"),
                            }

                        if isinstance(multi, list) and multi and as_board:
                            board_charts: list[dict] = []
                            for i, ch in enumerate(multi):
                                if not isinstance(ch, dict):
                                    continue
                                item = _norm_chart_item(ch, i)
                                if item:
                                    board_charts.append(item)
                            if board_charts:
                                gaps_raw = parsed.get("gaps")
                                gaps_out: list[dict] = []
                                if isinstance(gaps_raw, list):
                                    for g in gaps_raw[:8]:
                                        if isinstance(g, dict):
                                            gaps_out.append(
                                                {
                                                    "id": g.get("id"),
                                                    "title": g.get("title") or g.get("id"),
                                                    "reason": str(g.get("reason") or "")[
                                                        :300
                                                    ],
                                                }
                                            )
                                dashboard_event = {
                                    "type": "dashboard",
                                    "id": run_id,
                                    "tool": name,
                                    "title": str(
                                        parsed.get("label")
                                        or parsed.get("title")
                                        or "分析看板"
                                    ),
                                    "template_id": str(
                                        parsed.get("template_id") or ""
                                    ),
                                    "presentation": bool(
                                        parsed.get("presentation") or parsed.get("demo")
                                    ),
                                    "skin": str(parsed.get("skin") or "ops_dark"),
                                    "kpis": [
                                        k
                                        for k in (parsed.get("kpis") or [])
                                        if isinstance(k, dict)
                                    ][:6],
                                    "charts": board_charts,
                                    "gaps": gaps_out,
                                }
                        elif isinstance(multi, list) and multi:
                            for i, ch in enumerate(multi):
                                if not isinstance(ch, dict):
                                    continue
                                item = _norm_chart_item(ch, i)
                                if not item:
                                    continue
                                chart_events.append(
                                    {
                                        "type": "chart",
                                        "tool": name,
                                        **item,
                                    }
                                )
                        else:
                            chart_opt = parsed.get("chart_option")
                            chart_title = ""
                            chart_type = ""
                            chart_def = ""
                            chart_caveats: list = []
                            if not chart_opt and isinstance(parsed.get("chart"), dict):
                                chart_opt = parsed["chart"].get("chart_option")
                                chart_title = str(parsed["chart"].get("title") or "")
                                chart_type = str(parsed["chart"].get("chart_type") or "")
                                chart_def = str(parsed["chart"].get("definition") or "")
                                chart_caveats = list(parsed["chart"].get("caveats") or [])
                            if chart_opt and isinstance(chart_opt, dict):
                                item = _norm_chart_item(
                                    {
                                        "title": chart_title
                                        or str(parsed.get("title") or "分析图"),
                                        "chart_type": chart_type
                                        or str(parsed.get("chart_type") or "bar"),
                                        "option": chart_opt,
                                        "definition": chart_def
                                        or str(parsed.get("definition") or ""),
                                        "caveats": chart_caveats
                                        or list(parsed.get("caveats") or [])[:5],
                                        "layout": parsed.get("layout"),
                                    },
                                    0,
                                )
                                if item:
                                    chart_events.append(
                                        {
                                            "type": "chart",
                                            "id": run_id,
                                            "tool": name,
                                            **item,
                                        }
                                    )
                    if dashboard_event:
                        yield dashboard_event
                    for ev in chart_events:
                        yield ev
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
                            # 末批已过后禁止再压制：模型偶发重调 list 会把终稿整段吞掉
                            if not ide_batches_done:
                                suppress_ide_report_tokens = True
                            else:
                                suppress_ide_report_tokens = False
                                ide_await_report_header = True
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
                                ide_batches_done = True
                                suppress_ide_report_tokens = False
                                ide_await_report_header = True
                                ide_report_buf = ""
                                yield {
                                    "type": "status",
                                    "text": "各批已完成，正在汇总完整审核报告…",
                                    "phase": "generating",
                                }
                            elif ide_batches_done:
                                # 末批 done_after 后回补漏批：只允许读码，禁止重新压制终稿输出
                                suppress_ide_report_tokens = False
                                ide_await_report_header = True
                                if not active_runs:
                                    yield {
                                        "type": "status",
                                        "text": "补读完成，正在汇总完整审核报告…",
                                        "phase": "generating",
                                    }
                            else:
                                suppress_ide_report_tokens = True
                        else:
                            # request_ide_read_files 等：末批完成后不得再压制终稿
                            if ide_batches_done:
                                suppress_ide_report_tokens = False
                                if not ide_await_report_header and not ide_report_buf:
                                    ide_await_report_header = True
                                if not active_runs:
                                    yield {
                                        "type": "status",
                                        "text": "各批已完成，正在汇总完整审核报告…",
                                        "phase": "generating",
                                    }
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
                            ide_batches_done = True
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
                            # 缓冲较短时继续等标题；过长则去掉英文旁白后放行，避免整段被吞
                            if len(ide_report_buf) < 1200:
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

                    model_streamed_chars += len(text)
                    if ide_batches_done:
                        ide_report_emitted = True
                    yield {"type": "token", "text": text, "token": text}
                    continue

                # 部分模型/网关不走 token 流，只在 end 给整段 content；stream 为空时兜底放出
                if kind == "on_chat_model_end":
                    if active_runs or suppress_ide_report_tokens:
                        continue
                    if model_streamed_chars > 0:
                        continue
                    if saw_tool and not tool_ended:
                        continue
                    data = event.get("data") or {}
                    text = _chunk_text(data.get("output")) or _chunk_text(
                        (data.get("output") or {}).get("content")
                        if isinstance(data.get("output"), dict)
                        else None
                    )
                    if not text.strip():
                        continue
                    if ide_await_report_header:
                        ide_report_buf += text
                        idx = _find_ide_report_start(ide_report_buf)
                        if idx >= 0:
                            text = ide_report_buf[idx:]
                        else:
                            text = _drop_leading_english_aside(ide_report_buf)
                        ide_report_buf = ""
                        ide_await_report_header = False
                        if not text.strip():
                            continue
                    if not generating_sent:
                        generating_sent = True
                        yield {"type": "status", "text": "正在组织最终回答…", "phase": "generating"}
                    model_streamed_chars += len(text)
                    if ide_batches_done:
                        ide_report_emitted = True
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
                # 通用流异常：勿一律写成「审核过程」，避免查数/写码误导
                lane = ""
                try:
                    from middleware.request_context import get_page_context

                    lane = str((get_page_context() or {}).get("workbuddy_lane") or "")
                except Exception:
                    lane = ""
                if lane == "code_review" or "审核" in (message or ""):
                    err_text = f"审核过程异常：{msg[:300]}"
                elif lane == "code_dev":
                    err_text = f"写码过程异常：{msg[:300]}"
                else:
                    err_text = f"处理异常：{msg[:300]}"
                yield {
                    "type": "error",
                    "text": err_text,
                    "message": err_text,
                    "error": err_text,
                }
            return

        # 流结束兜底：若仍卡在「等报告标题」缓冲里，冲刷出来，避免前端空白
        if ide_report_buf.strip():
            leftover = ide_report_buf
            idx = _find_ide_report_start(leftover)
            if idx >= 0:
                leftover = leftover[idx:]
            else:
                leftover = _drop_leading_english_aside(leftover)
            ide_report_buf = ""
            ide_await_report_header = False
            if leftover.strip():
                if not generating_sent:
                    yield {"type": "status", "text": "正在组织最终回答…", "phase": "generating"}
                if ide_batches_done:
                    ide_report_emitted = True
                yield {"type": "token", "text": leftover, "token": leftover}
        elif ide_batches_done and not ide_report_emitted and not generating_sent:
            # 末批已完成但模型未吐出任何可见正文
            yield {
                "type": "token",
                "text": (
                    "\n\n⚠️ 各批源码已读完，但本轮未生成「🔍 代码审核报告」正文。"
                    "请回复「继续输出审核报告」或点「重新开始审核」。"
                ),
                "token": (
                    "\n\n⚠️ 各批源码已读完，但本轮未生成「🔍 代码审核报告」正文。"
                    "请回复「继续输出审核报告」或点「重新开始审核」。"
                ),
            }

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
