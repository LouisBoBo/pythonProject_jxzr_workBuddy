"""P1-3 部署配置（系统配置优先，.env 兜底；默认全关）。"""
from __future__ import annotations

import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path

_AGENT_DIR = Path(__file__).resolve().parents[1] / "agent"
if str(_AGENT_DIR) not in sys.path:
    sys.path.insert(0, str(_AGENT_DIR))


def _resolve(name: str, default: str = "") -> str:
    """settings.json 非空 → 环境变量 → default（与写码车道一致）。"""
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
    return str(raw).strip().lower() in ("1", "true", "yes", "on")


def _env_csv(name: str, default: str) -> list[str]:
    raw = _resolve(name, default) or default or ""
    raw = str(raw).strip()
    if not raw:
        return []
    return [x.strip().lower() for x in raw.split(",") if x.strip()]


# 相对路径：禁止 ..、绝对路径、空段、shell 元字符
_REL_PATH_RE = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_./\-]*$")
# 构建命令：argv 友好字符；禁止 ;|&`$()<> 等（执行时 shell=False）
_BUILD_CMD_RE = re.compile(r"^[A-Za-z0-9_./\-+=@:\s]+$")
# rsync --exclude 模式：禁止换行与选项注入字符
_EXCLUDE_RE = re.compile(r"^[A-Za-z0-9_.*?\[\]\-./]+$")


def _split_lines_or_csv(raw: str) -> list[str]:
    text = (raw or "").strip()
    if not text:
        return []
    parts: list[str] = []
    for chunk in text.replace("\r", "\n").split("\n"):
        for piece in chunk.split(","):
            item = piece.strip()
            if item:
                parts.append(item)
    return parts


def _safe_rel_path(value: str) -> str | None:
    raw = (value or "").strip()
    if not raw or raw.startswith("/") or raw.startswith("\\"):
        return None
    rel = raw.strip("/")
    if not rel or ".." in rel or "//" in rel:
        return None
    if not _REL_PATH_RE.match(rel):
        return None
    return rel


def _safe_build_cmd(cmd: str) -> str | None:
    text = (cmd or "").strip()
    if not text or len(text) > 240:
        return None
    if not _BUILD_CMD_RE.match(text):
        return None
    # 再挡一层：即使字符集放宽，也不允许空命令拼接痕迹
    if any(tok in text for tok in (";", "|", "&", "`", "$(", "${", "\n", "\r")):
        return None
    # 禁止解释器 -c（任意代码执行）
    try:
        parts = text.split()
    except Exception:
        return None
    lowered = [p.lower() for p in parts]
    shells = {"bash", "sh", "zsh", "dash", "ksh", "fish", "csh", "tcsh", "python", "python3", "node", "perl", "ruby"}
    if parts and parts[0].lower() in shells and "-c" in lowered:
        return None
    if "-c" in lowered:
        # npm 等也不该带裸 -c；避免 python -c / 变体漏网
        return None
    return text


def _parse_sync_pairs(raw: str) -> tuple[tuple[str, str], ...]:
    """DEPLOY_SSH_SYNC_PAIRS：local_rel:remote_rel（相对项目根 / 远端 app 根）。"""
    out: list[tuple[str, str]] = []
    for line in _split_lines_or_csv(raw):
        if ":" not in line:
            continue
        local_raw, remote_raw = line.split(":", 1)
        local_rel = _safe_rel_path(local_raw)
        remote_rel = _safe_rel_path(remote_raw)
        if not local_rel or not remote_rel:
            continue
        out.append((local_rel, remote_rel))
    return tuple(out)


def _parse_build_steps(raw: str) -> tuple[tuple[str, str], ...]:
    """DEPLOY_SSH_BUILD_STEPS：cwd_rel:cmd（cwd 空或 . 表示项目根；cmd 禁 shell 元字符）。"""
    out: list[tuple[str, str]] = []
    for line in _split_lines_or_csv(raw):
        if ":" in line:
            cwd_raw, cmd_raw = line.split(":", 1)
            cwd_tmp = (cwd_raw or ".").strip().strip("/") or "."
            cwd_rel = "." if cwd_tmp == "." else _safe_rel_path(cwd_tmp)
            cmd = _safe_build_cmd(cmd_raw)
        else:
            cwd_rel, cmd = ".", _safe_build_cmd(line)
        if not cwd_rel or not cmd:
            continue
        out.append((cwd_rel, cmd))
    return tuple(out)


def _parse_rsync_excludes(raw: str) -> tuple[str, ...]:
    items: list[str] = []
    for x in _split_lines_or_csv(raw):
        pat = x.strip()
        if not pat or len(pat) > 120:
            continue
        if not _EXCLUDE_RE.match(pat):
            continue
        items.append(pat)
    return tuple(items)


# 未配置 DEPLOY_SSH_* 时的兼容默认（Vite 前端 + Python 后端 monorepo）
DEFAULT_SSH_SYNC_PAIRS: tuple[tuple[str, str], ...] = (
    ("frontend/dist", "frontend/dist"),
    ("backend", "backend"),
)
DEFAULT_SSH_BUILD_STEPS: tuple[tuple[str, str], ...] = (
    ("frontend", "npm ci"),
    ("frontend", "npm run build"),
)
DEFAULT_SSH_RSYNC_EXCLUDES: tuple[str, ...] = (
    "__pycache__",
    ".venv",
    "venv",
    "*.pyc",
    ".pytest_cache",
    ".env",
    ".env.*",
    "*.pem",
    "id_rsa*",
    "id_ed25519*",
    "*.key",
    ".DS_Store",
)


@dataclass(frozen=True)
class DeployConfig:
    """人触发部署确认 → CI / 本机 SSH；默认关闭，避免误伤现有功能。"""

    enabled: bool
    env_whitelist: tuple[str, ...]
    allow_production: bool
    ci_provider: str
    github_workflow: str
    github_repo: str
    require_pushed_ref: bool
    confirm_timeout_sec: int
    poll_timeout_sec: int
    # 仅 ci_provider=local_ssh 使用；github_actions 忽略
    ssh_host: str = ""
    ssh_user: str = ""
    ssh_key_path: str = ""
    ssh_app_path: str = ""
    local_project_path: str = ""
    ssh_restart_cmd: str = ""
    ssh_port: str = "22"
    # P1-3d：部署后探活（可选；空则跳过）
    health_url: str = ""
    health_timeout_sec: int = 20
    health_retries: int = 5
    # 本机 SSH：可覆盖默认 monorepo 布局（空 = 使用 DEFAULT_*）
    ssh_sync_pairs: tuple[tuple[str, str], ...] = ()
    ssh_build_steps: tuple[tuple[str, str], ...] = ()
    ssh_rsync_excludes: tuple[str, ...] = ()
    # GitHub Actions workflow_dispatch 的 environment 输入名；none/- 表示不传
    github_workflow_env_input: str = "environment"


def effective_ssh_sync_pairs(cfg: DeployConfig) -> tuple[tuple[str, str], ...]:
    return cfg.ssh_sync_pairs or DEFAULT_SSH_SYNC_PAIRS


def effective_ssh_build_steps(cfg: DeployConfig) -> tuple[tuple[str, str], ...]:
    if cfg.ssh_build_steps:
        return cfg.ssh_build_steps
    if cfg.ssh_sync_pairs:
        return ()
    return DEFAULT_SSH_BUILD_STEPS


def effective_ssh_rsync_excludes(cfg: DeployConfig) -> tuple[str, ...]:
    return cfg.ssh_rsync_excludes or DEFAULT_SSH_RSYNC_EXCLUDES


def get_deploy_config() -> DeployConfig:
    allow_prod = _env_bool("DEPLOY_ALLOW_PRODUCTION", False)
    whitelist = _env_csv("DEPLOY_ENV_WHITELIST", "staging")
    if not allow_prod:
        whitelist = [e for e in whitelist if e not in ("production", "prod", "正式", "生产")]
    if not whitelist:
        whitelist = ["staging"]
    provider = (_resolve("DEPLOY_CI_PROVIDER", "github_actions") or "github_actions").lower()
    if provider not in ("github_actions", "local_ssh"):
        # 未知提供方回落默认，避免误进未实现执行器
        provider = "github_actions"
    try:
        confirm_sec = max(30, int(_resolve("DEPLOY_CONFIRM_TIMEOUT_SEC", "600") or "600"))
    except ValueError:
        confirm_sec = 600
    try:
        poll_sec = max(60, int(_resolve("DEPLOY_POLL_TIMEOUT_SEC", "1800") or "1800"))
    except ValueError:
        poll_sec = 1800
    try:
        health_timeout = max(3, int(_resolve("DEPLOY_HEALTH_TIMEOUT_SEC", "20") or "20"))
    except ValueError:
        health_timeout = 20
    try:
        health_retries = max(1, min(20, int(_resolve("DEPLOY_HEALTH_RETRIES", "5") or "5")))
    except ValueError:
        health_retries = 5
    return DeployConfig(
        enabled=_env_bool("DEPLOY_ENABLED", False),
        env_whitelist=tuple(whitelist),
        allow_production=allow_prod,
        ci_provider=provider,
        github_workflow=_resolve("DEPLOY_GITHUB_WORKFLOW", ""),
        github_repo=_resolve("DEPLOY_GITHUB_REPO", ""),
        require_pushed_ref=_env_bool("DEPLOY_REQUIRE_PUSHED_REF", True),
        confirm_timeout_sec=confirm_sec,
        poll_timeout_sec=poll_sec,
        ssh_host=_resolve("DEPLOY_SSH_HOST", ""),
        ssh_user=_resolve("DEPLOY_SSH_USER", ""),
        ssh_key_path=_resolve("DEPLOY_SSH_KEY_PATH", ""),
        ssh_app_path=_resolve("DEPLOY_SSH_APP_PATH", ""),
        local_project_path=_resolve("DEPLOY_LOCAL_PROJECT_PATH", ""),
        ssh_restart_cmd=_resolve("DEPLOY_SSH_RESTART_CMD", ""),
        ssh_port=_resolve("DEPLOY_SSH_PORT", "22") or "22",
        health_url=_resolve("DEPLOY_HEALTH_URL", ""),
        health_timeout_sec=health_timeout,
        health_retries=health_retries,
        ssh_sync_pairs=_parse_sync_pairs(_resolve("DEPLOY_SSH_SYNC_PAIRS", "")),
        ssh_build_steps=_parse_build_steps(_resolve("DEPLOY_SSH_BUILD_STEPS", "")),
        ssh_rsync_excludes=_parse_rsync_excludes(_resolve("DEPLOY_SSH_RSYNC_EXCLUDES", "")),
        github_workflow_env_input=_resolve("DEPLOY_GITHUB_WORKFLOW_ENV_INPUT", "environment")
        or "environment",
    )


def normalize_env(env: str | None) -> str:
    e = (env or "").strip().lower()
    if not e:
        return ""
    aliases = {
        "预发": "staging",
        "测试": "staging",
        "staging": "staging",
        "stage": "staging",
        "生产": "production",
        "正式": "production",
        "prod": "production",
        "production": "production",
    }
    return aliases.get(e, e)


def env_allowed(env: str, cfg: DeployConfig | None = None) -> bool:
    c = cfg or get_deploy_config()
    norm = normalize_env(env)
    if not norm:
        return False
    if norm in ("production", "prod") and not c.allow_production:
        return False
    e = (env or "").strip().lower()
    return norm in c.env_whitelist or e in c.env_whitelist


def default_deploy_ref() -> str:
    for name in ("DEPLOY_DEFAULT_REF", "LOCAL_DEV_WORK_BRANCH", "CURSOR_DEV_WORK_BRANCH"):
        raw = _resolve(name, "")
        if raw:
            return raw
    return ""


def default_deploy_env(cfg: DeployConfig | None = None) -> str:
    """未从消息/参数解析出环境时，用白名单首项（不再写死 staging）。"""
    c = cfg or get_deploy_config()
    if c.env_whitelist:
        return str(c.env_whitelist[0])
    return "staging"


def env_display_label(env: str) -> str:
    """UI 展示用环境名（配置驱动，非项目写死）。"""
    norm = normalize_env(env)
    if norm == "staging":
        return "预发"
    if norm in ("production", "prod"):
        return "生产"
    return (env or "").strip() or default_deploy_env()
