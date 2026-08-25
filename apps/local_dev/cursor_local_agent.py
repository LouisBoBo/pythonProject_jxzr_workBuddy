"""本机沙箱内跑 Cursor SDK Local Agent（LocalAgentOptions.cwd = 沙箱根）。"""
from __future__ import annotations

import re
import sys
import time
from pathlib import Path
from typing import Any, Callable

Sink = Callable[[dict[str, Any]], None]

_USAGE_LIMIT_RE = re.compile(
    r"out of usage|usage limit|increase your limit|you're out of usage",
    re.I,
)


def _emit(sink: Sink | None, event: dict[str, Any]) -> None:
    if sink:
        try:
            sink(event)
        except Exception:
            pass


def _local_agent_options(cwd: str):
    """本机 Agent：cwd=沙箱 + Cursor 进程级 sandbox，不加载用户 Cursor 全局设置。"""
    from cursor_sdk import LocalAgentOptions, LocalAgentStoreConfig, SandboxOptions  # type: ignore

    store_root = str(Path(cwd) / ".cursor-sdk-store")
    Path(store_root).mkdir(parents=True, exist_ok=True)
    kwargs: dict[str, Any] = {
        "cwd": cwd,
        "setting_sources": [],
        "sandbox_options": SandboxOptions(enabled=True),
        "store": LocalAgentStoreConfig(type="sqlite", root_dir=store_root),
    }
    try:
        return LocalAgentOptions(**kwargs)
    except TypeError:
        kwargs.pop("store", None)
        try:
            return LocalAgentOptions(**kwargs)
        except TypeError:
            return LocalAgentOptions(cwd=cwd, sandbox_options=SandboxOptions(enabled=True))


def _is_usage_limit_message(text: str) -> bool:
    return bool(_USAGE_LIMIT_RE.search(str(text or "")))


def _sdk_message_fields(message: Any) -> tuple[str, str, str]:
    """从 SDK 流式消息提取 (type, status, message)。"""
    mtype = str(
        getattr(message, "type", None)
        or (message.get("type") if isinstance(message, dict) else None)
        or ""
    )
    status = str(
        getattr(message, "status", None)
        or (message.get("status") if isinstance(message, dict) else None)
        or ""
    )
    msg = str(
        getattr(message, "message", None)
        or (message.get("message") if isinstance(message, dict) else None)
        or ""
    ).strip()
    return mtype, status, msg


def _format_cursor_run_error(
    run_id: str,
    detail: str,
    *,
    model: str = "",
) -> str:
    text = " ".join(str(detail or "").split())
    head = f"Cursor Local Run 失败（run={run_id or '?'}）"
    if not text:
        return (
            f"{head}：未返回详细原因。"
            "常见：Cursor 账号 composer 额度用尽（可改 auto 模型或联系管理员提额）；"
            "或本机 Cursor CLI/网络异常。"
        )
    body = text if len(text) <= 480 else text[:477].rstrip() + "…"
    if _is_usage_limit_message(text):
        hint = (
            "（composer 额度用尽：已在代码里自动尝试 auto 模型；"
            "仍失败请到 Cursor 控制台提额，或临时设 LOCAL_DEV_AGENT=llm + "
            "LOCAL_DEV_ALLOW_LLM_FALLBACK=1）"
        )
        return f"{head}：{body}{hint}"
    return f"{head}：{body}"


def cursor_local_availability() -> tuple[bool, str, str]:
    """返回 (ok, reason, model)。不要求 CURSOR_DEV_ENABLED（那是 GitHub Cloud 开关）。"""
    apps = Path(__file__).resolve().parents[1]
    if str(apps) not in sys.path:
        sys.path.insert(0, str(apps))
    try:
        from cursor_dev.config import get_config, reload_config

        try:
            reload_config()
        except Exception:
            pass
        cfg = get_config()
    except Exception as exc:  # noqa: BLE001
        return False, f"无法读取 Cursor 配置：{exc}", ""
    if not cfg.api_key:
        return False, "未配置 CURSOR_API_KEY（本机 Cursor 写码需要）", ""
    if not cfg.sdk_ok:
        return False, cfg.sdk_reason or "cursor-sdk 不可用", ""
    model = (cfg.model or "composer-2.5").strip() or "composer-2.5"
    return True, "", model


def build_cursor_local_prompt(
    *,
    requirement: str,
    workspace_hint: str,
    empty_target: bool,
    write_scope: list[str] | None = None,
) -> str:
    from .stack_chain import DATA_STACK_CHAIN_RULES, looks_like_data_ui_change

    mode = (
        "空目录新项目：请从零生成可运行的最小实现"
        if empty_target
        else "已有工程（工作区即沙箱拷贝）：请在现有结构上增量修改"
    )
    req = (requirement or "").strip()
    extra = ""
    if looks_like_data_ui_change(req):
        extra = f"\n\n{DATA_STACK_CHAIN_RULES}\n"
    scope_block = ""
    scope = [str(x).strip() for x in (write_scope or []) if str(x).strip()]
    if scope:
        listed = "\n".join(f"- `{p}`" for p in scope[:80])
        more = f"\n- …共 {len(scope)} 项" if len(scope) > 80 else ""
        scope_block = (
            "\n【用户选定的写范围 · 优先只改下列路径；目录表示其下均可改】\n"
            f"{listed}{more}\n"
            "若必须改范围外文件，请在说明里写清原因；系统同步时会再请用户确认。\n"
        )
    return (
        "你正在 ZR WorkBuddy 的本机写码沙箱中执行改码任务。\n"
        f"【工作区】当前 cwd 就是沙箱根目录，请直接读写此目录内文件。\n"
        f"【目标模式】{mode}\n"
        f"【用户确认的本机同步目录（勿当作 cwd；任务成功后由系统同步）】{workspace_hint}\n"
        f"{scope_block}\n"
        "规则：\n"
        "1. **只改本工作区（cwd）内文件**。禁止 `cd`/`..` 到父目录或绝对路径；禁止读写宿主机家目录、"
        "`.ssh`、`.env`、密钥、证书、其它工程。需要执行命令时也必须留在 cwd 内。\n"
        "2. 最小必要改动；列表/表单新字段须走完整链路（模型→接口→库表/补列→写入→旧数据回填）。\n"
        "3. 前端相对 import 按真实目录深度书写，避免 Vite 红屏。\n"
        "4. 结束后用简短中文说明改了哪些文件与如何验收；不要声称已改宿主机其它目录。\n\n"
        f"【需求】\n{req}\n"
        f"{extra}"
    )


def _run_cursor_local_once(
    *,
    sandbox: Path,
    prompt: str,
    sink: Sink | None,
    step: Callable[..., None],
    is_cancel_requested: Callable[[], bool],
    deadline: float,
    timeout_sec: int,
    model: str,
    api_key: str,
    cwd: str,
    Agent: Any,
    CursorAgentError: Any,
    _assistant_text_from_message: Callable[..., str],
    _finalize_assistant_summary: Callable[..., str],
    _merge_assistant_delta: Callable[..., tuple],
    announce_start: bool = True,
) -> dict[str, Any]:
    """单模型跑一轮 Local Agent。"""
    mdl = (model or "composer-2.5").strip()
    if announce_start:
        step("Cursor 本机 Agent 启动…", sid="cursor-local", state="running")
    _emit(
        sink,
        {
            "type": "status",
            "text": f"本机路径 + Cursor SDK（cwd=沙箱，model={mdl}）",
            "phase": "agent",
            "channel": "cursor_local",
        },
    )

    final_text = ""
    agent_id = ""
    run_id = ""
    run_obj: Any = None
    run_failure_detail = ""

    def _abort() -> str | None:
        if is_cancel_requested():
            try:
                if run_obj is not None and hasattr(run_obj, "cancel"):
                    if not hasattr(run_obj, "supports") or run_obj.supports("cancel"):
                        run_obj.cancel()
            except Exception:
                pass
            return "用户已取消写码任务"
        if time.time() > deadline:
            try:
                if run_obj is not None and hasattr(run_obj, "cancel"):
                    if not hasattr(run_obj, "supports") or run_obj.supports("cancel"):
                        run_obj.cancel()
            except Exception:
                pass
            return f"写码任务超时（>{timeout_sec}s），已中止"
        return None

    try:
        with Agent.create(
            model=mdl,
            api_key=api_key,
            local=_local_agent_options(cwd),
        ) as agent:
            agent_id = str(getattr(agent, "agent_id", None) or getattr(agent, "agentId", "") or "")
            if agent_id:
                _emit(
                    sink,
                    {
                        "type": "status",
                        "text": f"Cursor Local Agent：{agent_id}",
                        "phase": "agent",
                    },
                )

            abort = _abort()
            if abort:
                return {
                    "ok": False,
                    "text": "",
                    "agent_id": agent_id,
                    "run_id": "",
                    "error": abort,
                    "usage_limit": False,
                }

            run_obj = agent.send(prompt)
            run_id = str(getattr(run_obj, "id", None) or getattr(run_obj, "run_id", "") or "")
            if run_id:
                _emit(sink, {"type": "status", "text": f"Cursor Run：{run_id}", "phase": "agent"})

            stream_fn = getattr(run_obj, "stream", None) or getattr(run_obj, "messages", None)
            try:
                if callable(stream_fn):
                    for message in stream_fn():
                        abort = _abort()
                        if abort:
                            return {
                                "ok": False,
                                "text": final_text,
                                "agent_id": agent_id,
                                "run_id": run_id,
                                "error": abort,
                                "usage_limit": False,
                            }
                        mtype, st_status, st_msg = _sdk_message_fields(message)
                        if mtype == "status" and st_msg:
                            if st_status.upper() in {"ERROR", "FAILED"}:
                                run_failure_detail = st_msg
                                _emit(
                                    sink,
                                    {
                                        "type": "step",
                                        "id": "cursor-run-error",
                                        "state": "error",
                                        "title": f"Cursor：{st_msg[:200]}",
                                    },
                                )
                        if mtype == "assistant":
                            piece = _assistant_text_from_message(message)
                            if piece:
                                final_text, delta, replaced = _merge_assistant_delta(
                                    final_text, piece
                                )
                                if replaced:
                                    _emit(sink, {"type": "replace_text", "text": final_text})
                                elif delta:
                                    _emit(sink, {"type": "token", "text": delta})
            except Exception as stream_err:  # noqa: BLE001
                _emit(
                    sink,
                    {
                        "type": "step",
                        "id": "cursor-stream-warn",
                        "state": "done",
                        "title": f"Cursor 流式中断，改用结果汇总：{type(stream_err).__name__}",
                    },
                )

            result = run_obj.wait()
            status = str(getattr(result, "status", "") or "")
            result_text = str(
                getattr(result, "result", None) or getattr(result, "text", None) or ""
            )
            if result_text:
                final_text, delta, replaced = _merge_assistant_delta(final_text, result_text)
                if replaced:
                    _emit(sink, {"type": "replace_text", "text": final_text})
                elif delta:
                    _emit(sink, {"type": "token", "text": delta})
            final_text = _finalize_assistant_summary(final_text)

            abort = _abort()
            if abort:
                return {
                    "ok": False,
                    "text": final_text,
                    "agent_id": agent_id,
                    "run_id": run_id,
                    "error": abort,
                    "usage_limit": False,
                }

            if status == "error":
                detail = run_failure_detail or result_text
                usage_limit = _is_usage_limit_message(detail)
                return {
                    "ok": False,
                    "text": final_text,
                    "agent_id": agent_id,
                    "run_id": run_id,
                    "error": _format_cursor_run_error(run_id, detail, model=mdl),
                    "usage_limit": usage_limit,
                }

            step("Cursor 本机 Agent 本轮完成", sid="cursor-local", state="done")
            return {
                "ok": True,
                "text": final_text.strip() or "Cursor 已完成本轮本机写码。",
                "agent_id": agent_id,
                "run_id": run_id,
                "error": "",
                "usage_limit": False,
            }
    except CursorAgentError as err:  # type: ignore[name-defined]
        msg = getattr(err, "message", None) or str(err)
        retryable = getattr(err, "is_retryable", None)
        hint = f"（可重试={retryable}）" if retryable is not None else ""
        usage_limit = _is_usage_limit_message(msg)
        return {
            "ok": False,
            "text": final_text,
            "agent_id": agent_id,
            "run_id": run_id,
            "error": f"Cursor Agent 启动失败：{msg}{hint}",
            "usage_limit": usage_limit,
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "ok": False,
            "text": final_text,
            "agent_id": agent_id,
            "run_id": run_id,
            "error": f"{type(exc).__name__}: {exc}",
            "usage_limit": False,
        }


def run_cursor_local_agent(
    *,
    sandbox: Path,
    prompt: str,
    data_dir: Path,
    job_id: str,
    sink: Sink | None,
    step: Callable[..., None],
    is_cancel_requested: Callable[[], bool],
    timeout_sec: int = 2700,
    model: str | None = None,
    api_key: str | None = None,
) -> dict[str, Any]:
    """在 sandbox cwd 上跑一轮（可再 follow-up）Cursor Local Agent。

    返回 {ok, text, agent_id, run_id, error}。
    composer 额度用尽时自动用 auto 模型重试一轮。
    """
    apps = Path(__file__).resolve().parents[1]
    if str(apps) not in sys.path:
        sys.path.insert(0, str(apps))

    ok, reason, default_model = cursor_local_availability()
    if not ok:
        return {"ok": False, "text": "", "agent_id": "", "run_id": "", "error": reason}

    from cursor_dev.config import get_config
    from cursor_dev.service import (  # type: ignore
        _assistant_text_from_message,
        _finalize_assistant_summary,
        _merge_assistant_delta,
    )

    cfg = get_config()
    key = (api_key or cfg.api_key or "").strip()
    mdl = (model or default_model or cfg.model or "composer-2.5").strip()
    deadline = time.time() + max(60, int(timeout_sec or cfg.job_timeout_sec))

    try:
        from cursor_sdk import Agent, CursorAgentError  # type: ignore
    except ImportError as exc:
        return {
            "ok": False,
            "text": "",
            "agent_id": "",
            "run_id": "",
            "error": f"未安装 cursor-sdk: {exc}",
        }

    cwd = str(Path(sandbox).resolve())
    models = [mdl]
    if mdl.lower() != "auto":
        models.append("auto")

    last: dict[str, Any] = {
        "ok": False,
        "text": "",
        "agent_id": "",
        "run_id": "",
        "error": "Cursor 本机写码未执行",
    }
    for idx, try_model in enumerate(models):
        if idx > 0:
            step("composer 额度不足，改用 auto 模型重试…", sid="cursor-local-retry", state="running")
            _emit(
                sink,
                {
                    "type": "status",
                    "text": "Cursor composer 额度用尽，自动切换 auto 模型重试…",
                    "phase": "agent",
                    "channel": "cursor_local",
                },
            )
        last = _run_cursor_local_once(
            sandbox=sandbox,
            prompt=prompt,
            sink=sink,
            step=step,
            is_cancel_requested=is_cancel_requested,
            deadline=deadline,
            timeout_sec=timeout_sec,
            model=try_model,
            api_key=key,
            cwd=cwd,
            Agent=Agent,
            CursorAgentError=CursorAgentError,
            _assistant_text_from_message=_assistant_text_from_message,
            _finalize_assistant_summary=_finalize_assistant_summary,
            _merge_assistant_delta=_merge_assistant_delta,
            announce_start=idx == 0,
        )
        if last.get("ok"):
            return {
                "ok": True,
                "text": last.get("text") or "",
                "agent_id": last.get("agent_id") or "",
                "run_id": last.get("run_id") or "",
                "error": "",
            }
        if (
            idx == 0
            and try_model.lower() != "auto"
            and bool(last.get("usage_limit"))
        ):
            continue
        break

    return {
        "ok": False,
        "text": str(last.get("text") or ""),
        "agent_id": str(last.get("agent_id") or ""),
        "run_id": str(last.get("run_id") or ""),
        "error": str(last.get("error") or "Cursor 本机写码失败"),
    }


def run_cursor_local_followup(
    *,
    sandbox: Path,
    agent_id: str,
    prompt: str,
    data_dir: Path,
    job_id: str,
    sink: Sink | None,
    step: Callable[..., None],
    is_cancel_requested: Callable[[], bool],
    timeout_sec: int = 900,
    api_key: str | None = None,
    loop_sid: str = "cursor-local-followup",
) -> dict[str, Any]:
    """对已有 Local Agent 发 follow-up（如相对 import 修复）。"""
    apps = Path(__file__).resolve().parents[1]
    if str(apps) not in sys.path:
        sys.path.insert(0, str(apps))

    from cursor_dev.config import get_config
    from cursor_dev.service import (  # type: ignore
        _assistant_text_from_message,
        _finalize_assistant_summary,
        _merge_assistant_delta,
    )

    cfg = get_config()
    key = (api_key or cfg.api_key or "").strip()
    if not key:
        return {"ok": False, "text": "", "error": "未配置 CURSOR_API_KEY"}
    aid = (agent_id or "").strip()
    if not aid:
        # 无 agent_id 则新开一轮
        return run_cursor_local_agent(
            sandbox=sandbox,
            prompt=prompt,
            data_dir=data_dir,
            job_id=job_id,
            sink=sink,
            step=step,
            is_cancel_requested=is_cancel_requested,
            timeout_sec=timeout_sec,
            api_key=key,
        )

    try:
        from cursor_sdk import Agent, AgentOptions, CursorAgentError  # type: ignore
    except ImportError as exc:
        return {"ok": False, "text": "", "error": f"未安装 cursor-sdk: {exc}"}

    deadline = time.time() + max(60, int(timeout_sec))
    final_text = ""
    run_obj: Any = None
    step("Cursor 跟进修复…", sid=loop_sid, state="running")
    cwd = str(Path(sandbox).resolve())

    def _abort() -> str | None:
        if is_cancel_requested():
            try:
                if run_obj is not None and hasattr(run_obj, "cancel"):
                    if not hasattr(run_obj, "supports") or run_obj.supports("cancel"):
                        run_obj.cancel()
            except Exception:
                pass
            return "用户已取消写码任务"
        if time.time() > deadline:
            return "跟进修复超时"
        return None

    try:
        # resume 时显式带上 local cwd + sandbox，避免跟进轮丢失隔离选项
        local_opts = _local_agent_options(cwd)
        try:
            resume_opts = AgentOptions(api_key=key, local=local_opts)
        except TypeError:
            resume_opts = AgentOptions(api_key=key)
        with Agent.resume(aid, resume_opts) as agent:
            abort = _abort()
            if abort:
                return {"ok": False, "text": "", "error": abort}
            run_obj = agent.send(prompt)
            stream_fn = getattr(run_obj, "stream", None) or getattr(run_obj, "messages", None)
            try:
                if callable(stream_fn):
                    for message in stream_fn():
                        abort = _abort()
                        if abort:
                            return {"ok": False, "text": final_text, "error": abort}
                        mtype = getattr(message, "type", None) or (
                            message.get("type") if isinstance(message, dict) else None
                        )
                        if mtype == "assistant":
                            piece = _assistant_text_from_message(message)
                            if piece:
                                final_text, delta, replaced = _merge_assistant_delta(final_text, piece)
                                if replaced:
                                    _emit(sink, {"type": "replace_text", "text": final_text})
                                elif delta:
                                    _emit(sink, {"type": "token", "text": delta})
            except Exception:
                pass
            result = run_obj.wait()
            status = str(getattr(result, "status", "") or "")
            result_text = str(getattr(result, "result", None) or getattr(result, "text", None) or "")
            if result_text:
                final_text, _, _ = _merge_assistant_delta(final_text, result_text)
            final_text = _finalize_assistant_summary(final_text)
            if status == "error":
                return {"ok": False, "text": final_text, "error": "Cursor 跟进修复失败"}
            step("Cursor 跟进修复完成", sid=loop_sid, state="done")
            return {"ok": True, "text": final_text, "error": ""}
    except CursorAgentError as err:  # type: ignore[name-defined]
        msg = getattr(err, "message", None) or str(err)
        return {"ok": False, "text": final_text, "error": f"Cursor resume 失败：{msg}"}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "text": final_text, "error": f"{type(exc).__name__}: {exc}"}
