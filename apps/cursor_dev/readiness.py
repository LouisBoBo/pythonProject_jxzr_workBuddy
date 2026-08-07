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

    work_branch = (cfg.work_branch or "").strip()
    starting_ref = (cfg.starting_ref or "").strip()
    branch_prefix = (cfg.branch_prefix or "").strip() or "dev/wb/"
    if work_branch:
        wb_detail = (
            f"CURSOR_DEV_WORK_BRANCH={work_branch}（全员固定工作分支，覆盖按用户命名）；"
            f"STARTING_REF={starting_ref or '(仓默认)'}；"
            f"AUTO_PR={int(bool(cfg.auto_pr))}"
        )
        if starting_ref and starting_ref != work_branch:
            wb_detail += (
                f"；注意 STARTING_REF({starting_ref}) 与 WORK_BRANCH({work_branch}) 不一致，"
                "Cloud 起点与落盘分支可能不同"
            )
        checks.append(
            _check(
                True,
                "work_branch",
                f"固定工作分支：{work_branch}",
                wb_detail,
            )
        )
    else:
        checks.append(
            _check(
                True,
                "work_branch",
                "按用户命名工作分支",
                f"未设 CURSOR_DEV_WORK_BRANCH；将用前缀 {branch_prefix}<username>；"
                f"STARTING_REF={starting_ref or '(仓默认)'}；AUTO_PR={int(bool(cfg.auto_pr))}",
            )
        )

    checks.append(
        _check(
            True,
            "auto_pr",
            "默认不开 PR（推荐）" if not cfg.auto_pr else "AUTO_PR 已开启",
            (
                "CURSOR_DEV_AUTO_PR=0：写码只推工作分支，合入由对话内「合入 main」指引完成"
                if not cfg.auto_pr
                else "CURSOR_DEV_AUTO_PR=1：任务结束可能自动开 PR；试点固定分支场景建议改回 0"
            ),
        )
    )

    # Token：私有仓预检 + 误开 PR 自动关闭；不阻塞 ready，但强烈建议配置
    authed = bool(_github_token())
    checks.append(
        _check(
            True,
            "github_token",
            "GitHub Token（强烈建议）" if authed else "GitHub Token 未配置（建议补）",
            (
                "已配置：可用于私有仓预检、误开 PR 自动关闭"
                if authed
                else (
                    "未配置 CURSOR_DEV_GITHUB_TOKEN / GITHUB_TOKEN："
                    "公开仓仍可写码，但私有仓预检与误开 PR 清理不可靠"
                )
            ),
        )
    )

    # 预检用起点：固定工作分支优先，否则 STARTING_REF / 仓默认
    preflight_ref = work_branch or starting_ref or None
    repo_ok_all = True
    if allow:
        for repo in allow[:8]:
            pre = resolve_starting_ref(repo, preflight_ref)
            ok = bool(pre.get("ok"))
            if not ok:
                repo_ok_all = False
            detail = ""
            if ok:
                ref = pre.get("ref") or ""
                sha = (pre.get("sha") or "")[:7]
                detail = f"{repo}@{ref}" + (f" ({sha})" if sha else "")
                if work_branch and ref and ref != work_branch:
                    detail += f"；期望工作分支 {work_branch}（当前解析到 {ref}）"
            else:
                detail = f"{repo}: {pre.get('error') or '预检失败'}"
                if work_branch and not authed:
                    detail += "（若为私有仓，请先配置 GITHUB_TOKEN）"
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
    elif ready and not authed:
        summary = (
            "服务端配置就绪（建议补 GITHUB_TOKEN）；"
            "请确认人工项（GitHub App / Cloud Agents）后对同事开放"
        )
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
        "work_branch": work_branch or None,
        "auto_pr": bool(cfg.auto_pr),
        "github_token_configured": authed,
        "checks": checks,
    }
