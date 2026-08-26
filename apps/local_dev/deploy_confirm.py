"""P1-3：确认后触发部署（API 直执，不经模型）。"""
from __future__ import annotations

import re
import threading
import time
from typing import Any

from local_dev.deploy_config import DeployConfig, env_allowed, get_deploy_config, normalize_env
from local_dev.deploy_github import github_deploy_token, trigger_workflow_dispatch
from local_dev.deploy_prepare import prepare_deploy

# 进程内短窗去重，防双击（不持久化；重启后清空可接受）
_RECENT: dict[str, float] = {}
_RECENT_LOCK = threading.Lock()
_IDEMPOTENT_SEC = 90.0


def _default_ref(explicit: str | None = None) -> str:
    from local_dev.deploy_config import default_deploy_ref

    if (explicit or "").strip():
        return str(explicit).strip()
    return default_deploy_ref()


def _idem_key(user_id: Any, env: str, ref: str, provider_key: str) -> str:
    return f"{user_id or '-'}|{env}|{ref}|{provider_key}"


def confirm_deploy(
    *,
    decision: str,
    message: str = "",
    env: str | None = None,
    ref: str | None = None,
    user_id: Any = None,
    cfg: DeployConfig | None = None,
    trigger_fn=None,
) -> dict[str, Any]:
    """cancel → 仅记录；confirm → 复检门禁后触发 CI 或本机 SSH。

    Happy：confirm + 门禁过 → 对应执行器
    边界：cancel / 未开启 / 环境非法 / 配置缺失 / 无 ref
    失败：执行器报错 → ok=False；github 路径不改本地 git；local_ssh 用临时 worktree
    """
    d = (decision or "").strip().lower()
    if d in ("cancel", "skip", "cancelled", "canceled"):
        return {
            "ok": True,
            "status": "cancelled",
            "runtime": "deploy",
            "summary": "已取消部署，未触发发布",
        }
    if d not in ("confirm", "deploy", "ok"):
        return {"ok": False, "error": "decision 须为 confirm 或 cancel", "runtime": "deploy"}

    c = cfg or get_deploy_config()
    is_local_ssh = c.ci_provider == "local_ssh"
    target_env = normalize_env(env) or normalize_env(
        prepare_deploy(message=message, env=env, ref=ref, cfg=c).get("env")
    )
    target_ref = _default_ref(ref)

    gate = prepare_deploy(message=message, env=target_env, ref=target_ref, cfg=c)
    if not c.enabled:
        return {"ok": False, "error": "DEPLOY_ENABLED 未开启", "runtime": "deploy", "gate": gate}
    if not env_allowed(target_env, c):
        return {
            "ok": False,
            "error": f"环境「{target_env}」不在白名单",
            "runtime": "deploy",
            "gate": gate,
        }
    if not gate.get("ready_for_confirm"):
        reasons = gate.get("blocking_reasons") or ["配置未就绪"]
        return {
            "ok": False,
            "error": "；".join(str(x) for x in reasons),
            "runtime": "deploy",
            "gate": gate,
        }
    if not target_ref:
        return {
            "ok": False,
            "error": "缺少 git ref：请填写分支/tag，或配置 DEPLOY_DEFAULT_REF / LOCAL_DEV_WORK_BRANCH",
            "runtime": "deploy",
            "gate": gate,
        }
    # 拒绝路径穿越式 ref（local_ssh / github 共用）
    if ".." in target_ref or not re.match(r"^[A-Za-z0-9._/\-]+$", target_ref):
        return {
            "ok": False,
            "error": "非法 git ref",
            "runtime": "deploy",
            "gate": gate,
        }

    if is_local_ssh:
        provider_key = f"local_ssh|{c.ssh_host}|{c.ssh_app_path}"
        if trigger_fn is None:
            from local_dev.deploy_local_ssh import trigger_local_ssh_deploy

            fn = trigger_local_ssh_deploy
        else:
            fn = trigger_fn
    else:
        if not github_deploy_token():
            return {
                "ok": False,
                "error": "未配置 DEPLOY_GITHUB_TOKEN / GITHUB_TOKEN",
                "runtime": "deploy",
                "gate": gate,
            }
        if not c.github_repo:
            return {
                "ok": False,
                "error": "未配置 DEPLOY_GITHUB_REPO（owner/name）",
                "runtime": "deploy",
                "gate": gate,
            }
        provider_key = c.github_workflow or "github_actions"
        fn = trigger_fn or trigger_workflow_dispatch

    key = _idem_key(user_id, target_env, target_ref, provider_key)
    now = time.time()
    with _RECENT_LOCK:
        last = _RECENT.get(key) or 0.0
        if now - last < _IDEMPOTENT_SEC:
            return {
                "ok": False,
                "error": f"短时间内已触发过同环境同 ref（{_IDEMPOTENT_SEC:.0f}s 内勿重复点击）",
                "runtime": "deploy",
                "status": "duplicate",
                "gate": gate,
            }
        # 先占坑再触发，避免并行双击各打一次
        _RECENT[key] = now

    if is_local_ssh:
        result = fn(
            repo=c.github_repo,
            workflow=c.github_workflow,
            ref=target_ref,
            environment=target_env,
            cfg=c,
        )
    else:
        result = fn(
            repo=c.github_repo,
            workflow=c.github_workflow,
            ref=target_ref,
            environment=target_env,
            workflow_env_input=c.github_workflow_env_input,
        )
    if not result.get("ok"):
        # 硬失败允许短窗内重试
        with _RECENT_LOCK:
            _RECENT.pop(key, None)
        return {
            "ok": False,
            "error": result.get("error") or "触发部署失败",
            "runtime": "deploy",
            "status": "failed",
            "gate": gate,
            "ci": result,
        }

    return {
        "ok": True,
        "status": "triggered",
        "runtime": "deploy",
        "env": target_env,
        "ref": target_ref,
        "summary": result.get("message") or "已触发部署",
        "ci": result,
        "gate": gate,
    }
