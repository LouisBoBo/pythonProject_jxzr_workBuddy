"""Agent 工具：本机代码审核 / 读文件（仅 IDE_REVIEW_ENABLED 时挂载）。

本机工程文件必须经 Bridge/VS Code 扩展读取，禁止用服务端 read_file 读
/Users/... 等本机绝对路径（会报 File not found）。
"""
from __future__ import annotations

import json
from typing import Annotated, Any

from middleware.request_context import get_page_context, get_thread_id, get_user_id
from tools.ide_review.bridge_store import submit_read_files_task, submit_review_task
from tools.ide_review.enrich import enrich_bridge_result

_IDE_PATH_HINT = (
    "禁止对用户本机绝对路径调用服务端 read_file/grep。"
    "本机代码请用 request_ide_review / request_ide_read_files；"
    "Bridge 离线时用 request_git_review(local_path=… 或 repo_url=…)。"
    "路径优先用工作区相对路径（如 src/main/java/.../Foo.java）。"
)


def _page_ide_workspace_root() -> str:
    ctx = get_page_context() or {}
    return str(ctx.get("ide_workspace_root") or "").strip()


def _trim_file_contents(result: dict[str, Any], *, max_chars: int = 120_000) -> dict[str, Any]:
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
        if used + len(text) > max_chars:
            remain = max(0, max_chars - used)
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
    """
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
        "必须：工作区相对路径，或位于目标 VS Code 工程内的绝对路径",
    ],
    workspace_root: Annotated[str, "可选：工程根路径（同 request_ide_review）"] = "",
) -> dict[str, Any]:
    """读取用户本机 VS Code 工作区中的文件内容（经 Bridge）。

    当需要查看/引用本机工程源码时，必须用本工具，而不是 read_file。
    """
    user_id = get_user_id()
    # 兼容模型传入单个字符串
    if isinstance(paths, str):
        path_list = [paths]
    else:
        path_list = list(paths or [])
    root = (workspace_root or "").strip() or _page_ide_workspace_root()
    result = submit_read_files_task(
        user_id,
        paths=path_list,
        thread_id=get_thread_id(),
        workspace_root=root or None,
    )
    result = enrich_bridge_result(dict(result))
    # read_files 若仍空，用 paths 直接同机补读
    if not (result.get("file_contents") or []):
        from pathlib import Path

        from tools.ide_review.bridge_store import get_status
        from tools.ide_review.local_files import read_workspace_files

        st = get_status(user_id)
        fill_root = root or str(st.get("workspace_root") or "").strip()
        if fill_root and Path(fill_root).is_dir():
            packed = read_workspace_files(Path(fill_root), path_list)
            if packed.get("file_contents"):
                result = dict(result)
                result.update(packed)
                result["local_fill"] = "ok"
    result = dict(result)
    result["path_hint"] = _IDE_PATH_HINT
    return _trim_file_contents(result)


def request_git_review(
    local_path: Annotated[
        str,
        "本机工程根目录绝对路径（与 API 同机可读时推荐）；与 repo_url 二选一",
    ] = "",
    repo_url: Annotated[
        str,
        "Git 仓库 URL（https/ssh）；将浅克隆后审核；与 local_path 二选一",
    ] = "",
    ref: Annotated[str, "可选分支名或 tag"] = "",
    paths: Annotated[
        list[str] | None,
        "可选：相对路径或目录，限制审核范围",
    ] = None,
    prompt: Annotated[str, "审核关注点"] = "",
) -> dict[str, Any]:
    """不依赖 VS Code Bridge：审本机目录或 Git 仓（只读）。

    Bridge 在线时仍优先 request_ide_review。离线或审远端分支时用本工具。
    返回 findings + file_contents，须按固定代码审核报告模板输出。
    """
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
    return _trim_file_contents(result)


def format_review_for_cli(result: dict[str, Any]) -> str:
    return json.dumps(result, ensure_ascii=False, indent=2)
