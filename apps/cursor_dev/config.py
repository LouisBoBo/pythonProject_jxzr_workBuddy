"""Cursor 写码车道配置（环境变量 + 界面 settings 覆盖）。不依赖 Deep Agents。"""
from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

try:
    from dotenv import load_dotenv

    _REPO_ROOT = Path(__file__).resolve().parents[2]
    load_dotenv(_REPO_ROOT / ".env")
except ImportError:
    _REPO_ROOT = Path(__file__).resolve().parents[2]

from .allowlist import parse_allowlist

# 复用 agent settings_store（apps/agent 加入 path）
_AGENT_DIR = Path(__file__).resolve().parents[1] / "agent"
if str(_AGENT_DIR) not in sys.path:
    sys.path.insert(0, str(_AGENT_DIR))


def _resolve(name: str, default: str = "") -> str:
    try:
        from settings_store import resolve_setting

        return resolve_setting(name, default=default)
    except Exception:
        raw = os.getenv(name)
        if raw is None or str(raw).strip() == "":
            return default
        return str(raw).strip()


def _env_bool(name: str, default: bool = False) -> bool:
    raw = _resolve(name, "")
    if raw is None or str(raw).strip() == "":
        return default
    return str(raw).strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    raw = _resolve(name, "")
    if raw is None or str(raw).strip() == "":
        return default
    try:
        return int(str(raw).strip())
    except ValueError:
        return default

def _sdk_importable() -> tuple[bool, str]:
    try:
        import cursor_sdk  # noqa: F401

        return True, ""
    except ImportError:
        return False, "未安装 cursor-sdk（pip install cursor-sdk）"
    except Exception as exc:  # noqa: BLE001 — 隔离失败域
        return False, f"cursor-sdk 不可用: {exc}"


@dataclass(frozen=True)
class CursorDevConfig:
    enabled: bool
    api_key: str
    repo_allowlist: list[str]
    allowed_users: list[str]  # 空 = 不限制（仍须登录）
    max_concurrent: int
    max_concurrent_per_user: int
    job_timeout_sec: int
    model: str
    auto_pr: bool
    skip_reviewer_request: bool
    branch_prefix: str
    starting_ref: str
    work_branch: str  # 可选：整机固定工作分支（如 hebo），覆盖按用户命名
    sdk_ok: bool
    sdk_reason: str

    def availability(self) -> tuple[bool, str]:
        """写码车道是否可接任务。熔断/缺配置时 available=false，主服务仍可用。

        仓库白名单可选：为空表示不限制（用户在对话里自填）；非空时执行层再校验。
        """
        if not self.enabled:
            return False, "CURSOR_DEV_ENABLED 未开启"
        if not self.api_key:
            return False, "未配置 CURSOR_API_KEY"
        if not self.sdk_ok:
            return False, self.sdk_reason or "cursor-sdk 不可用"
        return True, ""


@lru_cache(maxsize=1)
def get_config() -> CursorDevConfig:
    # 用户白名单仍仅环境变量（P0 不开放 UI）
    users_raw = os.getenv("CURSOR_DEV_ALLOWED_USERS", "") or ""
    allowed_users = [u.strip() for u in users_raw.split(",") if u.strip()]
    sdk_ok, sdk_reason = _sdk_importable()
    return CursorDevConfig(
        enabled=_env_bool("CURSOR_DEV_ENABLED", False),
        api_key=_resolve("CURSOR_API_KEY", ""),
        repo_allowlist=parse_allowlist(_resolve("CURSOR_DEV_REPO_ALLOWLIST", "")),
        allowed_users=allowed_users,
        max_concurrent=max(1, _env_int("CURSOR_DEV_MAX_CONCURRENT", 3)),
        max_concurrent_per_user=max(1, _env_int("CURSOR_DEV_MAX_CONCURRENT_PER_USER", 1)),
        job_timeout_sec=max(60, _env_int("CURSOR_DEV_JOB_TIMEOUT_SEC", 2700)),
        model=(_resolve("CURSOR_DEV_MODEL", "") or "composer-2.5").strip(),
        auto_pr=_env_bool("CURSOR_DEV_AUTO_PR", False),
        skip_reviewer_request=_env_bool("CURSOR_DEV_SKIP_REVIEWER_REQUEST", True),
        branch_prefix=(_resolve("CURSOR_DEV_BRANCH_PREFIX", "") or "dev/wb/").strip()
        or "dev/wb/",
        starting_ref=_resolve("CURSOR_DEV_STARTING_REF", ""),
        work_branch=_resolve("CURSOR_DEV_WORK_BRANCH", ""),
        sdk_ok=sdk_ok,
        sdk_reason=sdk_reason,
    )


def reload_config() -> CursorDevConfig:
    """测试或热更新环境变量 / 界面配置后调用。"""
    try:
        from dotenv import load_dotenv

        load_dotenv(_REPO_ROOT / ".env", override=True)
    except Exception:
        pass
    try:
        from settings_store import invalidate_cache

        invalidate_cache()
    except Exception:
        pass
    get_config.cache_clear()
    return get_config()


def user_allowed(username: str | None, user_id: int | str | None = None) -> bool:
    cfg = get_config()
    if not cfg.allowed_users:
        return True
    candidates = []
    if username:
        candidates.append(str(username).strip())
    if user_id is not None and str(user_id).strip() != "":
        candidates.append(str(user_id).strip())
    allow = {u.lower() for u in cfg.allowed_users}
    return any(c.lower() in allow for c in candidates if c)
