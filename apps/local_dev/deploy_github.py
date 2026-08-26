"""P1-3：触发 GitHub Actions workflow_dispatch（仅服务端，不进 Prompt）。"""
from __future__ import annotations

import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Callable

_APPS = Path(__file__).resolve().parents[1]
_AGENT = _APPS / "agent"
if str(_AGENT) not in sys.path:
    sys.path.insert(0, str(_AGENT))

from safe_http import assert_http_url_allowed  # noqa: E402

_REPO_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
_REF_RE = re.compile(r"^[A-Za-z0-9._/\-]+$")
_WORKFLOW_RE = re.compile(r"^[A-Za-z0-9._\-]+\.ya?ml$", re.I)


def github_deploy_token() -> str:
    """优先系统配置 DEPLOY_GITHUB_TOKEN，再回落其它 GitHub Token 环境变量。"""
    try:
        from settings_store import resolve_setting

        tok = (resolve_setting("DEPLOY_GITHUB_TOKEN", "") or "").strip()
        if tok:
            return tok
    except Exception:
        pass
    for name in ("DEPLOY_GITHUB_TOKEN", "CURSOR_DEV_GITHUB_TOKEN", "GITHUB_TOKEN", "GH_TOKEN"):
        raw = (os.getenv(name) or "").strip()
        if raw:
            return raw
    return ""


def parse_github_repo(raw: str) -> tuple[str, str] | None:
    s = (raw or "").strip().removesuffix(".git")
    if s.startswith("https://github.com/"):
        s = s[len("https://github.com/") :]
    elif s.startswith("git@github.com:"):
        s = s[len("git@github.com:") :]
    s = s.strip("/")
    if not _REPO_RE.match(s):
        return None
    owner, name = s.split("/", 1)
    if ".." in owner or ".." in name or not owner or not name:
        return None
    return owner, name


def _request_json(
    url: str,
    *,
    method: str = "GET",
    body: dict[str, Any] | None = None,
    timeout: float = 30.0,
) -> tuple[int, dict[str, Any] | list[Any] | None]:
    assert_http_url_allowed(url, what="GitHub API")
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "zr-workbuddy-deploy",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    token = github_deploy_token()
    if not token:
        raise RuntimeError("未配置 DEPLOY_GITHUB_TOKEN / GITHUB_TOKEN，无法触发 Actions")
    headers["Authorization"] = f"Bearer {token}"
    data = None
    if body is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            code = int(getattr(resp, "status", None) or resp.getcode() or 0)
            raw = resp.read().decode("utf-8")
            if not raw.strip():
                return code, None
            return code, json.loads(raw)
    except urllib.error.HTTPError as e:
        err_body = ""
        try:
            err_body = e.read().decode("utf-8", errors="replace")[:500]
        except Exception:
            pass
        raise RuntimeError(f"GitHub API HTTP {e.code}: {err_body or e.reason}") from e


def trigger_workflow_dispatch(
    *,
    repo: str,
    workflow: str,
    ref: str,
    environment: str = "",
    workflow_env_input: str = "",
    request_json: Callable[..., tuple[int, Any]] | None = None,
) -> dict[str, Any]:
    """触发 workflow_dispatch。Happy：204；失败返回 ok=False（不抛给路由层以外）。

    request_json 可注入，便于单测不碰真网。
    """
    parsed = parse_github_repo(repo)
    if not parsed:
        return {"ok": False, "error": f"非法仓库名：{repo!r}（期望 owner/name）"}
    owner, name = parsed
    wf = (workflow or "").strip()
    if not _WORKFLOW_RE.match(wf):
        return {"ok": False, "error": f"非法 workflow 文件名：{wf!r}"}
    branch = (ref or "").strip()
    if not branch or not _REF_RE.match(branch):
        return {"ok": False, "error": "ref 无效（须为已推送的 branch/tag/commit 短名）"}
    env = (environment or "").strip().lower()
    if not env:
        try:
            from local_dev.deploy_config import default_deploy_env

            env = default_deploy_env()
        except Exception:
            env = "staging"

    api = (
        f"https://api.github.com/repos/{owner}/{name}/actions/workflows/"
        f"{urllib.parse.quote(wf)}/dispatches"
    )
    env_input_key = (workflow_env_input or "").strip()
    if not env_input_key:
        try:
            from local_dev.deploy_config import get_deploy_config

            env_input_key = (get_deploy_config().github_workflow_env_input or "environment").strip()
        except Exception:
            env_input_key = "environment"
    skip_env_input = env_input_key.lower() in ("none", "-", "off", "0")
    payload: dict[str, Any] = {"ref": branch}
    if not skip_env_input:
        payload["inputs"] = {env_input_key: env}
    do_req = request_json or _request_json
    try:
        code, _ = do_req(api, method="POST", body=payload)
    except Exception as e:  # noqa: BLE001
        # 部分 workflow 无 inputs 会 422；降级为无 inputs 再试一次
        msg = str(e)
        if "422" in msg or "Input" in msg or "inputs" in msg.lower():
            try:
                code, _ = do_req(api, method="POST", body={"ref": branch})
            except Exception as e2:  # noqa: BLE001
                return {"ok": False, "error": str(e2)[:400]}
        else:
            return {"ok": False, "error": msg[:400]}

    if code not in (204, 200):
        return {"ok": False, "error": f"触发失败，HTTP {code}"}

    actions_url = f"https://github.com/{owner}/{name}/actions"
    run_url = ""
    run_id = ""
    run_status = ""
    # 尽力取最近一次 run（可能有竞态，失败不阻断）
    try:
        time.sleep(0.8)
        runs_api = (
            f"https://api.github.com/repos/{owner}/{name}/actions/workflows/"
            f"{urllib.parse.quote(wf)}/runs?event=workflow_dispatch&per_page=1"
        )
        _, runs = do_req(runs_api, method="GET")
        if isinstance(runs, dict):
            items = runs.get("workflow_runs") or []
            if items and isinstance(items[0], dict):
                item = items[0]
                run_url = str(item.get("html_url") or "")
                run_id = str(item.get("id") or "")
                run_status = str(item.get("status") or "")
    except Exception:
        run_url = ""
        run_id = ""
        run_status = ""

    return {
        "ok": True,
        "provider": "github_actions",
        "repo": f"{owner}/{name}",
        "workflow": wf,
        "ref": branch,
        "environment": env,
        "run_id": run_id,
        "run_status": run_status,
        "run_url": run_url,
        "actions_url": actions_url,
        "message": "已触发 GitHub Actions workflow_dispatch",
    }


_TERMINAL = frozenset({"completed", "cancelled", "failure", "timed_out", "action_required", "stale", "skipped"})


def get_workflow_run_status(
    *,
    repo: str,
    run_id: str,
    request_json: Callable[..., tuple[int, Any]] | None = None,
) -> dict[str, Any]:
    """查询单次 Actions run 状态（P1-3c）。可注入 request_json，不依赖打开网页。"""
    parsed = parse_github_repo(repo)
    if not parsed:
        return {"ok": False, "error": f"非法仓库名：{repo!r}"}
    rid = str(run_id or "").strip()
    if not rid.isdigit():
        return {"ok": False, "error": "run_id 无效"}
    owner, name = parsed
    api = f"https://api.github.com/repos/{owner}/{name}/actions/runs/{rid}"
    do_req = request_json or _request_json
    try:
        code, data = do_req(api, method="GET")
    except Exception as e:  # noqa: BLE001
        return {
            "ok": False,
            "error": str(e)[:400],
            "unreachable": True,
            "message": "暂时无法查询 GitHub（网络或服务不可达），可稍后重试",
        }
    if code != 200 or not isinstance(data, dict):
        return {"ok": False, "error": f"查询失败 HTTP {code}"}

    status = str(data.get("status") or "")
    conclusion = str(data.get("conclusion") or "") or None
    html = str(data.get("html_url") or "")
    done = status == "completed" or status in _TERMINAL
    success = bool(done and conclusion == "success")
    failed = bool(done and conclusion and conclusion != "success")
    return {
        "ok": True,
        "provider": "github_actions",
        "repo": f"{owner}/{name}",
        "run_id": rid,
        "status": status,
        "conclusion": conclusion,
        "run_url": html,
        "done": done,
        "success": success,
        "failed": failed,
        "message": _status_message(status, conclusion, done, success),
    }


def find_latest_workflow_run(
    *,
    repo: str,
    workflow: str,
    ref: str = "",
    request_json: Callable[..., tuple[int, Any]] | None = None,
) -> dict[str, Any]:
    """无 run_id 时按 workflow 取最近一次 workflow_dispatch run。"""
    parsed = parse_github_repo(repo)
    if not parsed:
        return {"ok": False, "error": f"非法仓库名：{repo!r}"}
    wf = (workflow or "").strip()
    if not _WORKFLOW_RE.match(wf):
        return {"ok": False, "error": f"非法 workflow 文件名：{wf!r}"}
    owner, name = parsed
    api = (
        f"https://api.github.com/repos/{owner}/{name}/actions/workflows/"
        f"{urllib.parse.quote(wf)}/runs?event=workflow_dispatch&per_page=5"
    )
    do_req = request_json or _request_json
    try:
        code, data = do_req(api, method="GET")
    except Exception as e:  # noqa: BLE001
        return {
            "ok": False,
            "error": str(e)[:400],
            "unreachable": True,
            "message": "暂时无法查询 GitHub（网络或服务不可达），可稍后重试",
        }
    if code != 200 or not isinstance(data, dict):
        return {"ok": False, "error": f"查询失败 HTTP {code}"}
    want_ref = (ref or "").strip()
    items = data.get("workflow_runs") or []
    pick = None
    for item in items:
        if not isinstance(item, dict):
            continue
        head = str(item.get("head_branch") or "")
        if want_ref and head and head != want_ref:
            continue
        pick = item
        break
    if not pick:
        if want_ref:
            return {
                "ok": False,
                "error": f"尚未找到 ref={want_ref!r} 的 workflow run（可能仍在排队）",
            }
        return {"ok": False, "error": "尚未找到对应的 workflow run（可能仍在排队）"}
    rid = str(pick.get("id") or "")
    return get_workflow_run_status(repo=f"{owner}/{name}", run_id=rid, request_json=do_req)


def _status_message(status: str, conclusion: str | None, done: bool, success: bool) -> str:
    if not done:
        mapping = {
            "queued": "已排队，等待执行…",
            "in_progress": "流水线执行中…",
            "waiting": "等待审批/环境…",
            "requested": "已请求…",
            "pending": "等待中…",
        }
        return mapping.get(status, f"状态：{status or '未知'}")
    if success:
        return "部署流水线已成功结束"
    return f"流水线已结束：{conclusion or status or '失败'}"
