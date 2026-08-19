"""Agent 工具：本机 IDE 审核 / 公开 Git 审核。

挂载策略见 create_agent：git 工具默认挂载；ide 工具需 IDE_REVIEW_ENABLED。
本机工程文件必须经 Bridge/VS Code 扩展读取，禁止用服务端 read_file 读
/Users/... 等本机绝对路径（会报 File not found）。
"""
from __future__ import annotations

import json
import os
from typing import Annotated, Any

from middleware.request_context import get_page_context, get_thread_id, get_user_id
from tools.ide_review.bridge_store import (
    submit_list_files_task,
    submit_read_files_task,
    submit_review_task,
)
from tools.ide_review.enrich import enrich_bridge_result

_IDE_PATH_HINT = (
    "禁止对用户本机绝对路径调用服务端 read_file/grep。"
    "本机全仓：request_ide_list_source_files → request_ide_read_batch。"
    "公开 Git 全仓：request_git_list_source_files → request_git_read_batch。"
    "仅抽样/离线本机目录：request_git_review(local_path=… 或 repo_url=…)。"
)

# 每批固定 5 个文件（产品约定）
_READ_FILES_MAX_PATHS = 5
_BATCH_SIZE = 5

_CURSOR_DEV_LANE_BLOCK = (
    "当前为写码分支（workbuddy_lane=code_dev），与代码审核是对等的另一条路由。"
    "禁止调用 Git/IDE 审核工具。请只澄清需求并输出 :::cursor_dev_options 或 :::cursor_dev_propose；"
    "默认本机目录（target=local）；GitHub 用 target=github。勿直读本机绝对路径。"
    "本机写码经沙箱同步；GitHub 改仓由用户确认后经 Cursor Cloud 执行。提及仓库名不等于审核意图。"
)


def _reject_if_cursor_dev_coding_lane() -> dict[str, Any] | None:
    """写码分支硬拒绝审核工具；审核分支不受影响（两条路由互不干涉）。"""
    ctx = get_page_context() or {}
    lane = str(ctx.get("workbuddy_lane") or "").strip()
    if lane == "code_review":
        return None
    if lane == "code_dev" or ctx.get("cursor_dev_lane") or str(
        ctx.get("cursor_dev_repo") or ""
    ).strip():
        return {
            "status": "error",
            "provider": "cursor_dev_lane",
            "message": _CURSOR_DEV_LANE_BLOCK,
            "findings": [],
            "file_contents": [],
            "total": 0,
            "batch_count": 0,
            "path_hint": "禁止 request_git_* / request_ide_*；输出 cursor_dev 机器块。",
        }
    return None


def _page_ide_workspace_root() -> str:
    ctx = get_page_context() or {}
    return str(ctx.get("ide_workspace_root") or "").strip()


def _page_git_repo_url() -> str:
    ctx = get_page_context() or {}
    return str(ctx.get("git_repo_url") or "").strip()


def _page_git_ref() -> str:
    ctx = get_page_context() or {}
    return str(ctx.get("git_ref") or "").strip()


def _review_batch_max_chars() -> int:
    try:
        return max(8000, int(os.getenv("IDE_REVIEW_BATCH_MAX_CHARS", "65536")))
    except (TypeError, ValueError):
        return 65536


def _trim_file_contents(result: dict[str, Any], *, max_chars: int | None = None) -> dict[str, Any]:
    cap = max_chars if max_chars is not None else _review_batch_max_chars()
    contents = result.get("file_contents")
    if not isinstance(contents, list) or not contents:
        return result
    out = dict(result)
    kept: list[Any] = []
    used = 0
    for item in contents:
        if not isinstance(item, dict):
            continue
        text = str(item.get("content") or "")
        if used + len(text) > cap:
            remain = max(0, cap - used)
            if remain < 200:
                out["file_contents_truncated"] = True
                break
            item = dict(item)
            item["content"] = text[:remain]
            item["truncated"] = True
            kept.append(item)
            out["file_contents_truncated"] = True
            break
        kept.append(item)
        used += len(text)
    out["file_contents"] = kept
    return out


def request_ide_review(
    paths: Annotated[
        list[str] | None,
        "工作区相对路径列表，如 [\"src/main/java/.../Foo.java\"]；也可传工作区内绝对路径（由 Bridge 归一化）",
    ] = None,
    prompt: Annotated[str, "审核关注点，如「关注安全与空指针」"] = "",
    workspace_root: Annotated[
        str,
        "可选：本机工程根路径；通常由前端确认框写入 page_context.ide_workspace_root，也可显式传入",
    ] = "",
) -> dict[str, Any]:
    """审核用户本机工程（经 Bridge；可为最近打开的目录，不必是当前打开文件夹）。

    工程目录优先：参数 workspace_root > page_context.ide_workspace_root > Bridge 当前打开目录。
    返回 findings，并必须尽量附带 file_contents（源码正文）。
    - 有 file_contents：必须基于源码按 Skill「code-review」(Viprasol) 做深度审查，再套中文报告壳
      （问题总览 → P0/P1/P2 → 优先修复建议）；禁止让用户贴代码；禁止自造检查清单。
    - findings 为空：不等于代码无问题；以 file_contents 为主审依据。
    - 切勿再用 read_file 去读返回的 workspace_root 绝对路径。
    - 已拿到非空 file_contents 后禁止再批量 request_ide_read_files 扫全仓；立刻写报告。
    """
    blocked = _reject_if_cursor_dev_coding_lane()
    if blocked:
        return blocked
    user_id = get_user_id()
    root = (workspace_root or "").strip() or _page_ide_workspace_root()
    result = submit_review_task(
        user_id,
        paths=paths,
        prompt=prompt or "",
        thread_id=get_thread_id(),
        workspace_root=root or None,
    )
    result = enrich_bridge_result(dict(result))
    result["path_hint"] = _IDE_PATH_HINT
    findings = result.get("findings") or []
    if isinstance(findings, list) and len(findings) > 40:
        result["findings"] = findings[:40]
        result["findings_truncated"] = True
        result["findings_total"] = len(findings)
    contents = result.get("file_contents") or []
    if contents:
        result["next_step"] = (
            "此为单次抽样审核。若用户要审「整个工程/全仓」，"
            "请改走 request_ide_list_source_files → 按 batches 分批读审 → 终稿。"
        )
    if not contents:
        result["upgrade_hint"] = (
            "file_contents 仍为空：请升级 VS Code 扩展到 v0.4.2+（Reload Window），"
            "确认所选工程目录存在源码；或改用 request_git_review(local_path=工程根目录)。"
        )
    if result.get("status") == "offline":
        result["fallback_hint"] = (
            "Bridge 离线：可调用 request_git_review(local_path=\"本机工程绝对路径\") "
            "或 repo_url=Git 地址做只读审核（同模板出报告）。"
        )
    return _trim_file_contents(result)


def request_ide_read_files(
    paths: Annotated[
        list[str],
        "本批路径，最多 5 个；全仓请优先用 request_ide_read_batch(batch_index)",
    ],
    workspace_root: Annotated[str, "可选：工程根路径"] = "",
) -> dict[str, Any]:
    """按路径列表读取（≤5）。全仓循环请用 request_ide_read_batch。"""
    return _read_paths(
        list(paths) if not isinstance(paths, str) else [paths],
        workspace_root=workspace_root,
        batch_index=None,
    )


def request_ide_read_batch(
    batch_index: Annotated[int, "从 0 开始的批次号（list 之后使用）"],
    workspace_root: Annotated[str, "可选；默认用 list 时的工程根"] = "",
) -> dict[str, Any]:
    """按批次号读取下一组最多 5 个文件（全仓分批主路径，避免把全部路径塞进上下文）。"""
    blocked = _reject_if_cursor_dev_coding_lane()
    if blocked:
        return blocked
    from tools.ide_review.batch_plan import get_batch_paths

    info = get_batch_paths(get_thread_id(), int(batch_index))
    if info.get("status") != "ok":
        return {
            **info,
            "file_contents": [],
            "files": [],
            "path_hint": _IDE_PATH_HINT,
        }
    root = (workspace_root or "").strip() or str(info.get("workspace_root") or "")
    out = _read_paths(
        list(info.get("paths") or []),
        workspace_root=root,
        batch_index=int(batch_index),
        batch_count=int(info.get("batch_count") or 0),
        next_batch_index=info.get("next_batch_index"),
        done_after=bool(info.get("done_after")),
    )
    return out


def _read_paths(
    path_list: list[str],
    *,
    workspace_root: str = "",
    batch_index: int | None = None,
    batch_count: int = 0,
    next_batch_index: int | None = None,
    done_after: bool = False,
) -> dict[str, Any]:
    blocked = _reject_if_cursor_dev_coding_lane()
    if blocked:
        return blocked
    user_id = get_user_id()
    paths = [str(p).strip() for p in (path_list or []) if str(p).strip()]
    truncated = False
    if len(paths) > _READ_FILES_MAX_PATHS:
        paths = paths[:_READ_FILES_MAX_PATHS]
        truncated = True
    root = (workspace_root or "").strip() or _page_ide_workspace_root()

    result: dict[str, Any] = {}
    # 同机直读：避免 Bridge 认领后丢失导致空等卡死
    if root:
        from pathlib import Path

        from tools.ide_review.local_files import read_workspace_files

        if Path(root).is_dir():
            packed = read_workspace_files(Path(root), paths)
            if packed.get("file_contents"):
                result = dict(packed)
                result["local_fill"] = "prefer_same_host"

    if not (result.get("file_contents") or []):
        bridge = submit_read_files_task(
            user_id,
            paths=paths,
            thread_id=get_thread_id(),
            workspace_root=root or None,
            timeout_sec=45.0,
        )
        result = enrich_bridge_result(dict(bridge or {}))
        if not (result.get("file_contents") or []) and root:
            from pathlib import Path

            from tools.ide_review.local_files import read_workspace_files

            if Path(root).is_dir():
                packed = read_workspace_files(Path(root), paths)
                if packed.get("file_contents"):
                    result = dict(result)
                    result.update(packed)
                    result["local_fill"] = "ok"

    result = dict(result)
    result["path_hint"] = _IDE_PATH_HINT
    if truncated:
        result["paths_truncated"] = True
        result["paths_limit"] = _READ_FILES_MAX_PATHS
    if batch_index is not None:
        result["batch_index"] = batch_index
        result["batch_count"] = batch_count
        result["next_batch_index"] = next_batch_index
        result["done_after"] = done_after
        if done_after:
            result["next_step"] = (
                f"第 {batch_index + 1}/{batch_count} 批（最后一批）已读完。"
                "合并此前各批纪要，立刻输出完整「🔍 代码审核报告」。"
                "第一行必须是「## 🔍 代码审核报告」。"
                "禁止再调用 request_ide_read_files / request_ide_read_batch 补读配置或其它文件。"
                "每条问题必须含：问题描述、问题代码、修复建议、修复代码（完整相对路径）。"
            )
        else:
            result["next_step"] = (
                f"写「第 {batch_index + 1}/{batch_count} 批审核纪要」（含问题代码摘录，勿贴全文），"
                f"然后立刻 request_ide_read_batch(batch_index={next_batch_index})。"
            )
    else:
        result["next_step"] = (
            "写本批纪要后继续；全仓请用 request_ide_read_batch 按序号推进。"
        )
    return _trim_file_contents(result)


def request_ide_list_source_files(
    workspace_root: Annotated[
        str,
        "可选：本机工程根；默认用 page_context.ide_workspace_root",
    ] = "",
) -> dict[str, Any]:
    """枚举工程可审源文件并建立分批计划（每批 5 个）。

    返回摘要（总数/批次数），不把全部路径塞进模型上下文。
    随后用 request_ide_read_batch(0), read_batch(1), … 循环直至 done。
    """
    blocked = _reject_if_cursor_dev_coding_lane()
    if blocked:
        return blocked
    from pathlib import Path

    from tools.ide_review.batch_plan import save_repo_plan
    from tools.ide_review.bridge_store import get_status
    from tools.ide_review.local_files import list_workspace_source_files

    user_id = get_user_id()
    root = (workspace_root or "").strip() or _page_ide_workspace_root()
    listed: dict[str, Any] = {}

    if root and Path(root).is_dir():
        listed = list_workspace_source_files(Path(root), batch_size=_BATCH_SIZE)
        listed["local_fill"] = "prefer_same_host"
    else:
        bridge = submit_list_files_task(
            user_id,
            thread_id=get_thread_id(),
            workspace_root=root or None,
            timeout_sec=45.0,
        )
        listed = dict(bridge or {})
        if listed.get("status") != "ok" or not (listed.get("files") or listed.get("batches")):
            st = get_status(user_id)
            fill_root = root or str(st.get("workspace_root") or "").strip()
            if fill_root and Path(fill_root).is_dir():
                listed = list_workspace_source_files(Path(fill_root), batch_size=_BATCH_SIZE)
                listed["local_fill"] = "ok"
                root = fill_root

    files = list(listed.get("files") or [])
    if not files and listed.get("batches"):
        for b in listed["batches"]:
            files.extend(list(b or []))
    root_final = root or str(listed.get("workspace_root") or "")
    meta = save_repo_plan(
        get_thread_id(),
        workspace_root=root_final,
        files=files,
        batch_size=int(listed.get("batch_size") or _BATCH_SIZE),
    )
    return {
        "status": "ok" if meta["total"] else "error",
        "workspace_root": root_final,
        "total": meta["total"],
        "batch_size": meta["batch_size"],
        "batch_count": meta["batch_count"],
        "truncated": bool(listed.get("truncated")),
        "provider": listed.get("provider") or "local",
        "raw_summary": (
            f"共 {meta['total']} 个功能源码文件（已排除配置/锁文件/样式/文档等），"
            f"分 {meta['batch_count']} 批（每批 {meta['batch_size']}）。"
            "路径已在服务端缓存。"
        ),
        "filter": "functional_source_only",
        "first_batch_preview": (files[: meta["batch_size"]] if files else []),
        "path_hint": _IDE_PATH_HINT,
        "next_step": (
            "立刻 request_ide_read_batch(batch_index=0)；每批写短纪要后递增；"
            "全部完成后再输出完整终稿。只审功能代码，勿要求补审配置文件。"
            if meta["batch_count"]
            else "未枚举到功能源码，请确认工程路径。"
        ),
    }


def request_git_review(
    local_path: Annotated[
        str,
        "本机工程根目录绝对路径（与 API 同机可读时推荐）；与 repo_url 二选一",
    ] = "",
    repo_url: Annotated[
        str,
        "公开 HTTPS Git 仓库 URL（https://…）；浅克隆后抽样审核；与 local_path 二选一。"
        "不支持 SSH / 私有仓 Token。全仓请用 request_git_list_source_files",
    ] = "",
    ref: Annotated[str, "可选分支名或 tag"] = "",
    paths: Annotated[
        list[str] | None,
        "可选：相对路径或目录，限制审核范围",
    ] = None,
    prompt: Annotated[str, "审核关注点"] = "",
) -> dict[str, Any]:
    """一次性抽样审核（兼容路径）。公开 Git 全仓必须改用分批工具。

    有【Git仓库已确认】/ page_context.git_repo_url 时：
    优先 request_git_list_source_files → request_git_read_batch（禁止 request_ide_*）。
    本工具仅用于明确只要抽样、或 Bridge 离线审本机 local_path。
    """
    blocked = _reject_if_cursor_dev_coding_lane()
    if blocked:
        return blocked
    from tools.ide_review.git_review import run_git_or_local_review

    try:
        result = run_git_or_local_review(
            local_path=local_path or "",
            repo_url=repo_url or "",
            ref=ref or "",
            paths=paths,
            prompt=prompt or "",
        )
    except (FileNotFoundError, ValueError, RuntimeError) as e:
        return {
            "status": "error",
            "provider": "git_review",
            "message": str(e),
            "findings": [],
            "file_contents": [],
            "path_hint": _IDE_PATH_HINT,
        }
    result = dict(result)
    result["path_hint"] = _IDE_PATH_HINT
    findings = result.get("findings") or []
    if isinstance(findings, list) and len(findings) > 40:
        result["findings"] = findings[:40]
        result["findings_truncated"] = True
        result["findings_total"] = len(findings)
    if result.get("status") == "ok":
        result["upgrade_hint"] = (
            "公开 Git 全仓核心代码：请改用 request_git_list_source_files → "
            "request_git_read_batch(0..N-1) → 合并终稿，勿仅用本工具结案。"
        )
    return _trim_file_contents(result)


def request_git_list_source_files(
    repo_url: Annotated[
        str,
        "公开 HTTPS 仓库地址；默认取 page_context.git_repo_url",
    ] = "",
    ref: Annotated[str, "可选分支/tag；默认 page_context.git_ref"] = "",
    local_path: Annotated[
        str,
        "可选：同机本地目录（离线降级）；与 repo_url 二选一",
    ] = "",
) -> dict[str, Any]:
    """克隆/打开公开 Git 仓（按会话缓存），枚举全部功能源码并建立分批计划（每批 5）。

    返回摘要（总数/批次数）；随后 request_git_read_batch(0)..(N-1)，全部完成后再写终稿。
    禁止对本流程调用 request_ide_*。
    """
    blocked = _reject_if_cursor_dev_coding_lane()
    if blocked:
        return blocked
    from pathlib import Path

    from tools.ide_review.batch_plan import save_repo_plan
    from tools.ide_review.git_review import ensure_git_workspace
    from tools.ide_review.local_files import list_workspace_source_files

    tid = get_thread_id()
    url = (repo_url or "").strip() or _page_git_repo_url()
    ref_n = (ref or "").strip() or _page_git_ref()
    local = (local_path or "").strip()
    try:
        ws = ensure_git_workspace(
            tid, local_path=local, repo_url=url, ref=ref_n
        )
    except (FileNotFoundError, ValueError, RuntimeError) as e:
        return {
            "status": "error",
            "provider": "git_review",
            "message": str(e),
            "total": 0,
            "batch_count": 0,
            "path_hint": _IDE_PATH_HINT,
        }

    root = str(ws.get("workspace_root") or "")
    listed = list_workspace_source_files(Path(root), batch_size=_BATCH_SIZE)
    files = list(listed.get("files") or [])
    meta = save_repo_plan(
        tid,
        workspace_root=root,
        files=files,
        batch_size=int(listed.get("batch_size") or _BATCH_SIZE),
    )
    return {
        "status": "ok" if meta["total"] else "error",
        "provider": "git_review",
        "mode": ws.get("mode"),
        "repo_url": ws.get("repo_url") or url,
        "ref": ws.get("ref") or ref_n or "default",
        "workspace_root": root,
        "reused_clone": bool(ws.get("reused")),
        "total": meta["total"],
        "batch_size": meta["batch_size"],
        "batch_count": meta["batch_count"],
        "truncated": bool(listed.get("truncated")),
        "filter": "functional_source_only",
        "first_batch_preview": (files[: meta["batch_size"]] if files else []),
        "raw_summary": (
            f"公开 Git 仓共 {meta['total']} 个功能源码文件"
            f"{'（已达枚举上限）' if listed.get('truncated') else ''}，"
            f"分 {meta['batch_count']} 批（每批 {meta['batch_size']}）。路径已缓存。"
        ),
        "path_hint": _IDE_PATH_HINT,
        "next_step": (
            "立刻 request_git_read_batch(batch_index=0)；每批静默记下问题后递增；"
            "禁止中途输出报告；全部批次完成后再输出完整「🔍 代码审核报告」。"
            if meta["batch_count"]
            else "未枚举到功能源码，请确认仓库含 .py/.js/.java 等业务代码。"
        ),
    }


def request_git_read_batch(
    batch_index: Annotated[int, "批次序号，从 0 开始"] = 0,
) -> dict[str, Any]:
    """按 request_git_list_source_files 建立的计划，读取第 batch_index 批（每批最多 5 文件）。

    过程中禁止向用户输出正文；done_after=true 时合并各批写终稿。
    clone 缓存按会话 TTL 回收（末批不立刻删，便于报告失败后重试/补读）。
    """
    blocked = _reject_if_cursor_dev_coding_lane()
    if blocked:
        return blocked
    from pathlib import Path

    from tools.ide_review.batch_plan import get_batch_paths
    from tools.ide_review.enrich import augment_findings_from_contents
    from tools.ide_review.git_review import get_git_workspace_root
    from tools.ide_review.local_files import read_workspace_files

    tid = get_thread_id()
    info = get_batch_paths(tid, int(batch_index))
    if info.get("status") != "ok":
        msg = str(info.get("message") or "没有分批计划")
        if "request_ide_list" in msg:
            msg = "没有分批计划，请先调用 request_git_list_source_files"
        return {
            "status": "error",
            "provider": "git_review",
            "message": msg,
            "file_contents": [],
            "findings": [],
            "path_hint": _IDE_PATH_HINT,
        }

    root = str(info.get("workspace_root") or "").strip() or get_git_workspace_root(tid)
    paths = list(info.get("paths") or [])
    if not root or not Path(root).is_dir():
        return {
            "status": "error",
            "provider": "git_review",
            "message": "Git 工作区已失效，请重新 request_git_list_source_files",
            "file_contents": [],
            "findings": [],
            "path_hint": _IDE_PATH_HINT,
        }

    packed = read_workspace_files(Path(root), paths)
    # 过程卡与 IDE 图二对齐：workspace_root=克隆根绝对路径；files=仓内完整相对路径
    rel_files = [str(p).replace("\\", "/").strip() for p in paths if str(p).strip()]
    # 若 read 归一化后有路径，仍以计划路径为准（保证含目录前缀）
    if packed.get("files"):
        # 合并：保持计划顺序，补全已读相对路径
        got = {
            str(p).replace("\\", "/").strip()
            for p in (packed.get("files") or [])
            if str(p).strip()
        }
        rel_files = [p for p in rel_files if p in got] or [
            str(p).replace("\\", "/").strip()
            for p in (packed.get("files") or [])
            if str(p).strip()
        ]
    result: dict[str, Any] = {
        "status": "ok",
        "provider": "git_review",
        "findings": [],
        "file_contents": packed.get("file_contents") or [],
        "files": rel_files,
        "errors": packed.get("errors") or [],
        "batch_index": int(info.get("batch_index") or batch_index),
        "batch_count": int(info.get("batch_count") or 0),
        "next_batch_index": info.get("next_batch_index"),
        "done_after": bool(info.get("done_after")),
        "total": info.get("total"),
        "workspace_root": root,
        "repo_url": _page_git_repo_url() or "",
        "raw_summary": (
            f"Git 第 {int(info.get('batch_index') or 0) + 1}/"
            f"{info.get('batch_count')} 批，"
            f"{len(rel_files)} 个文件"
        ),
        "path_hint": _IDE_PATH_HINT,
    }
    result = augment_findings_from_contents(result)
    bi = int(result["batch_index"])
    bc = int(result["batch_count"] or 0)
    if result.get("done_after"):
        result["next_step"] = (
            f"第 {bi + 1}/{bc} 批（最后一批）已读完。"
            "合并此前各批问题，立刻输出完整「🔍 代码审核报告」。"
            "第一行必须是「## 🔍 代码审核报告」。"
            "禁止再调用 request_git_read_batch / request_git_list_source_files 补读或回补漏批；"
            "漏批内容已在上下文中则直接写入终稿。"
            "每条问题必须含：问题描述、问题代码、修复建议、修复代码（完整相对路径）。"
        )
        # 不在此释放 clone：报告生成/短确认续审可能仍需工作区；由 TTL 回收
    else:
        nxt = result.get("next_batch_index")
        result["next_step"] = (
            f"第 {bi + 1}/{bc} 批已读完：静默记下 P0/P1/P2（含问题代码摘录），"
            f"立刻 request_git_read_batch(batch_index={nxt})；"
            "必须按 batch_index 顺序推进，禁止跳批；禁止输出终稿。"
        )
    return _trim_file_contents(result)


def format_review_for_cli(result: dict[str, Any]) -> str:
    return json.dumps(result, ensure_ascii=False, indent=2)
