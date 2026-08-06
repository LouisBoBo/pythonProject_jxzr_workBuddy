"""GitHub 只读预检：解析默认分支 / 分支 tip，避免空仓误入 Cursor。

可选 GITHUB_TOKEN / GH_TOKEN / CURSOR_DEV_GITHUB_TOKEN：私有仓预检。
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from typing import Any


def _github_token() -> str:
    for name in ("CURSOR_DEV_GITHUB_TOKEN", "GITHUB_TOKEN", "GH_TOKEN"):
        raw = (os.getenv(name) or "").strip()
        if raw:
            return raw
    return ""


def _get_json(url: str, timeout: float = 15.0) -> dict[str, Any] | list[Any]:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "workbuddy-cursor-dev",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    token = _github_token()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _read_http_error_body(exc: urllib.error.HTTPError, limit: int = 400) -> str:
    try:
        return exc.read(limit).decode("utf-8", errors="replace")
    except Exception:
        return ""


def _format_http_error(code: int, body: str = "", *, authed: bool = False) -> str:
    b = (body or "").lower()
    if code == 403 and ("rate limit" in b or "rate_limit" in b):
        if authed:
            return (
                "GitHub API 限流（已带 Token 仍 403）。请稍后再试，或换权限更高的 PAT。"
            )
        return (
            "GitHub API 匿名访问已限流（HTTP 403）。"
            "请管理员在服务端配置 CURSOR_DEV_GITHUB_TOKEN 或 GITHUB_TOKEN（classic PAT，repo 只读即可），"
            "预检即可恢复；写码本身仍可由 Cursor Cloud 执行。"
        )
    if code == 403:
        return (
            "GitHub 拒绝访问（HTTP 403）。"
            + (
                "请检查 Token 是否有该仓权限，或是否需开通 SSO。"
                if authed
                else "未配置 Token 时也可能是限流；请配置 CURSOR_DEV_GITHUB_TOKEN / GITHUB_TOKEN。"
            )
        )
    if code == 401:
        return "GitHub Token 无效或过期（HTTP 401）。请检查 GITHUB_TOKEN。"
    return f"查询 GitHub 仓库失败：HTTP {code}"


def resolve_starting_ref(repo: str, preferred: str | None = None) -> dict[str, Any]:
    """返回 {ok, ref, sha, default_branch, error, authenticated, soft}。repo=owner/name。"""
    repo = (repo or "").strip()
    preferred = (preferred or "").strip() or None
    authed = bool(_github_token())
    if not repo or "/" not in repo:
        return {
            "ok": False,
            "error": "仓库格式无效",
            "ref": None,
            "sha": None,
            "default_branch": None,
            "authenticated": authed,
            "soft": False,
        }

    try:
        meta = _get_json(f"https://api.github.com/repos/{repo}")
    except urllib.error.HTTPError as exc:
        body = _read_http_error_body(exc)
        if exc.code == 404:
            hint = (
                f"GitHub 上找不到仓库 {repo}（404）。"
                if authed
                else f"GitHub 上找不到仓库 {repo}（404）。若为私有仓，请配置 GITHUB_TOKEN（或 CURSOR_DEV_GITHUB_TOKEN）供预检。"
            )
            return {
                "ok": False,
                "error": hint,
                "ref": None,
                "sha": None,
                "default_branch": None,
                "authenticated": authed,
                "soft": False,
            }
        err = _format_http_error(exc.code, body, authed=authed)
        # 限流/临时 403：允许上层软失败后继续走 Cursor Cloud
        soft = exc.code in (403, 429) or "rate limit" in body.lower()
        return {
            "ok": False,
            "error": err,
            "ref": preferred,
            "sha": None,
            "default_branch": None,
            "authenticated": authed,
            "soft": soft,
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "ok": False,
            "error": f"查询 GitHub 仓库失败：{type(exc).__name__}: {exc}",
            "ref": preferred,
            "sha": None,
            "default_branch": None,
            "authenticated": authed,
            "soft": True,
        }

    if not isinstance(meta, dict):
        return {
            "ok": False,
            "error": "GitHub 返回异常",
            "ref": None,
            "sha": None,
            "default_branch": None,
            "authenticated": authed,
            "soft": False,
        }

    default_branch = (meta.get("default_branch") or "").strip() or None
    ref = preferred or default_branch
    if not ref:
        return {
            "ok": False,
            "error": (
                f"仓库 {repo} 没有默认分支（通常是空仓、尚无 commit）。"
                "请先在 GitHub 创建 README 并提交。"
            ),
            "ref": None,
            "sha": None,
            "default_branch": None,
            "authenticated": authed,
            "soft": False,
        }

    def _branch_sha(branch: str) -> str | None:
        br = _get_json(f"https://api.github.com/repos/{repo}/branches/{urllib.parse.quote(branch)}")
        if isinstance(br, dict):
            return ((br.get("commit") or {}) or {}).get("sha")
        return None

    sha = None
    try:
        sha = _branch_sha(ref)
    except urllib.error.HTTPError as exc:
        body = _read_http_error_body(exc)
        # 指定工作分支失败时回退默认分支，避免写码整段卡死
        if preferred and default_branch and preferred != default_branch:
            try:
                sha = _branch_sha(default_branch)
                return {
                    "ok": True,
                    "ref": default_branch,
                    "sha": sha,
                    "default_branch": default_branch,
                    "error": (
                        f"分支 {preferred!r} 预检失败（HTTP {exc.code}），已回退默认分支 {default_branch!r}。"
                    ),
                    "authenticated": authed,
                    "soft": False,
                    "fallback_from": preferred,
                }
            except Exception:
                pass
        soft = exc.code in (403, 429) or "rate limit" in body.lower()
        return {
            "ok": False,
            "error": (
                f"无法读取分支 {ref!r}："
                + _format_http_error(exc.code, body, authed=authed)
            ),
            "ref": ref if soft else None,
            "sha": None,
            "default_branch": default_branch,
            "authenticated": authed,
            "soft": soft,
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "ok": True,
            "ref": ref,
            "sha": None,
            "default_branch": default_branch,
            "error": f"分支 tip 查询失败（可忽略）：{exc}",
            "authenticated": authed,
            "soft": False,
        }

    if not sha:
        return {
            "ok": False,
            "error": f"分支 {ref!r} 没有 commit tip。请确认仓库已有提交。",
            "ref": ref,
            "sha": None,
            "default_branch": default_branch,
            "authenticated": authed,
            "soft": False,
        }

    return {
        "ok": True,
        "ref": ref,
        "sha": sha,
        "default_branch": default_branch,
        "error": None,
        "authenticated": authed,
        "soft": False,
    }
