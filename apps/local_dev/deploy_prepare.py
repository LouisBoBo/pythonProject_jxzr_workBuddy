"""P1-3 部署准备：门禁说明与就绪检查。"""
from __future__ import annotations

from typing import Any

from local_dev.deploy_config import (
    DeployConfig,
    default_deploy_env,
    default_deploy_ref,
    env_allowed,
    env_display_label,
    get_deploy_config,
    normalize_env,
)
from local_dev.deploy_github import github_deploy_token


def _guess_env_from_message(message: str, cfg: DeployConfig | None = None) -> str:
    t = (message or "").strip().lower()
    if any(x in t for x in ("生产", "正式", "production", "prod")):
        return "production"
    if any(x in t for x in ("预发", "测试", "staging", "stage")):
        return "staging"
    return default_deploy_env(cfg)


def prepare_deploy(
    *,
    message: str = "",
    env: str | None = None,
    ref: str | None = None,
    cfg: DeployConfig | None = None,
) -> dict[str, Any]:
    """汇总部署意图门禁结果；本函数不触发 CI / SSH。

    Happy：开关开且对应提供方配置齐 → ready_for_confirm
    边界：开关关 / 环境不在白名单 / 提供方未配齐
    失败：只返回结构化结果
    """
    c = cfg or get_deploy_config()
    target_env = normalize_env(env) or _guess_env_from_message(message, c)
    target_ref = (ref or "").strip() or default_deploy_ref()
    is_local_ssh = c.ci_provider == "local_ssh"

    base: dict[str, Any] = {
        "ok": True,
        "runtime": "deploy",
        "enabled": bool(c.enabled),
        "env": target_env,
        "env_label": env_display_label(target_env),
        "ref": target_ref,
        "suggested_ref": target_ref,
        "env_whitelist": list(c.env_whitelist),
        "allow_production": bool(c.allow_production),
        "ci_provider": c.ci_provider,
        "github_workflow": c.github_workflow,
        "github_repo": c.github_repo,
        "require_pushed_ref": bool(c.require_pushed_ref),
        "has_github_token": bool(github_deploy_token()),
        "can_trigger_ci": False,
        "ready_for_confirm": False,
        "blocking_reasons": [],
        "checks": [],
        "summary": "",
        "next_hint": "",
        "poll_timeout_sec": int(c.poll_timeout_sec),
        "ssh_host": c.ssh_host if is_local_ssh else "",
        "local_project_path": c.local_project_path if is_local_ssh else "",
        "health_url": (c.health_url or "").strip(),
        "visit_url": (c.health_url or "").strip(),
    }

    checks: list[dict[str, Any]] = []
    blockers: list[str] = []

    if not c.enabled:
        blockers.append("DEPLOY_ENABLED 未开启（默认关闭，避免误触发发布）")
        checks.append({"id": "enabled", "ok": False, "detail": "总开关关闭"})
    else:
        checks.append({"id": "enabled", "ok": True, "detail": "总开关已开"})

    if env_allowed(target_env, c):
        checks.append({"id": "env", "ok": True, "detail": f"环境「{target_env}」在白名单内"})
    else:
        blockers.append(
            f"环境「{target_env}」不在白名单 {list(c.env_whitelist)}"
            + ("（生产默认禁止）" if target_env in ("production", "prod") else "")
        )
        checks.append({"id": "env", "ok": False, "detail": "环境未授权"})

    if is_local_ssh:
        from local_dev.deploy_local_ssh import local_ssh_settings, validate_local_ssh_settings

        ssh = local_ssh_settings(c)
        base["ssh_host"] = ssh.get("host") or ""
        base["local_project_path"] = ssh.get("local_project") or ""
        ssh_errs = validate_local_ssh_settings(ssh, c)
        if not ssh_errs:
            checks.append(
                {
                    "id": "ci",
                    "ok": True,
                    "detail": (
                        f"本机 SSH：{ssh['user']}@{ssh['host']}:{ssh['app_path']} "
                        f"← {ssh['local_project']}"
                    ),
                }
            )
            checks.append({"id": "token", "ok": True, "detail": "本机私钥路径已配置（不经 GitHub）"})
            provider_ready = True
            can_auth = True
        else:
            for e in ssh_errs:
                blockers.append(e)
            checks.append(
                {
                    "id": "ci",
                    "ok": False,
                    "detail": "本机 SSH 配置不完整：" + "；".join(ssh_errs[:3]),
                }
            )
            checks.append({"id": "token", "ok": False, "detail": "本机 SSH 未就绪"})
            provider_ready = False
            can_auth = False
        # local_ssh 不依赖 GitHub 仓库/Token；保留字段供 UI 可选展示
    else:
        workflow_ok = bool(c.github_workflow) and c.ci_provider == "github_actions"
        if workflow_ok:
            checks.append(
                {
                    "id": "ci",
                    "ok": True,
                    "detail": f"将使用 GitHub Actions：{c.github_workflow}",
                }
            )
        else:
            blockers.append(
                "尚未配置 DEPLOY_GITHUB_WORKFLOW（或 CI 提供方不是 github_actions）"
            )
            checks.append({"id": "ci", "ok": False, "detail": "CI workflow 未配置"})

        repo_ok = bool(c.github_repo)
        if repo_ok:
            checks.append({"id": "repo", "ok": True, "detail": f"仓库：{c.github_repo}"})
        else:
            blockers.append("尚未配置 DEPLOY_GITHUB_REPO（owner/name）")
            checks.append({"id": "repo", "ok": False, "detail": "仓库未配置"})

        token_ok = bool(github_deploy_token())
        if token_ok:
            checks.append({"id": "token", "ok": True, "detail": "已配置 GitHub Token（服务端）"})
        else:
            blockers.append("未配置 DEPLOY_GITHUB_TOKEN / GITHUB_TOKEN")
            checks.append({"id": "token", "ok": False, "detail": "缺少 Token"})

        provider_ready = workflow_ok and repo_ok
        can_auth = token_ok

    if target_ref:
        checks.append({"id": "ref", "ok": True, "detail": f"将使用 ref：{target_ref}"})
    else:
        checks.append(
            {
                "id": "ref",
                "ok": False,
                "detail": "未指定 ref（确认卡可填；或设 DEPLOY_DEFAULT_REF / LOCAL_DEV_WORK_BRANCH）",
                "warning": True,
            }
        )

    ready = bool(c.enabled) and env_allowed(target_env, c) and provider_ready
    can_trigger = ready and can_auth
    base["checks"] = checks
    base["blocking_reasons"] = blockers
    base["ready_for_confirm"] = ready
    base["can_trigger_ci"] = can_trigger

    if not c.enabled:
        base["summary"] = "自动化部署已识别，但当前未开启（安全默认）。"
        base["next_hint"] = (
            "请到「系统配置 → 自动化部署」打开开关，并按提供方填写配置"
            "（GitHub Actions 或本机 SSH）。"
        )
    elif not ready:
        base["summary"] = "部署请求已识别，但配置未就绪，不会弹出可确认发版卡。"
        base["next_hint"] = "；".join(blockers) if blockers else "请检查部署配置"
    elif is_local_ssh:
        env_label = env_display_label(target_env)
        base["summary"] = (
            f"配置已就绪：请确认环境与 ref 后由本机 SSH 同步到{env_label}"
            "（不经 GitHub Actions）。"
        )
        base["next_hint"] = "点确认后 API 在本机构建并 rsync，不经模型。"
    elif not can_auth:
        base["summary"] = "仓库与 workflow 已配，但缺少 GitHub Token，确认后仍无法触发。"
        base["next_hint"] = "配置 DEPLOY_GITHUB_TOKEN 或 GITHUB_TOKEN 后重试"
    else:
        env_label = env_display_label(target_env)
        base["summary"] = (
            f"配置已就绪：请确认环境与 ref 后触发 GitHub Actions（目标环境：{env_label}）。"
        )
        base["next_hint"] = "点确认后由 API 直执 workflow_dispatch，不经模型。"

    return base
