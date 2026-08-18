"""WorkBuddy 会话 JWT：HS256 自签，拒绝 alg=none 与伪造 payload。"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
from pathlib import Path
from typing import Any

_ISS = "zr-workbuddy"
_TYP = "wb_session"
_DEFAULT_TTL_SEC = int(os.getenv("WORKBUDDY_SESSION_TTL_SEC", "28800") or "28800")


def _b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _b64url_decode(text: str) -> bytes:
    pad = "=" * (-len(text) % 4)
    return base64.urlsafe_b64decode((text + pad).encode("ascii"))


def _secret() -> bytes:
    explicit = (os.getenv("WORKBUDDY_JWT_SECRET") or "").strip()
    if explicit:
        return explicit.encode("utf-8")
    root: Path | None = None
    data_dir = (os.getenv("DATA_DIR") or "").strip()
    if data_dir:
        root = Path(data_dir)
    else:
        try:
            from config import Config

            root = Path(Config.DATA_DIR)
        except Exception:
            root = Path(__file__).resolve().parents[2] / "data"
    root.mkdir(parents=True, exist_ok=True)
    path = root / ".session_jwt_secret"
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


def issue_session_jwt(
    *,
    user_id: Any,
    username: str,
    ttl_sec: int | None = None,
    extra: dict[str, Any] | None = None,
) -> tuple[str, int]:
    now = int(time.time())
    ttl = _DEFAULT_TTL_SEC if ttl_sec is None else int(ttl_sec)
    ttl = max(60, min(ttl, 7 * 86400))
    exp = now + ttl
    payload: dict[str, Any] = {
        "iss": _ISS,
        "typ": _TYP,
        "sub": user_id,
        "username": (username or "").strip() or f"user-{user_id}",
        "iat": now,
        "exp": exp,
    }
    if extra:
        for k, v in extra.items():
            if k not in payload:
                payload[k] = v
    header = _b64url_encode(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")).encode())
    body = _b64url_encode(json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode())
    sig = _b64url_encode(
        hmac.new(_secret(), f"{header}.{body}".encode("ascii"), hashlib.sha256).digest()
    )
    return f"{header}.{body}.{sig}", exp


def verify_session_jwt(token: str) -> dict[str, Any] | None:
    raw = (token or "").strip()
    parts = raw.split(".")
    if len(parts) != 3:
        return None
    header_b64, body_b64, sig_b64 = parts
    try:
        header = json.loads(_b64url_decode(header_b64).decode("utf-8"))
    except Exception:
        return None
    if not isinstance(header, dict):
        return None
    if str(header.get("alg") or "") != "HS256":
        return None
    expect = _b64url_encode(
        hmac.new(_secret(), f"{header_b64}.{body_b64}".encode("ascii"), hashlib.sha256).digest()
    )
    try:
        if not hmac.compare_digest(sig_b64, expect):
            return None
    except Exception:
        return None
    try:
        payload = json.loads(_b64url_decode(body_b64).decode("utf-8"))
    except Exception:
        return None
    if not isinstance(payload, dict):
        return None
    if payload.get("iss") != _ISS or payload.get("typ") != _TYP:
        return None
    exp = payload.get("exp")
    if not isinstance(exp, (int, float)) or time.time() > float(exp):
        return None
    return payload
