"""人触发：汇总本批已同步文件 → 审码门禁（不经写码收尾、不经全仓审）。"""
from __future__ import annotations

import time
from datetime import datetime
from pathlib import Path
from typing import Any

from local_dev import jobs as job_store
from local_dev.commit_gate import run_commit_review_gate
from local_dev.git_commit import (
    commit_synced_files,
    draft_chinese_commit_message,
    filter_pending_commit_files,
    inspect_git_repo,
    resolve_work_branch,
    validate_chinese_commit_message,
)


def _day_start_ts(now: float | None = None) -> int:
    """本地日历日 0 点（服务器本地时区）。"""
    t = datetime.fromtimestamp(now if now is not None else time.time())
    start = t.replace(hour=0, minute=0, second=0, microsecond=0)
    return int(start.timestamp())


def _norm_workspace(path: str) -> str:
    try:
        return str(Path(path).expanduser().resolve())
    except OSError:
        return str(path or "").strip()


def collect_batch_synced_files(
    data_dir: Path,
    *,
    user_id: str,
    workspace: str,
    today_only: bool = True,
    now: float | None = None,
) -> dict[str, Any]:
    """从本用户已成功的本机写码 job 汇总 synced_files（排除 commit_batch 自身）。"""
    ws = _norm_workspace(workspace)
    day0 = _day_start_ts(now) if today_only else 0
    jobs = job_store.list_jobs(data_dir, statuses={"succeeded"}, user_id=str(user_id or ""))
    sources: list[str] = []
    files: list[str] = []
    seen: set[str] = set()
    for job in jobs:
        if str(job.get("runtime") or "") == "commit_batch":
            continue
        jws = _norm_workspace(str(job.get("workspace") or ""))
        if jws != ws:
            continue
        created = int(job.get("created_at") or job.get("updated_at") or 0)
        if today_only and created < day0:
            continue
        synced = [str(p).replace("\\", "/").strip() for p in (job.get("synced_files") or []) if str(p).strip()]
        if not synced:
            continue
        sources.append(str(job.get("id") or ""))
        for rel in synced:
            while rel.startswith("./"):
                rel = rel[2:]
            rel = rel.lstrip("/")
            if not rel or rel in seen or ".." in rel.split("/"):
                continue
            abs_p = Path(ws) / rel
            try:
                if abs_p.is_file():
                    seen.add(rel)
                    files.append(rel)
            except OSError:
                continue
            if len(files) >= 120:
                break
        if len(files) >= 120:
            break

    return {
        "workspace": ws,
        "files": files,
        "source_job_ids": sources[:40],
        "today_only": bool(today_only),
        "day_start": day0 if today_only else None,
    }


def prepare_commit_batch(
    data_dir: Path,
    *,
    user_id: str | int | None,
    workspace: str,
    today_only: bool = True,
) -> dict[str, Any]:
    """仅汇总本批文件（快），供前端先展示进度后再跑门禁。"""
    uid = "" if user_id is None else str(user_id)
    try:
        ws = str(Path(workspace).expanduser().resolve())
    except OSError as exc:
        return {"ok": False, "error": f"工作区路径无效：{exc}"}

    batch = collect_batch_synced_files(
        data_dir, user_id=uid, workspace=ws, today_only=today_only
    )
    files = list(batch.get("files") or [])
    relaxed = False
    if not files and today_only:
        batch = collect_batch_synced_files(
            data_dir, user_id=uid, workspace=ws, today_only=False
        )
        files = list(batch.get("files") or [])
        relaxed = True
        batch["relaxed_from_today"] = True

    if not files:
        return {
            "ok": False,
            "error": "没有可提交的本批文件（请先完成本机写码同步，或确认工作区路径一致）",
            "workspace": ws,
            "files": [],
            "batch": batch,
        }

    filt = filter_pending_commit_files(ws, files)
    pending = list(filt.get("pending_files") or [])
    batch_meta = {
        "source_job_ids": batch.get("source_job_ids") or [],
        "today_only": batch.get("today_only"),
        "relaxed_from_today": relaxed or bool(batch.get("relaxed_from_today")),
        "synced_pool_total": filt.get("synced_total") or len(files),
        "synced_raw_total": filt.get("synced_raw_total") or len(files),
        "excluded_non_business_total": filt.get("excluded_non_business_total") or 0,
        "excluded_non_business": filt.get("excluded_non_business") or [],
        "git_dirty_total": filt.get("git_dirty_total") or 0,
        "scope_note": filt.get("scope_note") or "",
    }
    if not pending:
        return {
            "ok": True,
            "workspace": ws,
            "files": [],
            "file_count": 0,
            "pending": False,
            "message": (
                f"今日 WorkBuddy 同步池共 {batch_meta['synced_pool_total']} 个文件，"
                "相对 git 均无新变更（可能已本地提交）。"
                "若需推送远程，确认后仍可尝试 push。"
            ),
            "batch": batch_meta,
            "synced_pool": filt.get("synced_pool") or files,
            "preview": [],
        }
    return {
        "ok": True,
        "workspace": ws,
        "files": pending,
        "file_count": len(pending),
        "pending": True,
        "batch": batch_meta,
        "synced_pool": filt.get("synced_pool") or files,
        "preview": pending[:12],
    }


def supersede_pending_commit_batches(
    data_dir: Path,
    *,
    user_id: str,
) -> list[str]:
    """将本用户未确认的 commit_batch 标为已跳过，避免「卡死无法再提交」。

    用户再次说「提交今天的代码」时，以最新一批为准；旧确认卡失效。
    不触碰进行中的写码任务（runtime != commit_batch）。
    """
    uid = str(user_id or "")
    if not uid:
        return []
    superseded: list[str] = []
    for old in job_store.list_jobs(data_dir, statuses={"awaiting_commit"}, user_id=uid):
        if str(old.get("runtime") or "") != "commit_batch":
            continue
        jid = str(old.get("id") or "")
        if not jid:
            continue
        gate = old.get("commit_gate") if isinstance(old.get("commit_gate"), dict) else {}
        branch = str(gate.get("work_branch") or "")
        job_store.append_message(
            data_dir,
            jid,
            role="assistant",
            content="## 已跳过提交\n\n已被新一批提交请求取代，请在最新确认卡上操作。\n",
        )
        job_store.update_job(
            data_dir,
            jid,
            status="succeeded",
            commit_decision="skip",
            commit_result={
                "ok": True,
                "skipped": True,
                "superseded": True,
                "error": "",
                "message": "已被新一批提交请求取代",
                "branch": branch,
                "commit": "",
            },
            error=None,
        )
        superseded.append(jid)
    return superseded


def find_recent_push_retry_job(
    data_dir: Path,
    *,
    user_id: str,
    workspace: str,
    max_age_sec: int = 86_400,
) -> dict[str, Any] | None:
    """最近一条「本地已 commit、push 未成功」的 commit_batch（可仅重试 push）。"""
    from local_dev.git_commit import is_push_retry_needed

    ws = _norm_workspace(workspace)
    if not ws:
        return None
    now = int(time.time())
    best: tuple[int, dict[str, Any]] | None = None
    for job in job_store.list_jobs(data_dir, user_id=str(user_id or "")):
        if str(job.get("runtime") or "") != "commit_batch":
            continue
        if _norm_workspace(str(job.get("workspace") or "")) != ws:
            continue
        updated = int(job.get("updated_at") or job.get("created_at") or 0)
        if updated <= 0 or now - updated > max_age_sec:
            continue
        cr = job.get("commit_result")
        if not isinstance(cr, dict) or not is_push_retry_needed(cr):
            continue
        if best is None or updated > best[0]:
            best = (updated, job)
    return best[1] if best else None


def _resume_push_retry_response(job: dict[str, Any]) -> dict[str, Any]:
    """将 awaiting_commit 的 push 重试任务格式化为 start_commit_batch 返回值。"""
    gate = dict(job.get("commit_gate") or {})
    cr = dict(job.get("commit_result") or {})
    push_err = ""
    push = cr.get("push") if isinstance(cr.get("push"), dict) else None
    if push and not push.get("ok"):
        push_err = str(push.get("error") or "")
    files = list(cr.get("files") or job.get("synced_files") or gate.get("synced_files") or [])
    commit_sha = str(cr.get("commit") or "")
    msg = str(cr.get("message") or gate.get("suggested_commit_message") or "")
    gate.update(
        {
            "push_only": True,
            "push_retry": True,
            "retryable": True,
            "can_commit": True,
            "prior_commit": commit_sha,
            "summary": (
                f"本地已提交（commit `{commit_sha[:12]}`），远程推送未完成。"
                + (f" 失败原因：{push_err[:200]}" if push_err else "")
                + " 修复网络后请点「重试推送」（不会重新 commit）。"
            ),
            "verdict": "pass",
            "suggested_commit_message": msg,
            "synced_files": files,
        }
    )
    return {
        "ok": True,
        "resumed": True,
        "job_id": str(job.get("id") or ""),
        "files": files,
        "commit_gate": gate,
        "superseded_job_ids": [],
    }


def ensure_push_retry_confirmable(
    data_dir: Path,
    job_id: str,
    *,
    user_id: str = "",
) -> dict[str, Any] | None:
    """推送失败后的任务重新打开为 awaiting_commit，供 confirm-commit 仅 push。"""
    from local_dev.git_commit import is_push_retry_needed

    job = job_store.get_job(data_dir, job_id)
    if not job or str(job.get("runtime") or "") != "commit_batch":
        return None
    if user_id and str(job.get("user_id") or "") != str(user_id):
        return None
    cr = job.get("commit_result")
    if not isinstance(cr, dict) or not is_push_retry_needed(cr):
        return job
    status = str(job.get("status") or "")
    if status == "awaiting_commit" and job.get("commit_decision") not in {"commit", "skip"}:
        return job
    updated = job_store.update_job(
        data_dir,
        job_id,
        status="awaiting_commit",
        commit_decision=None,
    )
    return updated or job


def start_commit_batch(
    data_dir: Path,
    *,
    user_id: str | int | None,
    username: str | None,
    thread_id: str,
    workspace: str,
    message: str,
    today_only: bool = True,
    allow_blocked: bool = False,
    use_ide_review: bool | None = None,
    use_skill_review: bool | None = None,
    files: list[str] | None = None,
    batch_meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """创建 commit_batch job（status=awaiting_commit），不取消进行中的写码任务。

    若已有待确认的 commit_batch：自动取代（skip），再创建新任务，避免 UI 丢卡后死锁。
    """
    uid = "" if user_id is None else str(user_id)
    ws_check = Path(workspace).expanduser()
    try:
        ws = str(ws_check.resolve())
    except OSError as exc:
        return {"ok": False, "error": f"工作区路径无效：{exc}"}

    batch: dict[str, Any]
    file_list: list[str]
    if files is not None:
        cleaned: list[str] = []
        seen: set[str] = set()
        for p in files:
            rel = str(p).replace("\\", "/").strip()
            while rel.startswith("./"):
                rel = rel[2:]
            rel = rel.lstrip("/")
            if not rel or rel in seen or ".." in rel.split("/"):
                continue
            try:
                if (Path(ws) / rel).is_file():
                    seen.add(rel)
                    cleaned.append(rel)
            except OSError:
                continue
            if len(cleaned) >= 120:
                break
        batch = dict(batch_meta or {})
        batch.setdefault("source_job_ids", [])
        batch.setdefault("today_only", today_only)
        filt = filter_pending_commit_files(ws, cleaned)
        file_list = list(filt.get("pending_files") or [])
        batch.setdefault("synced_pool_total", filt.get("synced_total") or len(cleaned))
        batch.setdefault("synced_raw_total", filt.get("synced_raw_total") or len(cleaned))
        batch.setdefault("excluded_non_business_total", filt.get("excluded_non_business_total") or 0)
        batch.setdefault("excluded_non_business", filt.get("excluded_non_business") or [])
        batch.setdefault("git_dirty_total", filt.get("git_dirty_total") or 0)
        batch.setdefault("scope_note", filt.get("scope_note") or "")
        batch.setdefault("synced_pool", filt.get("synced_pool") or cleaned)
    else:
        prepared = prepare_commit_batch(
            data_dir, user_id=uid, workspace=ws, today_only=today_only
        )
        if not prepared.get("ok"):
            return prepared
        file_list = list(prepared.get("files") or [])
        batch = dict(prepared.get("batch") or {})
        batch.setdefault("synced_pool", prepared.get("synced_pool") or [])

    # 无待提交文件：若已有 push 重试中的确认任务，直接恢复（不重新 commit）
    if not file_list and uid:
        existing = find_recent_push_retry_job(data_dir, user_id=uid, workspace=ws)
        if existing and str(existing.get("status") or "") == "awaiting_commit":
            return _resume_push_retry_response(existing)

    superseded_ids = supersede_pending_commit_batches(data_dir, user_id=uid) if uid else []

    git_info = inspect_git_repo(ws)
    if not git_info.get("is_git"):
        return {
            "ok": False,
            "error": "目标目录不是 git 仓库，无法提交",
            "batch": batch,
        }

    push_only = not file_list
    push_retry_source = (
        find_recent_push_retry_job(data_dir, user_id=uid, workspace=ws) if push_only and uid else None
    )
    from local_dev.config import get_config as _ld_cfg

    _cfg = _ld_cfg()
    do_skill = use_skill_review if use_skill_review is not None else bool(_cfg.commit_use_skill_review)
    do_ide = use_ide_review if use_ide_review is not None else bool(_cfg.commit_use_ide_review)
    gate = run_commit_review_gate(
        ws,
        file_list,
        allow_blocked_override=allow_blocked,
        use_skill_review=bool(do_skill),
        use_ide_review=bool(do_ide),
    )
    work_branch = resolve_work_branch(username=username or "", user_id=uid)
    can_commit = bool(gate.get("can_commit")) and bool(git_info.get("is_git"))
    can_push = bool(can_commit) and bool(git_info.get("has_remote"))
    user_msg = (message or "提交本批代码").strip()
    suggested = draft_chinese_commit_message(user_message=user_msg, files=file_list or batch.get("synced_pool") or [])
    scope_note = str(batch.get("scope_note") or gate.get("scope_label") or "")
    prior_cr = (
        push_retry_source.get("commit_result")
        if push_retry_source and isinstance(push_retry_source.get("commit_result"), dict)
        else {}
    )
    if push_only:
        if prior_cr.get("message"):
            suggested = str(prior_cr.get("message") or suggested)
        gate = {
            **gate,
            "summary": (
                f"本地已提交（commit `{str(prior_cr.get('commit') or '')[:12]}`），无新文件需 commit。"
                if prior_cr.get("commit")
                else f"审码门禁：同步池 {batch.get('synced_pool_total') or 0} 个文件均已提交到 git，"
                "本批无新文件需审；"
            )
            + (
                f" 上次推送失败：{str((prior_cr.get('push') or {}).get('error') or '')[:160]}"
                if prior_cr.get("push") and not (prior_cr.get("push") or {}).get("ok")
                else ""
            )
            + " 确认后可「重试推送」（不会重新 commit）。",
            "verdict": "pass",
            "push_retry": bool(prior_cr.get("commit")),
            "prior_commit": str(prior_cr.get("commit") or ""),
        }
        if prior_cr.get("files"):
            file_list = list(prior_cr.get("files") or file_list)
        can_commit = bool(git_info.get("is_git"))
    commit_gate = {
        **gate,
        "git": git_info,
        "work_branch": work_branch,
        "can_commit": can_commit,
        "can_push": can_push,
        "synced_files": file_list,
        "suggested_commit_message": suggested,
        "push_only": push_only,
        "batch": {
            "source_job_ids": batch.get("source_job_ids") or [],
            "today_only": batch.get("today_only"),
            "relaxed_from_today": bool(batch.get("relaxed_from_today")),
            "synced_pool_total": batch.get("synced_pool_total"),
            "synced_raw_total": batch.get("synced_raw_total"),
            "excluded_non_business_total": batch.get("excluded_non_business_total"),
            "excluded_non_business": batch.get("excluded_non_business") or [],
            "git_dirty_total": batch.get("git_dirty_total"),
            "scope_note": scope_note,
        },
    }

    now = int(time.time())
    job_id = job_store.new_job_id()
    job: dict[str, Any] = {
        "id": job_id,
        "user_id": uid,
        "username": username or "",
        "thread_id": thread_id or "",
        "workspace": ws,
        "empty_target": False,
        "status": "awaiting_commit",
        "messages": [{"role": "user", "content": message or "提交本批代码", "at": now}],
        "sandbox_path": None,
        "changed_files": list(file_list),
        "synced_files": list(file_list),
        "write_scope": [],
        "file_paths": [],
        "deferred_files": [],
        "scope_decision": None,
        "commit_decision": None,
        "commit_gate": commit_gate,
        "commit_result": None,
        "preview_url": None,
        "preview": None,
        "error": None,
        "cancel_requested": False,
        "runtime": "commit_batch",
        "agent_id": None,
        "created_at": now,
        "updated_at": now,
    }
    job_store.write_job_document(data_dir, job)

    return {
        "ok": True,
        "job": job,
        "commit_gate": commit_gate,
        "files": file_list,
        "superseded_job_ids": superseded_ids,
    }


def finalize_commit_batch(
    data_dir: Path,
    job_id: str,
    decision: str,
    *,
    push: bool = False,
    push_url: str | None = None,
    save_remote: bool = False,
    commit_message: str | None = None,
) -> dict[str, Any]:
    """confirm-commit 后对 commit_batch 直执 git（不经 run_job / 模型）。"""
    job = job_store.get_job(data_dir, job_id)
    if not job:
        return {"ok": False, "error": "任务不存在"}
    if str(job.get("runtime") or "") != "commit_batch":
        return {"ok": False, "error": "非 commit_batch 任务"}
    status = str(job.get("status") or "")
    if status != "awaiting_commit":
        return {"ok": False, "error": f"任务状态不可提交：{status or 'unknown'}"}

    gate = job.get("commit_gate") if isinstance(job.get("commit_gate"), dict) else {}
    cr_prev = job.get("commit_result") if isinstance(job.get("commit_result"), dict) else {}
    files = list(job.get("synced_files") or gate.get("synced_files") or cr_prev.get("files") or [])
    ws = str(job.get("workspace") or "")
    branch = str(gate.get("work_branch") or resolve_work_branch(
        username=str(job.get("username") or ""),
        user_id=str(job.get("user_id") or ""),
    ))

    if decision == "skip":
        result = {"ok": True, "skipped": True, "error": "", "branch": branch, "commit": ""}
        summary = "## 已跳过提交\n\n本批文件仍保留在目标目录，未执行 git commit。\n"
        job_store.append_message(data_dir, job_id, role="assistant", content=summary)
        updated = job_store.update_job(
            data_dir,
            job_id,
            status="succeeded",
            commit_result=result,
            error=None,
        )
        return {"ok": True, "job": updated or job, "commit_result": result}

    if not gate.get("can_commit"):
        result = {
            "ok": False,
            "skipped": True,
            "error": "门禁未通过或非 git 仓，已拒绝提交",
            "branch": branch,
            "commit": "",
        }
        summary = f"## 未能提交\n\n{result['error']}\n"
        job_store.append_message(data_dir, job_id, role="assistant", content=summary)
        updated = job_store.update_job(
            data_dir,
            job_id,
            status="succeeded",
            commit_result=result,
            error=None,
        )
        return {"ok": True, "job": updated or job, "commit_result": result}

    raw_msg = (commit_message if commit_message is not None else "") or str(
        job.get("commit_message") or gate.get("suggested_commit_message") or ""
    )
    ok_msg, msg_err = validate_chinese_commit_message(raw_msg)
    if not ok_msg:
        result = {
            "ok": False,
            "skipped": False,
            "error": msg_err,
            "branch": branch,
            "commit": "",
        }
        summary = f"## 提交失败\n\n{msg_err}\n"
        job_store.append_message(data_dir, job_id, role="assistant", content=summary)
        # 允许用户改说明后再次确认：清掉 decision
        updated = job_store.update_job(
            data_dir,
            job_id,
            status="awaiting_commit",
            commit_decision=None,
            commit_result=result,
            error=msg_err,
        )
        return {"ok": False, "error": msg_err, "job": updated or job, "commit_result": result}

    msg = raw_msg.strip()[:200]
    try:
        result = commit_synced_files(
            ws,
            files,
            message=msg,
            work_branch=branch,
            push=push,
            push_url=push_url,
            save_remote=save_remote,
        )
    except Exception as exc:  # noqa: BLE001
        result = {
            "ok": False,
            "skipped": False,
            "error": f"{type(exc).__name__}: {exc}",
            "branch": branch,
            "commit": "",
        }

    if result.get("ok") and result.get("commit") and not result.get("skipped"):
        ignored = list(result.get("skipped_ignored") or [])
        summary = (
            f"## 已提交本批代码\n\n"
            f"说明：{msg}\n"
            f"分支：`{result.get('branch')}`\n"
            f"commit：`{result.get('commit')}`\n"
            f"文件数：{len(result.get('files') or files)}\n"
        )
        if ignored:
            preview = ", ".join(f"`{p}`" for p in ignored[:5])
            more = f" 等 {len(ignored)} 个" if len(ignored) > 5 else ""
            summary += f"\n已跳过 .gitignore 忽略文件：{preview}{more}\n"
        push_info = result.get("push") if isinstance(result.get("push"), dict) else None
        if push_info is None:
            summary += "\n（仅本地提交，未 push）\n"
        elif push_info.get("ok"):
            remote = push_info.get("remote") or "origin"
            url = push_info.get("remote_url") or ""
            summary += f"\n已推送到远程 `{remote}/{result.get('branch')}`"
            if url:
                summary += f"（{url}）"
            summary += "\n"
        else:
            summary += f"\n**本地已提交，推送失败：** {push_info.get('error') or '未知错误'}\n"
    elif result.get("ok") and result.get("skipped"):
        push_info = result.get("push") if isinstance(result.get("push"), dict) else None
        summary = f"## 未产生新提交\n\n{result.get('message') or result.get('error') or '无变更'}\n"
        if push_info is not None:
            if push_info.get("ok"):
                url = push_info.get("remote_url") or ""
                summary += (
                    f"\n已推送当前分支 `{result.get('branch')}` 到远程"
                    + (f"（{url}）" if url else "")
                    + "。\n"
                )
            else:
                summary += f"\n**推送失败：** {push_info.get('error') or '未知错误'}\n"
    else:
        summary = f"## 提交失败\n\n{result.get('error') or '未知错误'}\n"

    from local_dev.git_commit import is_commit_retryable, is_push_retry_needed

    retryable = is_commit_retryable(result)
    push_retry = is_push_retry_needed(result)
    if retryable:
        push_info = result.get("push") if isinstance(result.get("push"), dict) else None
        if push_retry:
            summary += (
                "\n**本地已提交，远程推送失败**；修复网络后请在确认卡点「重试推送」（不会重新 commit）。\n"
            )
        elif push_info is not None and not push_info.get("ok") and result.get("commit"):
            summary += "\n**网络原因推送失败，本地已提交**；修复网络后可在确认卡点「重试推送」。\n"
        else:
            summary += "\n**疑似网络原因**；修复网络后可在确认卡重试提交。\n"
        result = {**result, "retryable": True, "push_retry": bool(push_retry)}

    job_store.append_message(data_dir, job_id, role="assistant", content=summary)
    if retryable:
        push_info = result.get("push") if isinstance(result.get("push"), dict) else None
        err_out = str(result.get("error") or "")
        if push_info is not None and not push_info.get("ok"):
            err_out = str(push_info.get("error") or err_out)
        updated = job_store.update_job(
            data_dir,
            job_id,
            status="awaiting_commit",
            commit_decision=None,
            commit_result=result,
            error=err_out or None,
        )
        return {
            "ok": True,
            "retryable": True,
            "job": updated or job,
            "commit_result": result,
            "summary": summary,
        }

    updated = job_store.update_job(
        data_dir,
        job_id,
        status="succeeded",
        commit_result=result,
        error=None if result.get("ok") else (result.get("error") or None),
    )
    return {"ok": True, "job": updated or job, "commit_result": result, "summary": summary}
