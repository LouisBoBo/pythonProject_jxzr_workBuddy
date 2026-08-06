"""Cursor Cloud 执行层。仅 Cloud；失败不抛到进程外拖垮 API。"""
from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any

from .allowlist import normalize_repo
from .audit import append_audit
from .config import CursorDevConfig, reload_config
from . import jobs as job_store

EventSink = Callable[[dict[str, Any]], None]

_PR_URL_RE = re.compile(
    r"https?://(?:github\.com|gitlab\.com)/[^\s)\]\"']+/pull/\d+",
    re.IGNORECASE,
)


def _emit(sink: EventSink | None, event: dict[str, Any]) -> None:
    if sink:
        try:
            sink(event)
        except Exception:
            pass


def _extract_pr_url(text: str) -> str | None:
    m = _PR_URL_RE.search(text or "")
    return m.group(0) if m else None


def _friendly_cursor_error(msg: str, *, github_ok: bool = False, repo: str = "") -> str:
    """把 Cursor/GitHub 校验失败翻成可操作中文提示。"""
    text = (msg or "").strip()
    low = text.lower()
    if "resource_exhausted" in low or "rate limit" in low or "quota" in low:
        return (
            f"{text}\n\n"
            "账号用量/并发已耗尽或触发限流。请打开 https://cursor.com/dashboard/usage 查看用量，"
            "等待配额恢复或减少并发后再试；并在 https://cursor.com/agents 停掉卡住的 Cloud 任务。"
        )
    if (
        "failed to verify existence of branch" in low
        or "failed to verify existence of commit" in low
        or "failed to determine repository default branch" in low
    ):
        if github_ok:
            return (
                f"{text}\n\n"
                f"GitHub 上仓库 {repo or ''} 已能读到分支/commit，但 Cursor Cloud 仍校验失败。"
                "这通常是 Cursor↔GitHub 授权绑定问题（不是空仓）：\n"
                "1. 打开 https://cursor.com/dashboard/integrations → GitHub → Manage → Reconnect；\n"
                "2. 确认 CURSOR_API_KEY 属于「已连接 GitHub」的同一 Cursor 账号"
                "（Team Service Account Key 常常看不到个人授权的仓）；\n"
                "3. 打开 https://github.com/settings/installations 确认 Cursor App 能访问该仓；\n"
                "4. 等待 1～2 分钟后再试（新建仓后 Cursor 索引可能延迟）。"
            )
        return (
            f"{text}\n\n"
            "常见原因：\n"
            "1. 仓库还是空的（无 commit）→ 先在 GitHub 创建 README 并提交；\n"
            "2. Cursor 未授权该仓：https://cursor.com/dashboard/integrations ；\n"
            "3. 起始分支名写错；\n"
            "4. 偶发校验抖动：隔一会重试。"
        )
    return text


def _is_ref_validation_error(msg: str) -> bool:
    low = (msg or "").lower()
    return (
        "failed to determine repository default branch" in low
        or "failed to verify existence of branch" in low
        or "failed to verify existence of commit" in low
    )


def _assistant_text_from_message(message: Any) -> str:
    chunks: list[str] = []
    try:
        content = getattr(getattr(message, "message", None), "content", None)
        if content is None and isinstance(message, dict):
            content = (message.get("message") or {}).get("content")
        if not content:
            return ""
        for block in content:
            btype = getattr(block, "type", None) or (block.get("type") if isinstance(block, dict) else None)
            if btype == "text":
                text = getattr(block, "text", None) or (block.get("text") if isinstance(block, dict) else "")
                if text:
                    chunks.append(str(text))
    except Exception:
        return ""
    return "".join(chunks)


def _merge_assistant_delta(prev: str, incoming: str) -> tuple[str, str]:
    """合并助手文本，返回 (全文, 本次应推送的增量)。

    Cursor 可能推送纯增量，也可能每次推送累计全文；wait() 结果常与已流式内容相同。
    """
    if not incoming:
        return prev, ""
    if not prev:
        return incoming, incoming
    if incoming == prev:
        return prev, ""
    if incoming.startswith(prev):
        return incoming, incoming[len(prev) :]
    if prev.startswith(incoming):
        return prev, ""
    return prev + incoming, incoming


def run_job(
    data_dir,
    job: dict[str, Any],
    *,
    sink: EventSink | None = None,
    cfg: CursorDevConfig | None = None,
) -> dict[str, Any]:
    """同步执行一个 queued/running job。返回更新后的 job 快照。"""
    cfg = cfg or reload_config()
    job_id = job["id"]
    repo = normalize_repo(job.get("repo") or "")
    if not repo:
        raise ValueError("job.repo 无效")

    ok, reason = cfg.availability()
    if not ok:
        raise RuntimeError(reason or "写码车道不可用")

    preferred_ref = (job.get("ref") or cfg.starting_ref or "").strip() or None
    prompt = (job.get("system_prompt") or "").strip()
    if not prompt:
        msgs = job.get("messages") or []
        last_user = next((m.get("content") for m in reversed(msgs) if m.get("role") == "user"), "")
        prior_as = next((m.get("content") for m in reversed(msgs) if m.get("role") == "assistant"), "")
        if prior_as and last_user:
            from .prompts import build_followup_prompt
            from .user_branch import user_work_branch

            work = (preferred_ref or "").strip() or user_work_branch(
                branch_prefix=cfg.branch_prefix,
                username=job.get("username"),
                user_id=job.get("user_id"),
                fixed_branch=cfg.work_branch,
            )
            prompt = build_followup_prompt(
                user_message=last_user,
                repo=repo,
                work_branch=work,
                prior_assistant=str(prior_as),
                create_pr=bool(job.get("create_pr")),
            )
        else:
            prompt = last_user or "请根据会话需求修改仓库代码"

    import time as _time

    job_store.update_job(data_dir, job_id, status="running", error=None, cancel_requested=False)
    deadline = _time.time() + int(cfg.job_timeout_sec)

    from .github_preflight import resolve_starting_ref
    from .project_inspect import continuity_from_jobs
    from .user_branch import user_work_branch

    work_branch = (preferred_ref or "").strip() or user_work_branch(
        branch_prefix=cfg.branch_prefix,
        username=job.get("username"),
        user_id=job.get("user_id"),
        fixed_branch=cfg.work_branch,
    )
    continuity = continuity_from_jobs(
        data_dir,
        repo,
        username=job.get("username"),
        user_id=job.get("user_id"),
        preferred_work_branch=work_branch,
    )
    legacy = str(continuity.get("legacy_branch") or "").strip()

    # Cloud 起始 tip：优先用户固定分支；不存在则用历史功能分支（带上登录代码）；再退默认分支
    pre = resolve_starting_ref(repo, work_branch)
    github_ok = bool(pre.get("ok"))
    ref = work_branch
    tip_sha = None
    cloud_starting = work_branch

    if github_ok and pre.get("ref") == work_branch:
        tip_sha = pre.get("sha")
        cloud_starting = work_branch
    elif legacy:
        pre_legacy = resolve_starting_ref(repo, legacy)
        if pre_legacy.get("ok"):
            github_ok = True
            tip_sha = pre_legacy.get("sha")
            cloud_starting = legacy
            if pre_legacy.get("error"):
                _emit(sink, {"type": "status", "text": str(pre_legacy.get("error")), "phase": "preflight"})
        elif pre.get("soft") or pre_legacy.get("soft"):
            github_ok = False
            cloud_starting = legacy or work_branch
        else:
            # 回退默认
            pre_def = resolve_starting_ref(repo, cfg.starting_ref or None)
            if pre_def.get("ok"):
                github_ok = True
                tip_sha = pre_def.get("sha")
                cloud_starting = str(pre_def.get("ref") or work_branch)
            elif pre.get("soft") or pre_def.get("soft"):
                github_ok = False
                cloud_starting = work_branch
            else:
                err = pre.get("error") or pre_def.get("error") or "GitHub 预检失败"
                job_store.update_job(data_dir, job_id, status="failed", error=err)
                append_audit(
                    data_dir,
                    {"event": "job_failed", "job_id": job_id, "repo": repo, "error": err, "phase": "preflight"},
                )
                _emit(sink, {"type": "error", "message": err})
                return job_store.get_job(data_dir, job_id) or job
    elif not github_ok:
        err = pre.get("error") or "GitHub 预检失败"
        if pre.get("soft"):
            cloud_starting = work_branch
            _emit(
                sink,
                {
                    "type": "status",
                    "text": f"GitHub 预检暂不可用（将继续写码）：{err}",
                    "phase": "preflight",
                },
            )
            append_audit(
                data_dir,
                {
                    "event": "preflight_soft_fail",
                    "job_id": job_id,
                    "repo": repo,
                    "error": err,
                    "ref": work_branch,
                },
            )
        else:
            # 可能是工作分支尚不存在 → 已回退默认分支
            if pre.get("ref") and pre.get("ref") != work_branch:
                github_ok = True
                tip_sha = pre.get("sha")
                cloud_starting = str(pre.get("ref"))
            else:
                job_store.update_job(data_dir, job_id, status="failed", error=err)
                append_audit(
                    data_dir,
                    {"event": "job_failed", "job_id": job_id, "repo": repo, "error": err, "phase": "preflight"},
                )
                _emit(sink, {"type": "error", "message": err})
                return job_store.get_job(data_dir, job_id) or job
    else:
        # ok 但 ref 被回退成默认分支
        tip_sha = pre.get("sha")
        cloud_starting = str(pre.get("ref") or work_branch)
        if pre.get("error"):
            _emit(sink, {"type": "status", "text": str(pre.get("error")), "phase": "preflight"})

    job_store.update_job(data_dir, job_id, status="running", error=None, ref=work_branch)
    _emit(
        sink,
        {
            "type": "status",
            "text": (
                f"正在连接 Cursor Cloud：{repo} · 工作分支 {work_branch}"
                + (f"（起始 tip：{cloud_starting}）" if cloud_starting != work_branch else "")
            ),
            "phase": "start",
        },
    )
    if tip_sha:
        _emit(
            sink,
            {
                "type": "status",
                "text": f"GitHub 预检通过：{cloud_starting} @ {str(tip_sha)[:7]}",
                "phase": "preflight",
            },
        )
    _emit(
        sink,
        {
            "type": "step",
            "id": "cursor-boot",
            "state": "running",
            "title": f"Cursor Cloud 写码：{repo}@{work_branch}",
        },
    )

    try:
        from cursor_sdk import (  # type: ignore
            Agent,
            CloudAgentOptions,
            CloudRepository,
            CursorAgentError,
        )
    except ImportError as exc:
        raise RuntimeError("未安装 cursor-sdk") from exc

    url = f"https://github.com/{repo}"
    auto_pr = bool(job.get("create_pr")) and bool(cfg.auto_pr)

    def _check_abort(run_obj: Any = None) -> str | None:
        if job_store.is_cancel_requested(data_dir, job_id):
            try:
                if run_obj is not None and hasattr(run_obj, "cancel"):
                    run_obj.cancel()
            except Exception:
                pass
            return "用户已取消写码任务"
        if _time.time() > deadline:
            try:
                if run_obj is not None and hasattr(run_obj, "cancel"):
                    run_obj.cancel()
            except Exception:
                pass
            return f"写码任务超时（>{cfg.job_timeout_sec}s），已中止"
        return None

    def _make_cloud(starting: str | None):
        repos = [CloudRepository(url=url, **({"starting_ref": starting} if starting else {}))]
        kwargs: dict[str, Any] = {"repos": repos, "auto_create_pr": auto_pr}
        try:
            return CloudAgentOptions(**kwargs, skip_reviewer_request=bool(cfg.skip_reviewer_request))
        except TypeError:
            return CloudAgentOptions(**kwargs)

    agent_id = None
    run_id = None
    final_text = ""
    pr_url = None

    # create 常成功、send 才校验失败：整轮「重建 Agent + send」重试
    # 优先：有代码的起始 tip（可能是历史功能分支）→ 用户固定分支 → tip sha → 默认
    ref_candidates: list[str | None] = []
    for cand in (cloud_starting, work_branch, tip_sha, None):
        if cand not in ref_candidates:
            ref_candidates.append(cand)

    last_err: Exception | None = None
    max_rounds = 5

    try:
        for round_i in range(1, max_rounds + 1):
            starting = ref_candidates[(round_i - 1) % len(ref_candidates)]
            cloud = _make_cloud(starting)
            agent_cm = None
            try:
                _emit(
                    sink,
                    {
                        "type": "status",
                        "text": f"启动 Cursor（第 {round_i}/{max_rounds} 轮，ref={starting or 'default'}）…",
                        "phase": "retry" if round_i > 1 else "agent",
                    },
                )
                agent_cm = Agent.create(model=cfg.model, api_key=cfg.api_key, cloud=cloud)
                agent = agent_cm.__enter__()
                agent_id = getattr(agent, "agent_id", None) or getattr(agent, "agentId", None)
                job_store.update_job(data_dir, job_id, agent_id=agent_id)
                _emit(sink, {"type": "status", "text": f"Agent 已创建：{agent_id or '-'}", "phase": "agent"})

                run = agent.send(prompt)
                run_id = getattr(run, "id", None)
                job_store.update_job(data_dir, job_id, run_id=run_id)
                _emit(
                    sink,
                    {
                        "type": "step",
                        "id": "cursor-run",
                        "state": "running",
                        "title": "Cursor 正在改代码…",
                    },
                )

                stream_fn = getattr(run, "stream", None) or getattr(run, "messages", None)
                try:
                    for message in (stream_fn() if callable(stream_fn) else []):
                        abort = _check_abort(run)
                        if abort:
                            job_store.update_job(
                                data_dir,
                                job_id,
                                status="cancelled",
                                error=abort,
                                agent_id=agent_id,
                                run_id=run_id,
                            )
                            append_audit(
                                data_dir,
                                {
                                    "event": "job_cancelled",
                                    "job_id": job_id,
                                    "repo": repo,
                                    "error": abort,
                                },
                            )
                            _emit(sink, {"type": "error", "message": abort})
                            return job_store.get_job(data_dir, job_id) or job
                        mtype = getattr(message, "type", None) or (
                            message.get("type") if isinstance(message, dict) else None
                        )
                        if mtype == "assistant":
                            piece = _assistant_text_from_message(message)
                            if piece:
                                final_text, delta = _merge_assistant_delta(final_text, piece)
                                if delta:
                                    _emit(sink, {"type": "token", "text": delta})
                        elif mtype in {"tool_call", "tool", "status"}:
                            _emit(
                                sink,
                                {
                                    "type": "step",
                                    "id": f"cursor-{mtype}-{run_id or 'x'}",
                                    "state": "running",
                                    "title": f"Cursor：{mtype}",
                                },
                            )
                except Exception as stream_err:  # noqa: BLE001
                    # 流式失败时仍可走 wait() 兜底；勿静默吞掉便于排查「无流式」
                    _emit(
                        sink,
                        {
                            "type": "step",
                            "id": "cursor-stream-warn",
                            "state": "running",
                            "title": f"Cursor 流式中断，改用结果汇总：{type(stream_err).__name__}",
                        },
                    )

                abort = _check_abort(run)
                if abort:
                    job_store.update_job(
                        data_dir,
                        job_id,
                        status="cancelled",
                        error=abort,
                        agent_id=agent_id,
                        run_id=run_id,
                    )
                    append_audit(
                        data_dir,
                        {"event": "job_cancelled", "job_id": job_id, "repo": repo, "error": abort},
                    )
                    _emit(sink, {"type": "error", "message": abort})
                    return job_store.get_job(data_dir, job_id) or job

                result = run.wait()
                status = str(getattr(result, "status", "") or "")
                result_text = getattr(result, "result", None) or getattr(result, "text", None)
                if result_text:
                    # 已流式推送过则只补增量，禁止把 wait() 全文再发一遍（UI 重复）
                    final_text, delta = _merge_assistant_delta(final_text, str(result_text))
                    if delta:
                        _emit(sink, {"type": "token", "text": delta})

                pr_url = _extract_pr_url(final_text)
                if pr_url:
                    _emit(sink, {"type": "pr", "url": pr_url})

                if status.lower() in {"error", "failed"}:
                    err = f"Cursor run 失败：status={status}"
                    job_store.update_job(
                        data_dir,
                        job_id,
                        status="failed",
                        error=err,
                        agent_id=agent_id,
                        run_id=run_id or getattr(result, "id", None),
                    )
                    append_audit(
                        data_dir,
                        {
                            "event": "job_failed",
                            "job_id": job_id,
                            "repo": repo,
                            "agent_id": agent_id,
                            "run_id": run_id,
                            "error": err,
                        },
                    )
                    _emit(sink, {"type": "error", "message": err})
                    return job_store.get_job(data_dir, job_id) or job

                last_err = None
                break  # success path

            except CursorAgentError as err:  # type: ignore[name-defined]
                last_err = err
                msg = getattr(err, "message", None) or str(err)
                retryable = _is_ref_validation_error(msg) or "resource_exhausted" in msg.lower() or bool(
                    getattr(err, "is_retryable", False)
                )
                if agent_cm is not None:
                    try:
                        agent_cm.__exit__(None, None, None)
                    except Exception:
                        pass
                    agent_cm = None
                if not retryable or round_i >= max_rounds:
                    raise
                _emit(
                    sink,
                    {
                        "type": "status",
                        "text": f"Cursor 校验/限流失败，准备重建 Agent 重试（{round_i}/{max_rounds}）…",
                        "phase": "retry",
                    },
                )
                _time.sleep(min(8.0, 1.5 * round_i))
                continue
            finally:
                if agent_cm is not None:
                    try:
                        agent_cm.__exit__(None, None, None)
                    except Exception:
                        pass

        if last_err is not None:
            raise last_err

    except CursorAgentError as err:  # type: ignore[name-defined]
        msg = _friendly_cursor_error(
            getattr(err, "message", None) or str(err),
            github_ok=github_ok,
            repo=repo,
        )
        job_store.update_job(data_dir, job_id, status="failed", error=msg, agent_id=agent_id, run_id=run_id)
        append_audit(
            data_dir,
            {
                "event": "job_failed",
                "job_id": job_id,
                "repo": repo,
                "agent_id": agent_id,
                "error": msg,
                "retryable": getattr(err, "is_retryable", None),
                "github_ok": github_ok,
                "resolved_ref": ref,
            },
        )
        _emit(sink, {"type": "error", "message": f"Cursor 启动失败：{msg}"})
        return job_store.get_job(data_dir, job_id) or job
    except Exception as exc:  # noqa: BLE001
        msg = _friendly_cursor_error(f"{type(exc).__name__}: {exc}", github_ok=github_ok, repo=repo)
        job_store.update_job(data_dir, job_id, status="failed", error=msg, agent_id=agent_id, run_id=run_id)
        append_audit(
            data_dir,
            {"event": "job_failed", "job_id": job_id, "repo": repo, "agent_id": agent_id, "error": msg},
        )
        _emit(sink, {"type": "error", "message": f"写码执行失败：{msg}"})
        return job_store.get_job(data_dir, job_id) or job

    summary = final_text.strip() or "Cursor 已完成本轮执行。"
    if pr_url:
        summary = f"{summary}\n\nPR：{pr_url}"

    updated = job_store.update_job(
        data_dir,
        job_id,
        status="idle_for_followup",
        agent_id=agent_id,
        run_id=run_id,
        pr_url=pr_url,
        error=None,
    )
    job_store.append_message(data_dir, job_id, role="assistant", content=summary[:8000])
    append_audit(
        data_dir,
        {
            "event": "job_run_finished",
            "job_id": job_id,
            "repo": repo,
            "agent_id": agent_id,
            "run_id": run_id,
            "pr_url": pr_url,
            "status": "idle_for_followup",
        },
    )
    review_hint = (
        "本轮写码已完成。建议在对话中发起代码审核（或 IDE/Git 审核）后再合入主分支；"
        "可继续补充需求做续聊改码。"
    )
    _emit(sink, {"type": "step", "id": "cursor-run", "state": "done", "title": "Cursor 本轮完成"})
    _emit(
        sink,
        {
            "type": "review_hint",
            "text": review_hint,
            "gate": "gate-90",
        },
    )
    _emit(
        sink,
        {
            "type": "done",
            "job_id": job_id,
            "agent_id": agent_id,
            "run_id": run_id,
            "pr_url": pr_url,
            "text": summary,
            "status": "idle_for_followup",
            "suggest_code_review": True,
            "review_hint": review_hint,
        },
    )
    return updated or job_store.get_job(data_dir, job_id) or job
