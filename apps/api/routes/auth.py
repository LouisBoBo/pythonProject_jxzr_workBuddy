"""
认证：代理 ERP 登录，解析 JWT 得到用户 id。

登录接口对齐平台：POST {PLATFORM_BASE_URL}/api/v1/auth/login
请求体：username / password / enterprise_code(可选)
"""
from __future__ import annotations

import base64
import json
import os
import time
from typing import Annotated, Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from routes_config import AgentConfig

router = APIRouter(prefix="/api/auth", tags=["auth"])

AUTH_REQUIRED = os.getenv("AUTH_REQUIRED", "true").lower() in ("1", "true", "yes")


class LoginBody(BaseModel):
    username: str = Field(..., min_length=1)
    password: str = Field(..., min_length=1)
    enterprise_code: str = ""


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    username: str
    user_id: int | str | None = None
    enterprise_code: str = ""
    expires_at: int | None = None


class UserInfo(BaseModel):
    username: str = ""
    user_id: int | str | None = None
    enterprise_code: str = ""
    expires_at: int | None = None


def _decode_jwt_payload(token: str) -> dict[str, Any]:
    """不校验签名，只读 payload（token 已由 ERP 签发）。"""
    try:
        parts = token.split(".")
        if len(parts) < 2:
            return {}
        payload = parts[1]
        payload += "=" * (-len(payload) % 4)
        raw = base64.urlsafe_b64decode(payload.encode("utf-8"))
        data = json.loads(raw.decode("utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _erp_login(username: str, password: str, enterprise_code: str = "") -> dict[str, Any]:
    base = AgentConfig.PLATFORM_BASE_URL.rstrip("/")
    body: dict[str, Any] = {"username": username, "password": password}
    if enterprise_code:
        body["enterprise_code"] = enterprise_code
    data = json.dumps(body).encode("utf-8")
    req = Request(
        f"{base}/api/v1/auth/login",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode("utf-8") or "{}")
    except HTTPError as e:
        detail = e.reason
        try:
            err_body = e.read().decode("utf-8")
            parsed = json.loads(err_body)
            detail = parsed.get("detail") or parsed.get("message") or err_body
        except Exception:
            pass
        raise HTTPException(status_code=e.code if e.code in (400, 401, 403, 422) else 401, detail=str(detail))
    except URLError as e:
        raise HTTPException(status_code=502, detail=f"无法连接 ERP 登录服务: {e.reason}")
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"登录失败: {e}")


@router.post("/login", response_model=LoginResponse)
async def login(body: LoginBody):
    """使用 ERP 真实账号登录，返回平台 access_token 与用户信息。"""
    result = _erp_login(body.username, body.password, body.enterprise_code.strip())
    token = result.get("access_token") or ""
    if not token:
        raise HTTPException(status_code=401, detail="ERP 未返回 access_token")

    payload = _decode_jwt_payload(token)
    user_id = payload.get("sub")
    exp = payload.get("exp")
    expires_at = int(exp) if isinstance(exp, (int, float)) else None

    return LoginResponse(
        access_token=token,
        token_type=str(result.get("token_type") or "bearer"),
        username=body.username,
        user_id=user_id,
        enterprise_code=body.enterprise_code.strip(),
        expires_at=expires_at,
    )


def require_auth(
    authorization: Annotated[str | None, Header()] = None,
    x_user_name: Annotated[str | None, Header(alias="X-User-Name")] = None,
) -> tuple[str, UserInfo]:
    """返回 (access_token, user)。AUTH_REQUIRED=false 时跳过（本地 Mock）。"""
    if not AUTH_REQUIRED:
        return "", UserInfo(username=x_user_name or "dev", user_id=0)

    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="未登录，请先登录")
    token = authorization.split(" ", 1)[1].strip()
    if not token:
        raise HTTPException(status_code=401, detail="未登录，请先登录")

    payload = _decode_jwt_payload(token)
    exp = payload.get("exp")
    if isinstance(exp, (int, float)) and time.time() > float(exp):
        raise HTTPException(status_code=401, detail="登录已过期，请重新登录")

    username = (x_user_name or "").strip()
    if not username:
        username = f"user-{payload.get('sub')}" if payload.get("sub") is not None else "unknown"

    user = UserInfo(
        username=username,
        user_id=payload.get("sub"),
        expires_at=int(exp) if isinstance(exp, (int, float)) else None,
    )
    return token, user


@router.get("/me", response_model=UserInfo)
async def me(
    authorization: Annotated[str | None, Header()] = None,
    x_user_name: Annotated[str | None, Header(alias="X-User-Name")] = None,
):
    """校验 token 未过期，返回用户信息。"""
    _, user = require_auth(authorization, x_user_name)
    return user
