"""
整站运行时配置（UI 覆盖层）。

解析顺序：settings.json 非空值 → 环境变量 → 空/默认。
不写回 .env；缺 Key 时由各能力自行熔断。
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import threading
from pathlib import Path
from typing import Any

from bundle_root import resolve_repo_root

# 仓库根（桌面冻结时走 bundle_root，勿写死 parents）
_REPO_ROOT = resolve_repo_root()

# P0 白名单（对话模型 + 视觉模型 + 写码车道 + ERP 地址）
ALLOWED_KEYS: frozenset[str] = frozenset(
    {
        # 通用 OpenAI 兼容对话模型
        "LLM_API_KEY",
        "LLM_BASE_URL",
        "MAIN_MODEL",
        "MODEL_NAME",
        "LLM_PROVIDER",
        # 截图视觉理解（OpenAI 兼容多模态）
        "VISION_API_KEY",
        "VISION_BASE_URL",
        "VISION_MODEL",
        "ZHIPU_API_KEY",
        "ZHIPU_BASE_URL",
        # ERP / 平台（桌面同事必配；网页也可覆盖 .env）
        "PLATFORM_BASE_URL",
        # MES 查数鉴权（调用已导入业务接口；不是 WorkBuddy 登录）
        "MES_API_USERNAME",
        "MES_API_PASSWORD",
        "MES_API_ENTERPRISE_CODE",
        # MES 资料包（DATA_DIR/mes_profiles/{id}；空=未配置，不使用仓库演示）
        "MES_PROFILE_ID",
        # 可选：显式表结构绝对路径（优先于资料包内 schema.md）
        "MES_SCHEMA_DOC",
        # 兼容旧字段（仍可从 .env / 历史 settings 解析）
        "DEEPSEEK_API_KEY",
        "DEEPSEEK_BASE_URL",
        "SILICONFLOW_API_KEY",
        "CURSOR_API_KEY",
        "CURSOR_DEV_ENABLED",
        "CURSOR_DEV_REPO_ALLOWLIST",
        "CURSOR_DEV_MODEL",
        "CURSOR_DEV_STARTING_REF",
        "CURSOR_DEV_WORK_BRANCH",
        "CURSOR_DEV_AUTO_PR",
        "CURSOR_DEV_BRANCH_PREFIX",
        # Git 审码拉仓：HTTPS 镜像前缀（国内加速；可逗号分隔多个）
        "IDE_GIT_HTTPS_MIRROR",
        "IDE_GIT_MIRROR_FIRST",
    }
)

SECRET_KEYS: frozenset[str] = frozenset(
    {
        "LLM_API_KEY",
        "VISION_API_KEY",
        "ZHIPU_API_KEY",
        "DEEPSEEK_API_KEY",
        "SILICONFLOW_API_KEY",
        "CURSOR_API_KEY",
        "MES_API_PASSWORD",
    }
)

_lock = threading.Lock()
_cache: dict[str, str] | None = None
_ENC_PREFIX = "enc:v1:"


def _data_dir() -> Path:
    raw = (os.getenv("DATA_DIR") or "").strip()
    if raw:
        return Path(raw).expanduser().resolve()
    return (_REPO_ROOT / "data").resolve()


def _settings_key() -> bytes:
    explicit = (os.getenv("WORKBUDDY_SETTINGS_KEY") or "").strip()
    if explicit:
        return hashlib.sha256(explicit.encode("utf-8")).digest()
    path = _data_dir() / ".settings_key"
    if path.is_file():
        data = path.read_bytes().strip()
        if data:
            return hashlib.sha256(data).digest() if len(data) != 32 else data
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = os.urandom(32)
    path.write_bytes(raw)
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass
    return raw


def _xor_keystream(data: bytes, key: bytes, iv: bytes) -> bytes:
    out = bytearray()
    counter = 0
    seed = key + iv
    while len(out) < len(data):
        block = hashlib.sha256(seed + counter.to_bytes(8, "big")).digest()
        out.extend(block)
        counter += 1
    return bytes(a ^ b for a, b in zip(data, out[: len(data)]))


def encrypt_secret(plain: str) -> str:
    text = (plain or "").strip()
    if not text or text.startswith(_ENC_PREFIX):
        return text
    key = _settings_key()
    iv = os.urandom(16)
    raw = text.encode("utf-8")
    ct = _xor_keystream(raw, key, iv)
    mac = hmac.new(key, iv + ct, hashlib.sha256).digest()
    blob = base64.urlsafe_b64encode(iv + mac + ct).decode("ascii")
    return _ENC_PREFIX + blob


def decrypt_secret(value: str) -> str:
    text = (value or "").strip()
    if not text.startswith(_ENC_PREFIX):
        return text
    try:
        blob = base64.urlsafe_b64decode(text[len(_ENC_PREFIX) :].encode("ascii"))
        iv, mac, ct = blob[:16], blob[16:48], blob[48:]
        key = _settings_key()
        expect = hmac.new(key, iv + ct, hashlib.sha256).digest()
        if not hmac.compare_digest(mac, expect):
            return ""
        return _xor_keystream(ct, key, iv).decode("utf-8")
    except Exception:
        return ""


def _restrict_file(path: Path) -> None:
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


def settings_path() -> Path:
    return _data_dir() / "settings.json"


def _load_unlocked() -> dict[str, str]:
    global _cache
    if _cache is not None:
        return _cache
    path = settings_path()
    if not path.is_file():
        _cache = {}
        return _cache
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        _cache = {}
        return _cache
    if not isinstance(raw, dict):
        _cache = {}
        return _cache
    out: dict[str, str] = {}
    migrate = False
    for k, v in raw.items():
        key = str(k).strip()
        if key not in ALLOWED_KEYS:
            continue
        if v is None:
            continue
        s = str(v).strip() if not isinstance(v, bool) else ("1" if v else "0")
        if s == "":
            continue
        if key in SECRET_KEYS:
            if s.startswith(_ENC_PREFIX):
                s = decrypt_secret(s)
            else:
                migrate = True
            if not s:
                continue
        out[key] = s
    _cache = out
    if migrate and out:
        _persist_unlocked(out)
    else:
        _restrict_file(path)
    return _cache


def invalidate_cache() -> None:
    global _cache
    with _lock:
        _cache = None


def get_overlay() -> dict[str, str]:
    """返回 UI 覆盖层副本（不含空值）。"""
    with _lock:
        return dict(_load_unlocked())


def resolve_setting(key: str, default: str = "") -> str:
    """UI 覆盖优先，否则环境变量，再否则 default。"""
    key = (key or "").strip()
    if not key:
        return default
    with _lock:
        overlay = _load_unlocked()
        if key in overlay and overlay[key] != "":
            return overlay[key]
    env_val = os.getenv(key)
    if env_val is not None and str(env_val).strip() != "":
        return str(env_val).strip()
    return default


def setting_source(key: str) -> str:
    """返回 ui / env / unset。"""
    key = (key or "").strip()
    with _lock:
        overlay = _load_unlocked()
        if key in overlay and overlay[key] != "":
            return "ui"
    env_val = os.getenv(key)
    if env_val is not None and str(env_val).strip() != "":
        return "env"
    return "unset"


def mask_secret(value: str) -> str:
    """掩码展示：保留末 4 位。"""
    v = (value or "").strip()
    if not v:
        return ""
    if len(v) <= 4:
        return "****"
    return f"{'*' * min(8, len(v) - 4)}{v[-4:]}"


def update_settings(partial: dict[str, Any]) -> dict[str, str]:
    """
    部分更新白名单字段。
    - 密钥/普通字段：非空字符串写入覆盖层
    - 空字符串：删除覆盖，回退到环境变量
    - 未知 key：忽略
    返回更新后的完整覆盖层。
    """
    if not isinstance(partial, dict):
        raise TypeError("partial must be a dict")

    with _lock:
        current = dict(_load_unlocked())
        for k, v in partial.items():
            key = str(k).strip()
            if key not in ALLOWED_KEYS:
                continue
            if v is None:
                current.pop(key, None)
                continue
            if isinstance(v, bool):
                s = "1" if v else "0"
            else:
                s = str(v).strip()
            if s == "":
                current.pop(key, None)
            else:
                current[key] = s

        _persist_unlocked(current)
        global _cache
        _cache = current
        return dict(current)


def _persist_unlocked(current: dict[str, str]) -> None:
    disk = dict(current)
    for key in SECRET_KEYS:
        if key in disk and disk[key]:
            disk[key] = encrypt_secret(disk[key])
    path = settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(
        json.dumps(disk, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    tmp.replace(path)
    _restrict_file(path)
