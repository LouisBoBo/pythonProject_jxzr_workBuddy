"""P2：css_layout 小改补丁通道（GitHub Contents API）。

不经 Cursor Cloud 拉仓；失败则返回 ok=False，由调用方回退 Cloud。
质量闸门：仅 css_layout、少文件、改动幅度受限、路径必须来自锚点/索引。
"""
from __future__ import annotations

import base64
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from .allowlist import normalize_repo
from .github_preflight import _github_token, _get_json
from .prompts import classify_task_tier, extract_page_search_hints, merge_file_anchors
from .repo_index import get_or_refresh_repo_index, match_paths_by_hints

_MAX_FILES = 3
_MAX_FILE_CHARS = 120_000
_MIN_KEEP_RATIO = 0.55
_MAX_GROW_RATIO = 1.45


def _request_json(
    url: str,
    *,
    method: str = "GET",
    body: dict[str, Any] | None = None,
    timeout: float = 45.0,
) -> dict[str, Any]:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "workbuddy-cursor-dev-patch",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    token = _github_token()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    data = None
    if body is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode("utf-8")
        return json.loads(raw) if raw.strip() else {}


def eligible_for_patch_channel(
    message: str,
    *,
    has_images: bool = False,
) -> bool:
    if has_images:
        return False
    if not _github_token():
        return False
    if classify_task_tier(message, has_images=False) != "css_layout":
        return False
    # 明确大改 / 多页 / 逻辑 → 不走补丁
    if re.search(r"重构|新功能|接口|权限|登录鉴权|数据库|多页面|全部页面", message or "", re.I):
        return False
    return True


def _fetch_file(repo: str, path: str, ref: str) -> dict[str, Any] | None:
    try:
        data = _get_json(
            f"https://api.github.com/repos/{repo}/contents/{urllib.parse.quote(path)}"
            f"?ref={urllib.parse.quote(ref)}"
        )
    except Exception:
        return None
    if not isinstance(data, dict) or data.get("type") != "file":
        return None
    content = data.get("content") or ""
    encoding = (data.get("encoding") or "").lower()
    try:
        if encoding == "base64":
            text = base64.b64decode(content).decode("utf-8", errors="replace")
        else:
            text = str(content)
    except Exception:
        return None
    if len(text) > _MAX_FILE_CHARS:
        return None
    return {
        "path": path,
        "content": text,
        "sha": str(data.get("sha") or ""),
    }


def _put_file(
    repo: str,
    path: str,
    *,
    content: str,
    sha: str,
    branch: str,
    message: str,
) -> dict[str, Any]:
    body = {
        "message": message,
        "content": base64.b64encode(content.encode("utf-8")).decode("ascii"),
        "branch": branch,
        "sha": sha,
    }
    return _request_json(
        f"https://api.github.com/repos/{repo}/contents/{urllib.parse.quote(path)}",
        method="PUT",
        body=body,
    )


def _llm_patch(
    *,
    requirement: str,
    files: list[dict[str, str]],
) -> dict[str, Any]:
    """调用与主 Agent 相同的 LLM；返回 {ok, files, summary, error}。"""
    try:
        from config import Config

        Config.reload_runtime()
        api_key = (Config.LLM_API_KEY or "").strip()
        model_name = Config.MODEL_NAME
        base = (Config.LLM_BASE_URL or "").rstrip("/")
    except Exception:
        api_key = (
            os.getenv("LLM_API_KEY")
            or os.getenv("DEEPSEEK_API_KEY")
            or os.getenv("SILICONFLOW_API_KEY")
            or ""
        ).strip()
        model_name = os.getenv("MODEL_NAME") or os.getenv("MAIN_MODEL") or "deepseek-chat"
        base = (
            os.getenv("LLM_BASE_URL")
            or os.getenv("DEEPSEEK_BASE_URL")
            or "https://api.deepseek.com"
        ).rstrip("/")
    if not api_key:
        return {"ok": False, "error": "无可用 LLM Key，跳过补丁通道"}
    model = model_name or "deepseek-chat"
    if not base:
        base = "https://api.openai.com/v1"
    if not base.endswith("/v1"):
        url = base + "/v1/chat/completions"
    else:
        url = base + "/chat/completions"
    file_blocks = []
    for f in files:
        file_blocks.append(
            f"### FILE: {f['path']}\n```\n{f['content']}\n```"
        )
    sys_prompt = (
        "你是前端样式修复器。只修 overflow/宽度/滚动/ECharts resize 等布局问题。"
        "禁止改配色、图表 option 业务数据、文案、路由与接口。"
        "必须只输出 JSON（不要 markdown）："
        '{"summary":"一句话","files":[{"path":"相对路径","content":"完整文件新内容"}]}。'
        "files 只能包含我提供的 path；content 必须是完整文件。"
    )
    user_prompt = (
        f"需求：\n{requirement.strip()}\n\n"
        f"待改文件：\n" + "\n\n".join(file_blocks)
    )
    payload = {
        "model": model,
        "temperature": 0.1,
        "messages": [
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "response_format": {"type": "json_object"},
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
            raw = json.loads(resp.read().decode("utf-8"))
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": f"LLM 调用失败：{type(exc).__name__}: {exc}"}

    try:
        text = raw["choices"][0]["message"]["content"]
    except Exception:
        return {"ok": False, "error": "LLM 响应无 content"}
    text = str(text or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return {"ok": False, "error": "LLM 未返回合法 JSON"}
    out_files = data.get("files") if isinstance(data, dict) else None
    if not isinstance(out_files, list) or not out_files:
        return {"ok": False, "error": "LLM JSON 缺少 files"}
    return {
        "ok": True,
        "summary": str((data or {}).get("summary") or "已应用样式补丁"),
        "files": out_files,
        "error": "",
    }


def _validate_patch(
    original: dict[str, str],
    patched_files: list[Any],
) -> tuple[bool, str, list[dict[str, str]]]:
    allowed = set(original.keys())
    cleaned: list[dict[str, str]] = []
    for item in patched_files:
        if not isinstance(item, dict):
            return False, "files 项非法", []
        raw_path = str(item.get("path") or "").replace("\\", "/").strip()
        if (
            not raw_path
            or raw_path.startswith("/")
            or any(part == ".." for part in raw_path.split("/"))
        ):
            return False, f"非法路径：{raw_path}", []
        path = raw_path.lstrip("./")
        content = item.get("content")
        if path not in allowed:
            return False, f"禁止改未授权路径：{path}", []
        if not isinstance(content, str) or not content.strip():
            return False, f"空内容：{path}", []
        if len(content) > _MAX_FILE_CHARS:
            return False, f"文件过大：{path}", []
        old = original[path]
        if old == content:
            continue
        ratio = len(content) / max(1, len(old))
        if ratio < _MIN_KEEP_RATIO or ratio > _MAX_GROW_RATIO:
            return False, f"改动幅度过大（疑非纯样式）：{path}", []
        # 粗拦：删掉大半 script 或引入明显后端逻辑关键词
        if re.search(r"\b(DROP TABLE|rm -rf|eval\()", content, re.I):
            return False, f"内容含危险片段：{path}", []
        cleaned.append({"path": path, "content": content})
    if not cleaned:
        return False, "模型未产生有效改动", []
    if len(cleaned) > _MAX_FILES:
        return False, "改动文件过多", []
    return True, "", cleaned


def try_patch_channel(
    *,
    data_dir,
    repo: str,
    branch: str,
    message: str,
    file_anchors: list[str] | None = None,
    page_hints: list[str] | None = None,
) -> dict[str, Any]:
    """尝试补丁通道。成功：{ok:True, summary, files, commit_urls}；否则 ok:False + error。"""
    repo_n = normalize_repo(repo)
    branch_s = (branch or "").strip() or "main"
    if not eligible_for_patch_channel(message):
        return {"ok": False, "error": "不适用补丁通道", "fallback": True}

    hints = list(page_hints or []) or extract_page_search_hints(message)
    index = get_or_refresh_repo_index(data_dir, repo_n, branch_s)
    matched = match_paths_by_hints(index, hints, limit=6)
    anchors = merge_file_anchors(file_anchors, matched)[:_MAX_FILES]
    if not anchors:
        return {"ok": False, "error": "无可用文件锚点", "fallback": True}

    fetched: list[dict[str, Any]] = []
    original_map: dict[str, str] = {}
    sha_map: dict[str, str] = {}
    for path in anchors:
        item = _fetch_file(repo_n, path, branch_s)
        if not item:
            continue
        fetched.append(item)
        original_map[path] = item["content"]
        sha_map[path] = item["sha"]
        if len(fetched) >= _MAX_FILES:
            break
    if not fetched:
        return {"ok": False, "error": "锚点文件读取失败", "fallback": True}

    llm = _llm_patch(
        requirement=message,
        files=[{"path": f["path"], "content": f["content"]} for f in fetched],
    )
    if not llm.get("ok"):
        return {"ok": False, "error": llm.get("error") or "LLM 失败", "fallback": True}

    ok, err, cleaned = _validate_patch(original_map, llm.get("files") or [])
    if not ok:
        return {"ok": False, "error": err, "fallback": True}

    commit_urls: list[str] = []
    changed_paths: list[str] = []
    for item in cleaned:
        path = item["path"]
        try:
            resp = _put_file(
                repo_n,
                path,
                content=item["content"],
                sha=sha_map[path],
                branch=branch_s,
                message=f"fix(css_layout): patch {path} via WorkBuddy fast channel",
            )
        except urllib.error.HTTPError as exc:
            return {
                "ok": False,
                "error": f"GitHub 写入失败 {path}: HTTP {exc.code}",
                "fallback": True,
            }
        except Exception as exc:  # noqa: BLE001
            return {
                "ok": False,
                "error": f"GitHub 写入失败 {path}: {type(exc).__name__}",
                "fallback": True,
            }
        changed_paths.append(path)
        commit = (resp.get("commit") or {}) if isinstance(resp, dict) else {}
        html = str(commit.get("html_url") or "")
        if html:
            commit_urls.append(html)
        # 刷新 sha 供同批下一文件（通常不同 path）
        content_meta = resp.get("content") if isinstance(resp, dict) else None
        if isinstance(content_meta, dict) and content_meta.get("sha"):
            sha_map[path] = str(content_meta["sha"])

    summary = str(llm.get("summary") or "已通过快速补丁通道完成样式修复")
    summary += (
        f"\n\n【快速补丁通道】未拉起 Cursor Cloud / 未重新 clone。"
        f"已改：{', '.join(changed_paths)}（分支 `{branch_s}`）。"
        "若未达预期，可在同会话继续说明，将回退完整 Cloud 写码。"
    )
    return {
        "ok": True,
        "summary": summary,
        "files": changed_paths,
        "commit_urls": commit_urls,
        "fallback": False,
        "channel": "patch",
    }
