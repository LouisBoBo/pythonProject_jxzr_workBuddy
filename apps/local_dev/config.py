"""本机写码配置。"""
from __future__ import annotations

import os
from dataclasses import dataclass


def _env_bool(name: str, default: bool = True) -> bool:
    raw = os.getenv(name)
    if raw is None or not str(raw).strip():
        return default
    return str(raw).strip().lower() in ("1", "true", "yes", "on")


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


def _env_agent(name: str, default: str = "cursor_sdk") -> str:
    """本机写码执行器：cursor_sdk（默认）| llm（旧 DeepSeek 工具环，应急）。"""
    raw = (os.getenv(name) or "").strip().lower()
    if not raw:
        return default
    if raw in {"cursor_sdk", "cursor", "sdk", "local_cursor"}:
        return "cursor_sdk"
    if raw in {"llm", "openai", "deepseek", "local_sandbox"}:
        return "llm"
    return default


@dataclass(frozen=True)
class LocalDevConfig:
    enabled: bool = True
    # cursor_sdk：本机路径 + Cursor SDK Local Agent；llm：系统配置 LLM 工具环
    agent: str = "cursor_sdk"
    max_concurrent: int = 2
    max_concurrent_per_user: int = 1
    max_agent_steps: int = 40
    max_file_bytes: int = 512_000
    max_changed_files: int = 80
    max_total_write_bytes: int = 2_000_000
    copy_max_files: int = 4000
    copy_max_total_bytes: int = 80_000_000
    # 同步后确保开发服务 / 预览
    preview_enabled: bool = True
    preview_fe_port: int = 5175
    preview_be_port: int = 8009
    preview_start_timeout_sec: int = 75
    preview_install_timeout_sec: int = 180
    cursor_timeout_sec: int = 2700


def get_config() -> LocalDevConfig:
    return LocalDevConfig(
        enabled=_env_bool("LOCAL_DEV_ENABLED", True),
        agent=_env_agent("LOCAL_DEV_AGENT", "cursor_sdk"),
        max_concurrent=max(1, _env_int("LOCAL_DEV_MAX_CONCURRENT", 2)),
        max_concurrent_per_user=max(1, _env_int("LOCAL_DEV_MAX_CONCURRENT_PER_USER", 1)),
        max_agent_steps=max(5, _env_int("LOCAL_DEV_MAX_AGENT_STEPS", 40)),
        max_file_bytes=max(10_000, _env_int("LOCAL_DEV_MAX_FILE_BYTES", 512_000)),
        max_changed_files=max(1, _env_int("LOCAL_DEV_MAX_CHANGED_FILES", 80)),
        max_total_write_bytes=max(50_000, _env_int("LOCAL_DEV_MAX_TOTAL_WRITE_BYTES", 2_000_000)),
        copy_max_files=max(100, _env_int("LOCAL_DEV_COPY_MAX_FILES", 4000)),
        copy_max_total_bytes=max(1_000_000, _env_int("LOCAL_DEV_COPY_MAX_TOTAL_BYTES", 80_000_000)),
        preview_enabled=_env_bool("LOCAL_DEV_PREVIEW_ENABLED", True),
        preview_fe_port=max(1, _env_int("LOCAL_DEV_FE_PORT", 5175)),
        preview_be_port=max(1, _env_int("LOCAL_DEV_BE_PORT", 8009)),
        preview_start_timeout_sec=max(15, _env_int("LOCAL_DEV_PREVIEW_START_TIMEOUT", 75)),
        preview_install_timeout_sec=max(30, _env_int("LOCAL_DEV_PREVIEW_INSTALL_TIMEOUT", 180)),
        cursor_timeout_sec=max(60, _env_int("LOCAL_DEV_CURSOR_TIMEOUT_SEC", 2700)),
    )


# 受限拷贝时跳过的目录名
COPY_SKIP_DIR_NAMES = frozenset(
    {
        "node_modules",
        ".git",
        "dist",
        "build",
        "__pycache__",
        ".venv",
        "venv",
        ".tox",
        ".mypy_cache",
        ".pytest_cache",
        ".next",
        "coverage",
        ".idea",
        ".vscode",
        "target",
        "out",
        ".vite",
        ".dev-logs",
        ".cursor-sdk-store",
    }
)

# 禁止改/删（相对路径名或后缀）
SENSITIVE_BASENAMES = frozenset(
    {
        ".env",
        ".env.local",
        ".env.production",
        ".env.development",
        "credentials.json",
        "service-account.json",
        "id_rsa",
        "id_ed25519",
        "id_ecdsa",
        "id_dsa",
        "authorized_keys",
        "known_hosts",
        "passwd",
        "shadow",
    }
)

SENSITIVE_SUFFIXES = (".pem", ".p12", ".pfx", ".key", ".ppk")

# 路径任一组件命中则拒绝（防 .git/hooks、.ssh 等）
SENSITIVE_PATH_PARTS = frozenset(
    {
        ".git",
        ".ssh",
        ".gnupg",
        ".aws",
        ".kube",
        ".docker",
    }
)

# 拒绝作为目标根的敏感前缀（规范化后）
FORBIDDEN_TARGET_PREFIXES = (
    "/etc",
    "/usr",
    "/bin",
    "/sbin",
    "/var",
    "/System",
    "/Library",
    "/private/etc",
    "/private/var",
    "/Windows",
    "/Program Files",
    "/Program Files (x86)",
)
