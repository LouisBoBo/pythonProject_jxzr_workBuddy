"""
认证：代理 ERP 登录，解析 JWT 得到用户 id。

登录接口对齐平台：POST {PLATFORM_BASE_URL}/api/v1/auth/login
请求体：username / password / enterprise_code(可选)

本地开发：若 PLATFORM_BASE_URL（默认 :8000）连不上，自动改打
API_PROBE_SANDBOX_URL（dev.sh 默认 :8001 探活沙箱），避免 Connection refused 卡死登录。
"""
from __future__ import annotations

import base64
import json
import logging
import os
import time
from typing import Annotated, Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from routes_config import AgentConfig

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["认证"])

AUTH_REQUIRED = os.getenv("AUTH_REQUIRED", "true").lower() in ("1", "true", "yes")


class LoginBody(BaseModel):
    username: str = Field(..., min_length=1, description="ERP 账号")
    password: str = Field(..., min_length=1, description="ERP 密码")
    enterprise_code: str = Field("", description="企业编码（登录页下拉，可空）")


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


def _username_from_jwt(payload: dict[str, Any]) -> str | None:
    """从 JWT claim 取登录名；没有则返回 None（再降级到请求头）。"""
    for key in ("preferred_username", "username", "unique_name", "name"):
        val = payload.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    return None


def _login_base_urls() -> list[str]:
    """登录目标：主 ERP → 本地探活沙箱（仅当不同且已配置）。

    PLATFORM_BASE_URL 每次现场解析（settings.json 覆盖优先），避免保存配置后仍打旧地址。
    """
    primary = ""
    try:
        from settings_store import resolve_setting

        primary = (resolve_setting("PLATFORM_BASE_URL", "") or "").rstrip("/")
    except Exception:
        primary = ""
    if not primary:
        primary = (AgentConfig.PLATFORM_BASE_URL or "").rstrip("/")
    sandbox = (os.getenv("API_PROBE_SANDBOX_URL") or "").strip().rstrip("/")
    out: list[str] = []
    for candidate in (primary, sandbox):
        if not candidate or candidate in out:
            continue
        low = candidate.lower()
        if not (low.startswith("http://") or low.startswith("https://")):
            logger.warning("忽略非法登录基址: %s", candidate[:80])
            continue
        out.append(candidate)
    # 再兜底本仓默认沙箱端口，避免未 export 时仍 Connection refused
    fallback = "http://127.0.0.1:8001"
    if fallback not in out:
        out.append(fallback)
    return out


def _post_erp_login(base: str, body: dict[str, Any]) -> dict[str, Any]:
    data = json.dumps(body).encode("utf-8")
    req = Request(
        f"{base}/api/v1/auth/login",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode("utf-8") or "{}")


def _erp_login(username: str, password: str, enterprise_code: str = "") -> dict[str, Any]:
    body: dict[str, Any] = {"username": username, "password": password}
    if enterprise_code:
        body["enterprise_code"] = enterprise_code

    bases = _login_base_urls()
    last_url_err: URLError | None = None
    for i, base in enumerate(bases):
        try:
            result = _post_erp_login(base, body)
            if i > 0:
                logger.warning(
                    "ERP 主地址不可达，已改用备用登录 %s（本地沙箱/探活）",
                    base,
                )
            return result
        except HTTPError as e:
            detail = e.reason
            try:
                err_body = e.read().decode("utf-8")
                parsed = json.loads(err_body)
                detail = parsed.get("detail") or parsed.get("message") or err_body
            except Exception:
                pass
            raise HTTPException(
                status_code=e.code if e.code in (400, 401, 403, 422) else 401,
                detail=str(detail),
            ) from e
        except URLError as e:
            last_url_err = e
            logger.info("登录连接失败 %s: %s，尝试下一地址", base, e.reason)
            continue
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"登录失败: {e}") from e

    reason = last_url_err.reason if last_url_err else "未知"
    raise HTTPException(
        status_code=502,
        detail=(
            f"无法连接 ERP 登录服务: {reason}。"
            f"已尝试：{', '.join(bases)}。"
            "请启动本地 ERP(:8000) 或确认探活沙箱(:8001) 已随 ./scripts/dev.sh 启动。"
        ),
    )


@router.post(
    "/login",
    response_model=LoginResponse,
    summary="ERP 账号登录",
    description=(
        "代理平台登录；主地址不可达时自动回落到 API 探活沙箱（本地开发）。"
        "成功返回 access_token，前端后续请求带 Bearer。"
    ),
)
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
    """返回 (access_token, user)。AUTH_REQUIRED=false 时跳过（本地 Mock）。

    生产：user_id 固定取 JWT sub；username 优先 JWT claim，其次才用 X-User-Name（展示/兼容）。
    历史归属以 user_id 为准，避免仅靠请求头冒名访问他人会话。
    亦接受 IDE Bridge 长期凭证（wb1.…），供 VS Code 扩展在网页 JWT 过期后继续工作。
    """
    if not AUTH_REQUIRED:
        return "", UserInfo(username=x_user_name or "dev", user_id=0)

    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="未登录，请先登录")
    token = authorization.split(" ", 1)[1].strip()
    if not token:
        raise HTTPException(status_code=401, detail="未登录，请先登录")

    # 长期 Bridge 凭证（配对一次 ≈ 90 天）
    try:
        from tools.ide_review.bridge_token import is_bridge_token, verify_bridge_token

        if is_bridge_token(token):
            bridge = verify_bridge_token(token)
            if not bridge:
                raise HTTPException(
                    status_code=401,
                    detail="Bridge 凭证无效或已过期，请在网页重新「配对 VS Code」",
                )
            return token, UserInfo(
                username=str(bridge.get("username") or f"user-{bridge.get('sub')}"),
                user_id=bridge.get("sub"),
                expires_at=int(bridge["exp"]) if isinstance(bridge.get("exp"), (int, float)) else None,
            )
    except HTTPException:
        raise
    except Exception:
        pass

    payload = _decode_jwt_payload(token)
    exp = payload.get("exp")
    if isinstance(exp, (int, float)) and time.time() > float(exp):
        raise HTTPException(status_code=401, detail="登录已过期，请重新登录")

    sub = payload.get("sub")
    jwt_name = _username_from_jwt(payload)
    header_name = (x_user_name or "").strip()
    if jwt_name:
        username = jwt_name
    elif header_name:
        username = header_name
    elif sub is not None:
        username = f"user-{sub}"
    else:
        username = "unknown"

    user = UserInfo(
        username=username,
        user_id=sub,
        expires_at=int(exp) if isinstance(exp, (int, float)) else None,
    )
    return token, user


@router.get(
    "/me",
    response_model=UserInfo,
    summary="当前登录用户",
    description="校验 Bearer token 未过期，返回用户名与 user_id。",
)
async def me(
    authorization: Annotated[str | None, Header()] = None,
    x_user_name: Annotated[str | None, Header(alias="X-User-Name")] = None,
):
    """校验 token 未过期，返回用户信息。"""
    _, user = require_auth(authorization, x_user_name)
    return user
