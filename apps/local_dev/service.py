"""本机写码执行：沙箱 +（默认）Cursor SDK Local Agent → 闸门 → 同步目标目录。"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any, Callable

from . import jobs as job_store
from .config import LocalDevConfig, get_config
from .cursor_local_agent import (
    build_cursor_local_prompt,
    cursor_local_availability,
    run_cursor_local_agent,
    run_cursor_local_followup,
)
from .dev_runtime import ensure_dev_preview
from .fs_snapshot import diff_snapshots, snapshot_sandbox
from .import_check import find_broken_relative_imports, format_repair_prompt
from .prompts import SYSTEM_PROMPT, TOOL_SPECS, build_user_prompt, parse_plan_steps_from_text
from .sandbox import prepare_sandbox, sync_changed_to_target
from .stack_chain import looks_like_data_ui_change
from .stack_chain_gate import format_gate_summary, run_stack_chain_gate
from .tools_fs import SandboxFS
from .workspace import validate_workspace

Sink = Callable[[dict[str, Any]], None]


def _emit(sink: Sink | None, event: dict[str, Any]) -> None:
    if sink:
        try:
            sink(event)
        except Exception:
            pass


class _PlanTracker:
    def __init__(self, sink: Sink | None) -> None:
        self.sink = sink
        self.steps: list[dict[str, Any]] = []

    def set_steps(self, titles: list[str]) -> dict[str, Any]:
        cleaned: list[str] = []
        for t in titles or []:
            s = str(t or "").strip()
            if not s:
                continue
            s = re.sub(r"^第\s*[一二三四五六七八九十百零〇\d]+\s*步\s*[：:．.]?\s*", "", s)
            if s and s not in cleaned:
                cleaned.append(s[:80])
            if len(cleaned) >= 12:
                break
        if len(cleaned) < 1:
            return {"ok": False, "error": "steps 不能为空"}
        self.steps = [
            {"id": str(i), "title": title, "state": "pending"} for i, title in enumerate(cleaned)
        ]
        _emit(self.sink, {"type": "plan", "steps": list(self.steps)})
        return {"ok": True, "count": len(self.steps), "steps": [s["title"] for s in self.steps]}

    def update(self, index: int, state: str) -> dict[str, Any]:
        if not self.steps:
            return {"ok": False, "error": "请先调用 set_plan"}
        try:
            idx = int(index)
        except (TypeError, ValueError):
            return {"ok": False, "error": "index 无效"}
        if idx < 0 or idx >= len(self.steps):
            return {"ok": False, "error": f"index 越界（0..{len(self.steps) - 1}）"}
        st = str(state or "").strip().lower()
        if st not in {"running", "done", "error", "pending"}:
            return {"ok": False, "error": "state 须为 running/done/error"}
        # 同一时刻只保留一个 running
        if st == "running":
            for s in self.steps:
                if s["state"] == "running":
                    s["state"] = "done"
        self.steps[idx]["state"] = st
        _emit(
            self.sink,
            {
                "type": "plan_progress",
                "id": self.steps[idx]["id"],
                "index": idx,
                "state": st,
                "title": self.steps[idx]["title"],
                "steps": list(self.steps),
            },
        )
        return {"ok": True, "index": idx, "state": st, "title": self.steps[idx]["title"]}

    def mark_all_done(self) -> None:
        if not self.steps:
            return
        for s in self.steps:
            if s["state"] != "done":
                s["state"] = "done"
        _emit(self.sink, {"type": "plan", "steps": list(self.steps)})


def _load_llm_client():
    """复用 agent Config 的 OpenAI 兼容客户端。"""
    agent_root = Path(__file__).resolve().parents[1] / "agent"
    if str(agent_root) not in sys.path:
        sys.path.insert(0, str(agent_root))
    from config import Config  # type: ignore

    try:
        Config.reload_runtime()
    except Exception:
        pass
    api_key = (Config.LLM_API_KEY or "").strip()
    if not api_key:
        raise RuntimeError("未配置对话模型 API Key（系统配置 LLM_API_KEY）")
    from openai import OpenAI

    kwargs: dict[str, Any] = {"api_key": api_key}
    base = (Config.LLM_BASE_URL or "").strip().rstrip("/")
    if base:
        kwargs["base_url"] = base
    client = OpenAI(**kwargs)
    model = (Config.MODEL_NAME or "deepseek-chat").strip()
    return client, model


def _dispatch_tool(
    fs: SandboxFS,
    plan: _PlanTracker,
    name: str,
    args: dict[str, Any],
) -> dict[str, Any]:
    if name == "set_plan":
        raw = args.get("steps") or []
        if isinstance(raw, str):
            raw = [x.strip() for x in raw.replace("\n", ",").split(",") if x.strip()]
        if not isinstance(raw, list):
            return {"ok": False, "error": "steps 须为字符串数组"}
        return plan.set_steps([str(x) for x in raw])
    if name == "update_plan_step":
        return plan.update(args.get("index", -1), str(args.get("state") or ""))
    if name == "list_dir":
        return fs.list_dir(str(args.get("path") or "."))
    if name == "read_file":
        return fs.read_file(str(args.get("path") or ""))
    if name == "write_file":
        return fs.write_file(str(args.get("path") or ""), str(args.get("content") or ""))
    if name == "mkdir":
        return fs.mkdir(str(args.get("path") or ""))
    return {"ok": False, "error": f"未知工具：{name}"}


def _truncate_tool_json(text: str, max_chars: int) -> str:
    if max_chars <= 0 or len(text) <= max_chars:
        return text
    keep = max(500, max_chars - 24)
    return text[:keep] + "\n…(工具结果已截断，完整内容在沙箱文件)"


def _compact_tool_messages(
    messages: list[dict[str, Any]],
    *,
    keep_rounds: int,
    max_tool_chars: int,
) -> None:
    """就地压缩旧轮 tool 输出，保留最近 keep_rounds 轮完整结果。"""
    if keep_rounds <= 0 or max_tool_chars <= 0:
        return
    tool_idxs = [i for i, m in enumerate(messages) if m.get("role") == "tool"]
    if len(tool_idxs) <= keep_rounds:
        return
    for idx in tool_idxs[: len(tool_idxs) - keep_rounds]:
        content = messages[idx].get("content")
        if not isinstance(content, str):
            continue
        compact = _truncate_tool_json(content, max(800, max_tool_chars // 2))
        if compact != content:
            messages[idx]["content"] = compact


def _run_llm_tool_loop(
    *,
    client: Any,
    model: str,
    messages: list[dict[str, Any]],
    fs: SandboxFS,
    plan: _PlanTracker,
    sink: Sink | None,
    data_dir: Path,
    job_id: str,
    max_steps: int,
    step: Callable[..., None],
    stream_tokens: bool,
    loop_sid: str,
    tool_result_max_chars: int = 12000,
    tool_history_keep_rounds: int = 4,
) -> str:
    """跑若干轮 tool-calling；返回最后一轮助手正文。"""
    assistant_text = ""
    last_emitted_norm = ""
    for _ in range(max(1, int(max_steps))):
        if job_store.is_cancel_requested(data_dir, job_id):
            raise RuntimeError("任务已取消")

        _compact_tool_messages(
            messages,
            keep_rounds=tool_history_keep_rounds,
            max_tool_chars=tool_result_max_chars,
        )

        resp = client.chat.completions.create(
            model=model,
            messages=messages,
            tools=TOOL_SPECS,
            tool_choice="auto",
            temperature=0.2,
        )
        choice = resp.choices[0]
        msg = choice.message
        tool_calls = list(msg.tool_calls or [])
        content = (msg.content or "").strip()
        if content:
            assistant_text = content
            if not plan.steps:
                parsed = parse_plan_steps_from_text(content)
                if len(parsed) >= 2:
                    plan.set_steps(parsed)
                    content = re.sub(
                        r"(?m)^\s*第\s*[一二三四五六七八九十百零〇\d]+\s*步.*$",
                        "",
                        content,
                    ).strip()
                    content = re.sub(r"\n{3,}", "\n\n", content)
            should_stream = stream_tokens and bool(content) and not tool_calls
            if should_stream:
                norm = re.sub(r"\s+", "", content)
                if norm and norm != last_emitted_norm and not (
                    last_emitted_norm and (norm in last_emitted_norm or last_emitted_norm in norm)
                ):
                    _emit(
                        sink,
                        {
                            "type": "token",
                            "text": content if not last_emitted_norm else ("\n" + content),
                        },
                    )
                    last_emitted_norm = norm

        assistant_msg: dict[str, Any] = {"role": "assistant", "content": msg.content or ""}
        if tool_calls:
            assistant_msg["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments or "{}",
                    },
                }
                for tc in tool_calls
            ]
        messages.append(assistant_msg)

        if not tool_calls:
            step("模型已结束工具调用", sid=loop_sid, state="done")
            break

        for tc in tool_calls:
            name = tc.function.name
            try:
                args = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {}
            if not isinstance(args, dict):
                args = {}
            result = _dispatch_tool(fs, plan, name, args)
            if name in {"set_plan", "update_plan_step"}:
                title = (
                    f"计划已更新（{result.get('count')} 步）"
                    if name == "set_plan" and result.get("ok")
                    else (
                        f"步骤 {int(args.get('index', -1)) + 1} → {args.get('state')}"
                        if name == "update_plan_step"
                        else f"{name} 失败"
                    )
                )
                step(title, sid=f"tool-{tc.id}", state="done")
            else:
                title = f"{name}({args.get('path') or '.'})"
                if result.get("ok"):
                    step(title, sid=f"tool-{tc.id}", state="done")
                else:
                    step(f"{title} 失败：{result.get('error')}", sid=f"tool-{tc.id}", state="done")
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": _truncate_tool_json(
                        json.dumps(result, ensure_ascii=False),
                        tool_result_max_chars,
                    ),
                }
            )
    else:
        step("达到最大步数，停止", sid=loop_sid, state="done")
    return assistant_text


def run_job(
    data_dir: Path,
    job: dict[str, Any],
    *,
    sink: Sink | None = None,
    cfg: LocalDevConfig | None = None,
) -> dict[str, Any]:
    cfg = cfg or get_config()
    job_id = str(job.get("id") or "")
    if not job_id:
        raise ValueError("job id missing")

    if not cfg.enabled:
        err = "本机写码未开启（LOCAL_DEV_ENABLED）"
        job_store.update_job(data_dir, job_id, status="failed", error=err)
        _emit(sink, {"type": "error", "message": err})
        return job_store.get_job(data_dir, job_id) or job

    use_cursor = (cfg.agent or "cursor_sdk") == "cursor_sdk"
    runtime_label = "cursor_local" if use_cursor else "local_sandbox"
    job_store.update_job(data_dir, job_id, status="running", error=None, runtime=runtime_label)
    start_text = (
        "本机路径 + Cursor SDK 写码开始"
        if use_cursor
        else "本机沙箱写码开始（LLM 工具环）"
    )
    _emit(sink, {"type": "status", "text": start_text, "phase": "start", "channel": runtime_label})

    workspace = str(job.get("workspace") or "").strip()
    check = validate_workspace(workspace)
    if not check.get("ok"):
        err = check.get("error") or "目标目录无效"
        job_store.update_job(data_dir, job_id, status="failed", error=err)
        _emit(sink, {"type": "error", "message": err})
        return job_store.get_job(data_dir, job_id) or job

    target = Path(check["path"])
    # 以运行时目录状态为准，避免创建任务时 empty 快照过期
    empty_target = bool(check.get("empty"))
    job_store.update_job(data_dir, job_id, empty_target=empty_target)

    def step(title: str, *, sid: str, state: str = "running") -> None:
        _emit(sink, {"type": "step", "id": sid, "state": state, "title": title})

    try:
        if job_store.is_cancel_requested(data_dir, job_id):
            raise RuntimeError("任务已取消")

        if use_cursor:
            ok_c, reason_c, _model_c = cursor_local_availability()
            if not ok_c:
                raise RuntimeError(
                    reason_c
                    or "本机 Cursor 写码不可用：请配置 CURSOR_API_KEY 并确认 cursor-sdk 已安装"
                )

        step("准备沙箱", sid="sandbox-prep")
        meta = prepare_sandbox(
            data_dir,
            job_id,
            target,
            empty_target=empty_target,
            cfg=cfg,
            on_progress=lambda t: step(t, sid="sandbox-prep"),
        )
        sandbox_path = Path(meta["sandbox"])
        job_store.update_job(data_dir, job_id, sandbox_path=str(sandbox_path))
        step("沙箱就绪", sid="sandbox-prep", state="done")

        requirement = ""
        for m in reversed(job.get("messages") or []):
            if m.get("role") == "user":
                requirement = str(m.get("content") or "")
                break
        if not requirement.strip():
            raise RuntimeError("需求为空")

        fs = SandboxFS(sandbox_path, cfg=cfg)
        plan = _PlanTracker(sink)
        assistant_text = ""
        cursor_agent_id = ""

        if use_cursor:
            before = snapshot_sandbox(sandbox_path)
            prompt = build_cursor_local_prompt(
                requirement=requirement,
                workspace_hint=str(target),
                empty_target=empty_target,
            )
            step("Cursor 在沙箱内改码…", sid="agent-loop")
            cre = run_cursor_local_agent(
                sandbox=sandbox_path,
                prompt=prompt,
                data_dir=data_dir,
                job_id=job_id,
                sink=sink,
                step=step,
                is_cancel_requested=lambda: job_store.is_cancel_requested(data_dir, job_id),
                timeout_sec=cfg.cursor_timeout_sec,
            )
            if not cre.get("ok"):
                raise RuntimeError(cre.get("error") or "Cursor 本机写码失败")
            assistant_text = str(cre.get("text") or "")
            cursor_agent_id = str(cre.get("agent_id") or "")
            if cursor_agent_id:
                job_store.update_job(data_dir, job_id, agent_id=cursor_agent_id)

            # 相对 import 闸门：破损则 Cursor follow-up 再修
            for repair_i in range(2):
                after_mid = snapshot_sandbox(sandbox_path)
                changed_mid = diff_snapshots(before, after_mid)
                issues = find_broken_relative_imports(sandbox_path, changed_mid)
                if not issues:
                    if repair_i == 0:
                        step("相对 import 校验通过", sid="import-gate", state="done")
                    else:
                        step("相对 import 已修复", sid="import-gate", state="done")
                    break
                step(
                    f"相对 import 闸门：{len(issues)} 处无法解析，强制修复（第 {repair_i + 1} 轮）…",
                    sid="import-gate",
                )
                repaired = run_cursor_local_followup(
                    sandbox=sandbox_path,
                    agent_id=cursor_agent_id,
                    prompt=format_repair_prompt(issues),
                    data_dir=data_dir,
                    job_id=job_id,
                    sink=sink,
                    step=step,
                    is_cancel_requested=lambda: job_store.is_cancel_requested(data_dir, job_id),
                    timeout_sec=min(900, cfg.cursor_timeout_sec),
                    loop_sid=f"import-repair-{repair_i + 1}",
                )
                if repaired.get("ok") and repaired.get("text"):
                    assistant_text = str(repaired.get("text") or assistant_text)
                elif not repaired.get("ok"):
                    step(
                        f"相对 import 修复未成功：{str(repaired.get('error') or '')[:120]}",
                        sid="import-gate",
                        state="done",
                    )
                    # 不再空转；下方统一 leftover 检查后中止同步
                    break
            after_mid = snapshot_sandbox(sandbox_path)
            leftover = find_broken_relative_imports(
                sandbox_path, diff_snapshots(before, after_mid)
            )
            if leftover:
                detail = "; ".join(
                    f"{x['file']} ← {x['import']}" for x in leftover[:8]
                )
                raise RuntimeError(
                    "相对 import 校验未通过，已中止同步（避免 Vite 红屏）：" + detail
                )

            plan.mark_all_done()
            changed = diff_snapshots(before, snapshot_sandbox(sandbox_path))
            job_store.update_job(data_dir, job_id, changed_files=changed)
        else:
            client, model = _load_llm_client()
            messages: list[dict[str, Any]] = [
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": build_user_prompt(
                        requirement=requirement,
                        workspace_hint=str(target),
                        empty_target=empty_target,
                    ),
                },
            ]

            step("模型在沙箱内改码…", sid="agent-loop")
            assistant_text = _run_llm_tool_loop(
                client=client,
                model=model,
                messages=messages,
                fs=fs,
                plan=plan,
                sink=sink,
                data_dir=data_dir,
                job_id=job_id,
                max_steps=cfg.max_agent_steps,
                step=step,
                stream_tokens=True,
                loop_sid="agent-loop",
                tool_result_max_chars=cfg.tool_result_max_chars,
                tool_history_keep_rounds=cfg.tool_history_keep_rounds,
            )

            # 相对 import 闸门：破损则强制再修，避免同步后 Vite 红屏
            for repair_i in range(2):
                issues = find_broken_relative_imports(sandbox_path, fs.changed_files())
                if not issues:
                    if repair_i == 0:
                        step("相对 import 校验通过", sid="import-gate", state="done")
                    else:
                        step("相对 import 已修复", sid="import-gate", state="done")
                    break
                step(
                    f"相对 import 闸门：{len(issues)} 处无法解析，强制修复（第 {repair_i + 1} 轮）…",
                    sid="import-gate",
                )
                messages.append({"role": "user", "content": format_repair_prompt(issues)})
                repaired = _run_llm_tool_loop(
                    client=client,
                    model=model,
                    messages=messages,
                    fs=fs,
                    plan=plan,
                    sink=sink,
                    data_dir=data_dir,
                    job_id=job_id,
                    max_steps=min(10, cfg.max_agent_steps),
                    step=step,
                    stream_tokens=False,
                    loop_sid=f"import-repair-{repair_i + 1}",
                    tool_result_max_chars=cfg.tool_result_max_chars,
                    tool_history_keep_rounds=cfg.tool_history_keep_rounds,
                )
                if repaired:
                    assistant_text = repaired
            else:
                leftover = find_broken_relative_imports(sandbox_path, fs.changed_files())
                if leftover:
                    detail = "; ".join(
                        f"{x['file']} ← {x['import']}" for x in leftover[:8]
                    )
                    raise RuntimeError(
                        "相对 import 校验未通过，已中止同步（避免 Vite 红屏）：" + detail
                    )

            plan.mark_all_done()
            changed = fs.changed_files()
            job_store.update_job(data_dir, job_id, changed_files=changed)

        if not changed:
            summary = assistant_text or "模型未写入任何文件。"
            err = "沙箱内无文件变更，未同步到目标目录"
            job_store.append_message(data_dir, job_id, role="assistant", content=summary)
            job_store.update_job(data_dir, job_id, status="failed", error=err)
            _emit(sink, {"type": "error", "message": err})
            return job_store.get_job(data_dir, job_id) or job

        if len(changed) > cfg.max_changed_files:
            raise RuntimeError(f"变更文件过多（{len(changed)}），已中止同步")

        if job_store.is_cancel_requested(data_dir, job_id):
            raise RuntimeError("任务已取消")

        step(f"同步 {len(changed)} 个文件到目标目录…", sid="sync")
        synced = sync_changed_to_target(sandbox_path, target, changed, cfg=cfg)
        step(f"已同步 {len(synced)} 个文件", sid="sync", state="done")

        gate_result: dict[str, Any] = {"skipped": True, "actions": []}
        if looks_like_data_ui_change(requirement):
            step("数据链路闸门：补列并回填空值…", sid="stack-gate")
            try:
                gate_result = run_stack_chain_gate(target, requirement=requirement)
                n_act = len(gate_result.get("actions") or [])
                if n_act:
                    step(f"数据链路闸门已处理 {n_act} 项", sid="stack-gate", state="done")
                else:
                    step("数据链路闸门已检查，无需回填", sid="stack-gate", state="done")
            except Exception as gate_exc:  # noqa: BLE001
                err_name = type(gate_exc).__name__
                gate_result = {"skipped": False, "actions": [], "error": err_name}
                step(f"数据链路闸门未完全执行（{err_name}）", sid="stack-gate", state="done")

        if job_store.is_cancel_requested(data_dir, job_id):
            raise RuntimeError("任务已取消")

        preview: dict[str, Any] = {}
        preview_url = ""
        try:
            step("确保开发服务 / 预览…", sid="preview")
            preview = ensure_dev_preview(
                target,
                synced,
                cfg=cfg,
                on_progress=lambda t: step(t, sid="preview"),
                should_cancel=lambda: job_store.is_cancel_requested(data_dir, job_id),
            )
            preview_url = str(preview.get("preview_url") or "").strip()
            if preview.get("ok") and preview_url:
                step(f"预览就绪：{preview_url}", sid="preview", state="done")
            else:
                step(
                    f"预览未完全就绪：{preview.get('notes') or '未知原因'}",
                    sid="preview",
                    state="done",
                )
        except Exception as preview_exc:  # noqa: BLE001
            preview = {
                "ok": False,
                "preview_url": "",
                "backend_url": "",
                "notes": f"{type(preview_exc).__name__}: {preview_exc}",
                "frontend": {"action": "skipped", "error": str(preview_exc)},
                "backend": {"action": "skipped", "error": str(preview_exc)},
            }
            step(f"预览步骤异常（同步已成功）：{preview_exc}", sid="preview", state="done")

        if job_store.is_cancel_requested(data_dir, job_id):
            raise RuntimeError("任务已取消")

        files_md = "\n".join(f"- `{p}`" for p in synced[:80])
        if preview_url:
            preview_md = (
                f"可打开预览验收：[{preview_url}]({preview_url})\n\n"
                f"{preview.get('notes') or ''}\n"
            )
        else:
            preview_md = (
                f"同步已完成，预览未自动就绪："
                f"{preview.get('notes') or '请手动启动该工程前后端'}\n"
            )
        gate_md = format_gate_summary(gate_result)
        gate_block = f"{gate_md}\n\n" if gate_md else ""
        accept_block = ""
        if looks_like_data_ui_change(requirement):
            try:
                # 本机写码进程可能不在 agent 包路径下，按需加入
                import sys
                from pathlib import Path as _P

                _agent = _P(__file__).resolve().parents[1] / "agent"
                if str(_agent) not in sys.path:
                    sys.path.insert(0, str(_agent))
                from tools.query_tool.dev_preflight import mes_change_preflight

                pf = mes_change_preflight(requirement)
                md = str(pf.get("acceptance_markdown") or "").strip()
                if md:
                    accept_block = f"{md}\n\n"
            except Exception:  # noqa: BLE001
                accept_block = (
                    "### 改后数据侧验收\n\n"
                    "- 在对话里查相关列表，确认无 401、条数合理\n"
                    "- 加字段：核对新列展示与历史回填\n\n"
                )
        summary = (
            f"## 已完成本机写码\n\n"
            f"已写入目标目录：`{target}`\n\n"
            f"变更文件（{len(synced)}）：\n{files_md}\n\n"
            f"{preview_md}\n"
            f"{gate_block}"
            f"{accept_block}"
            f"沙箱 id：`{job_id}`\n\n"
            f"{'本机写码：Cursor SDK Local Agent（不经 GitHub Cloud / 不经 DeepSeek 工具环）。' if use_cursor else '本机写码：LLM 工具环（应急模式 LOCAL_DEV_AGENT=llm）。'}\n"
        )
        if assistant_text:
            summary += f"\n### 模型说明\n{assistant_text}\n"

        job_store.append_message(data_dir, job_id, role="assistant", content=summary)
        updated = job_store.update_job(
            data_dir,
            job_id,
            status="succeeded",
            synced_files=synced,
            preview_url=preview_url or None,
            preview=preview,
            error=None,
        )
        # 取消竞态：落盘可能已完成，但任务状态不得被改成成功
        if not updated or str(updated.get("status") or "") != "succeeded":
            _emit(sink, {"type": "error", "message": "任务已取消"})
            return updated or job_store.get_job(data_dir, job_id) or job
        _emit(sink, {"type": "replace_text", "text": summary})
        _emit(
            sink,
            {
                "type": "done",
                "job_id": job_id,
                "text": summary,
                "status": "succeeded",
                "workspace": str(target),
                "changed_files": synced,
                "sandbox_id": job_id,
                "channel": "local_sandbox",
                "preview_url": preview_url,
                "preview": preview,
            },
        )
        return updated or job_store.get_job(data_dir, job_id) or job

    except Exception as exc:  # noqa: BLE001
        err = f"{type(exc).__name__}: {exc}"
        if "取消" in str(exc):
            job_store.update_job(data_dir, job_id, status="cancelled", error=str(exc))
        else:
            job_store.update_job(data_dir, job_id, status="failed", error=err)
        _emit(sink, {"type": "error", "message": err})
        return job_store.get_job(data_dir, job_id) or job
