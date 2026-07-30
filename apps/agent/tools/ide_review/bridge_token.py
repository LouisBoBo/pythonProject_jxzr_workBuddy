"""长期 Bridge 凭证：配对一次，扩展自动连，不随网页 ERP JWT 过期。

格式：wb1.<base64url(payload)>.<base64url(hmac-sha256)>
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
from pathlib import Path
from typing import Any


_TOKEN_PREFIX = "wb1."
_DEFAULT_TTL_DAYS = int(os.getenv("IDE_BRIDGE_TOKEN_TTL_DAYS", "90") or "90")


def _b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _b64url_decode(text: str) -> bytes:
    pad = "=" * (-len(text) % 4)
    return base64.urlsafe_b64decode((text + pad).encode("ascii"))


def _secret() -> bytes:
    explicit = (os.getenv("IDE_BRIDGE_TOKEN_SECRET") or "").strip()
    if explicit:
        return explicit.encode("utf-8")
    # 本地开发：DATA_DIR 下落盘一次，避免每次重启签发密钥变化导致旧凭证失效
    try:
        from config import Config

        root = Path(Config.DATA_DIR) / "ide_bridge"
        root.mkdir(parents=True, exist_ok=True)
        path = root / ".bridge_token_secret"
        if path.is_file():
            data = path.read_bytes().strip()
            if data:
                return data
        secret = hashlib.sha256(os.urandom(32)).hexdigest().encode("utf-8")
        path.write_bytes(secret)
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass
        return secret
    except Exception:
        # 极端降级：进程内不稳定，仅防完全不可用
        return hashlib.sha256(b"workbuddy-ide-bridge-dev").digest()


def is_bridge_token(token: str) -> bool:
    return bool(token) and token.startswith(_TOKEN_PREFIX)


def issue_bridge_token(
    *,
    user_id: Any,
    username: str = "",
    ttl_days: int | None = None,
) -> dict[str, Any]:
    days = _DEFAULT_TTL_DAYS if ttl_days is None else int(ttl_days)
    days = max(1, min(days, 3650))
    now = int(time.time())
    exp = now + days * 86400
    payload = {
        "typ": "wb_ide_bridge",
        "sub": user_id,
        "username": (username or "").strip() or f"user-{user_id}",
        "iat": now,
        "exp": exp,
    }
    body = _b64url_encode(json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
    sig = _b64url_encode(hmac.new(_secret(), body.encode("ascii"), hashlib.sha256).digest())
    token = f"{_TOKEN_PREFIX}{body}.{sig}"
    return {
        "access_token": token,
        "token_type": "bridge",
        "expires_in": exp - now,
        "expires_at": exp,
        "user_id": user_id,
        "username": payload["username"],
        "hint": f"已写入长期凭证（约 {days} 天）。网页登录过期也无需再配对；到期或换机再 Pair 一次即可。",
    }


def verify_bridge_token(token: str) -> dict[str, Any] | None:
    """校验成功返回 payload；失败返回 None。"""
    raw = (token or "").strip()
    if not is_bridge_token(raw):
        return None
    try:
        rest = raw[len(_TOKEN_PREFIX) :]
        body, sig = rest.rsplit(".", 1)
        expect = _b64url_encode(hmac.new(_secret(), body.encode("ascii"), hashlib.sha256).digest())
        if not hmac.compare_digest(expect, sig):
            return None
        payload = json.loads(_b64url_decode(body).decode("utf-8"))
        if not isinstance(payload, dict):
            return None
        if payload.get("typ") != "wb_ide_bridge":
            return None
        exp = payload.get("exp")
        if not isinstance(exp, (int, float)) or time.time() > float(exp):
            return None
        if payload.get("sub") is None:
            return None
        return payload
    except Exception:
        return None
