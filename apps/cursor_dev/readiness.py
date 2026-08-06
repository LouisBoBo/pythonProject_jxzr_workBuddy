"""写码车道上线就绪检查：管理员上线前用；同事无需配置。"""
from __future__ import annotations

from typing import Any

from .config import CursorDevConfig, reload_config
from .github_preflight import _github_token, resolve_starting_ref


def _check(ok: bool, id_: str, title: str, detail: str = "") -> dict[str, Any]:
    return {
        "id": id_,
        "ok": bool(ok),
        "title": title,
        "detail": (detail or "").strip(),
        "admin_only": True,
    }


def build_readiness(cfg: CursorDevConfig | None = None) -> dict[str, Any]:
    """返回 {ready, summary, checks[]}。ready=全部硬性检查通过。"""
    cfg = cfg or reload_config()
    checks: list[dict[str, Any]] = []

    checks.append(
        _check(
            cfg.enabled,
            "enabled",
            "CURSOR_DEV_ENABLED 已开启",
            "" if cfg.enabled else "请在服务端 .env 设置 CURSOR_DEV_ENABLED=1",
        )
    )
    checks.append(
        _check(
            bool(cfg.api_key),
            "api_key",
            "已配置服务端 CURSOR_API_KEY（Team Key）",
            ""
            if cfg.api_key
            else "请配置 Team/Service Account Key；同事不要各自申请个人 Key",
        )
    )
    checks.append(
        _check(
            cfg.sdk_ok,
            "sdk",
            "cursor-sdk 可导入",
            cfg.sdk_reason or "",
        )
    )

    allow = list(cfg.repo_allowlist or [])
    checks.append(
        _check(
            bool(allow),
            "allowlist",
            "已配置仓库白名单（生产建议）",
            f"共 {len(allow)} 个仓"
            if allow
            else "CURSOR_DEV_REPO_ALLOWLIST 为空：任意仓可填，生产风险更高",
        )
    )

    # 对白名单仓做 GitHub 预检（无私有 Token 时私有仓可能 404）
    authed = bool(_github_token())
    checks.append(
        _check(
            True,
            "github_token",
            "GitHub Token（私有仓预检，可选）",
            "已配置" if authed else "未配置：仅能可靠预检公开仓；私有仓请设 CURSOR_DEV_GITHUB_TOKEN 或 GITHUB_TOKEN",
        )
    )

    repo_ok_all = True
    if allow:
        for repo in allow[:8]:
            pre = resolve_starting_ref(repo, cfg.starting_ref or None)
            ok = bool(pre.get("ok"))
            if not ok:
                repo_ok_all = False
            detail = ""
            if ok:
                ref = pre.get("ref") or ""
                sha = (pre.get("sha") or "")[:7]
                detail = f"{repo}@{ref}" + (f" ({sha})" if sha else "")
            else:
                detail = f"{repo}: {pre.get('error') or '预检失败'}"
            checks.append(
                _check(
                    ok,
                    f"github:{repo}",
                    f"GitHub 可读且非空：{repo}",
                    detail,
                )
            )
    else:
        checks.append(
            _check(
                True,
                "github:skip",
                "跳过 GitHub 仓预检（无白名单）",
                "上线前请至少配置一个试点仓并确认非空",
            )
        )

    # 人工项：Cursor Integrations / Cloud Agents（无法用 Key 静默证明，仅提示）
    checks.append(
        {
            "id": "cursor_github_integration",
            "ok": True,
            "title": "【人工确认】Cursor Team 已连接 GitHub App（org 级）",
            "detail": "https://cursor.com/dashboard/integrations → GitHub Connect/Reconnect",
            "admin_only": True,
            "manual": True,
        }
    )
    checks.append(
        {
            "id": "cursor_cloud_agents",
            "ok": True,
            "title": "【人工确认】Cloud Agents 已 Set Up",
            "detail": "https://cursor.com/agents",
            "admin_only": True,
            "manual": True,
        }
    )

    hard = [c for c in checks if not c.get("manual")]
    # allowlist 空在本地可接受：不阻塞 ready，但生产应配置
    blocking_ids = {"enabled", "api_key", "sdk"}
    blocking_ok = all(c["ok"] for c in hard if c["id"] in blocking_ids)
    # 有白名单时要求至少一个仓预检通过
    if allow:
        gh_checks = [c for c in hard if str(c["id"]).startswith("github:")]
        repo_gate = any(c["ok"] for c in gh_checks) if gh_checks else False
    else:
        repo_gate = True

    ready = blocking_ok and repo_gate and cfg.availability()[0]
    if ready and allow and not repo_ok_all:
        summary = "核心可用，但部分白名单仓 GitHub 预检失败（私有仓或权限问题请管理员复查）"
    elif ready:
        summary = "服务端配置就绪；请确认人工项（GitHub App / Cloud Agents）后对同事开放"
    else:
        failed = [c["title"] for c in hard if not c["ok"] and c["id"] in blocking_ids]
        if allow and not repo_gate:
            failed.append("白名单仓 GitHub 预检均未通过")
        summary = "未就绪：" + "；".join(failed or ["见 checks"])

    return {
        "ready": ready,
        "summary": summary,
        "colleague_zero_config": True,
        "checks": checks,
    }
