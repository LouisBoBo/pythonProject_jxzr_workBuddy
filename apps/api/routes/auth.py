"""
认证：ZR WorkBuddy 平台登录。

与「系统配置 → MES 接入」上传的表结构 / OpenAPI **无关**。
上传接口文档只用来生成可查对象；本接口不读取资料包里的登录路径或 docs 主机。

登录目标：仅环境变量 PLATFORM_BASE_URL；连不上时仅当设置了
API_PROBE_SANDBOX_URL 才回落探活沙箱。界面里的平台访问地址不用于本登录。
成功后签发 WorkBuddy 自签会话 JWT（HS256），前端后续请求带 Bearer。
"""
from __future__ import annotations

import json
import logging
import os
from typing import Annotated, Any
from urllib.error import HTTPError, URLError
from urllib.request import Request

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from routes_config import AgentConfig  # noqa: F401 — 保持 agent 路径已注入
from safe_http import assert_http_url_allowed, urlopen_limited
from session_jwt import issue_session_jwt, verify_session_jwt

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["认证"])

AUTH_REQUIRED = os.getenv("AUTH_REQUIRED", "true").lower() in ("1", "true", "yes")


class LoginBody(BaseModel):
    username: str = Field(..., min_length=1, description="WorkBuddy 账号")
    password: str = Field(..., min_length=1, description="WorkBuddy 密码")
    enterprise_code: str = Field("", description="企业编码（登录页下拉，可空）")


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    username: str
    user_id: int | str | None = None
    enterprise_code: str = ""
    expires_at: int | None = None


class ExchangeBody(BaseModel):
    token: str = Field(..., min_length=8, description="宿主页面传入的平台 token")
    username: str = Field("", description="展示名兜底（服务端仍以 /me 为准）")
    display_name: str = Field("", description="侧栏展示名（可选）")


class UserInfo(BaseModel):
    username: str = ""
    user_id: int | str | None = None
    enterprise_code: str = ""
    expires_at: int | None = None


def _username_from_payload(payload: dict[str, Any]) -> str | None:
    """从 JWT 或 /me 响应取登录名。"""
    for key in ("preferred_username", "username", "unique_name", "name"):
        val = payload.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    return None


def _env_platform_base() -> str:
    """WorkBuddy 登录只认环境变量，不读 UI 覆盖（防改设置劫持密码）。"""
    return (os.getenv("PLATFORM_BASE_URL") or "").strip().rstrip("/")


def _login_base_urls() -> list[str]:
    """WorkBuddy 登录目标：环境变量平台地址 → 显式探活沙箱。不硬编码 :8001。"""
    primary = _env_platform_base()
    sandbox = (os.getenv("API_PROBE_SANDBOX_URL") or "").strip().rstrip("/")
    out: list[str] = []
    for candidate in (primary, sandbox):
        if not candidate or candidate in out:
            continue
        try:
            out.append(assert_http_url_allowed(candidate, what="登录地址"))
        except ValueError:
            logger.warning("忽略非法登录基址: %s", candidate[:80])
    return out


# WorkBuddy / 探活沙箱自身的登录路径，不是客户 MES OpenAPI 里的登录接口
_WORKBUDDY_LOGIN_PATHS = ("/api/v1/auth/login", "/api/auth/login")
_ME_PATHS = ("/api/auth/me", "/api/v1/auth/me")


def _post_erp_login(base: str, body: dict[str, Any]) -> dict[str, Any]:
    data = json.dumps(body).encode("utf-8")
    last_http: HTTPError | None = None
    last_url: URLError | None = None
    for path in _WORKBUDDY_LOGIN_PATHS:
        req = Request(
            f"{base}{path}",
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urlopen_limited(req, timeout=15, max_bytes=1024 * 1024) as resp:
                return json.loads(resp.read().decode("utf-8") or "{}")
        except HTTPError as e:
            if e.code in (404, 405):
                last_http = e
                continue
            raise
        except URLError as e:
            last_url = e
            break
    if last_url:
        raise last_url
    if last_http:
        raise last_http
    raise URLError("login_path_not_found")


def _erp_login(username: str, password: str, enterprise_code: str = "") -> dict[str, Any]:
    body: dict[str, Any] = {"username": username, "password": password}
    if enterprise_code:
        body["enterprise_code"] = enterprise_code

    bases = _login_base_urls()
    if not bases:
        raise HTTPException(
            status_code=502,
            detail=(
                "未配置 WorkBuddy 登录地址。"
                "请在环境变量设置 PLATFORM_BASE_URL；本地开发可设置 API_PROBE_SANDBOX_URL。"
                "这与 MES 接口文档、界面里的平台访问地址无关。"
            ),
        )
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
            # 404：该基址不是 API（常见于填了网页端口），继续试下一个
            if e.code in (404, 405):
                last_url_err = URLError(f"HTTP {e.code} at {base}")
                logger.info("登录 %s 返回 %s，尝试下一地址", base, e.code)
                continue
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

    raise HTTPException(
        status_code=502,
        detail=(
            "无法连接 WorkBuddy 登录服务。"
            "这与 MES 接口文档无关。请检查环境变量 PLATFORM_BASE_URL，"
            "或启动本地探活沙箱（./scripts/dev.sh）。"
        ),
    )


def _identity_from_login_result(result: dict[str, Any], fallback_username: str) -> tuple[Any, str]:
    user_id = result.get("user_id")
    if user_id is None:
        user_id = result.get("id")
    username = _username_from_payload(result) or fallback_username
    token = result.get("access_token") or result.get("token") or ""
    if user_id is None and isinstance(token, str) and token.count(".") == 2:
        # 仅作身份映射：上游登录已成功，不校验其 JWT 签名
        try:
            import base64

            payload_b64 = token.split(".")[1]
            payload_b64 += "=" * (-len(payload_b64) % 4)
            data = json.loads(base64.urlsafe_b64decode(payload_b64.encode("utf-8")))
            if isinstance(data, dict):
                if user_id is None:
                    user_id = data.get("sub")
                if not _username_from_payload({"username": username}) and _username_from_payload(data):
                    username = _username_from_payload(data) or username
        except Exception:
            pass
    if user_id is None:
        user_id = fallback_username
    return user_id, username


def _issue_wb_session(*, user_id: Any, username: str, enterprise_code: str = "") -> tuple[str, int]:
    extra = {}
    if enterprise_code:
        extra["enterprise_code"] = enterprise_code
    return issue_session_jwt(user_id=user_id, username=username, extra=extra or None)


@router.post(
    "/login",
    response_model=LoginResponse,
    summary="WorkBuddy 登录",
    description=(
        "ZR WorkBuddy 平台登录，与 MES 资料包、上传的接口文档无关。"
        "登录目标只读环境变量 PLATFORM_BASE_URL（及可选 API_PROBE_SANDBOX_URL），"
        "不使用界面里的平台访问地址。"
        "成功后签发 WorkBuddy 会话 JWT（HS256），前端后续请求带 Bearer。"
    ),
)
async def login(body: LoginBody):
    """WorkBuddy 账号登录，返回自签 access_token 与用户信息。"""
    result = _erp_login(body.username, body.password, body.enterprise_code.strip())
    token = result.get("access_token") or result.get("token") or ""
    if not token:
        raise HTTPException(status_code=401, detail="登录服务未返回 access_token")

    user_id, username = _identity_from_login_result(result, body.username)
    wb_token, exp = _issue_wb_session(
        user_id=user_id,
        username=username,
        enterprise_code=body.enterprise_code.strip(),
    )
    return LoginResponse(
        access_token=wb_token,
        token_type="bearer",
        username=username,
        user_id=user_id,
        enterprise_code=body.enterprise_code.strip(),
        expires_at=exp,
    )


def _me_bases() -> list[str]:
    bases: list[str] = []
    try:
        from mes_profile import resolve_mes_api_base

        mes = (resolve_mes_api_base() or "").strip()
        if mes:
            bases.append(mes)
    except Exception:
        pass
    for extra in _login_base_urls():
        if extra not in bases:
            bases.append(extra)
    out: list[str] = []
    for b in bases:
        try:
            out.append(assert_http_url_allowed(b, what="身份校验地址"))
        except ValueError:
            continue
    return out


def _identity_from_foreign_token(token: str) -> dict[str, Any] | None:
    """用宿主 token 调 MES 或登录服务 /me，成功才认身份。"""
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
    }
    for base in _me_bases():
        for path in _ME_PATHS:
            req = Request(f"{base}{path}", headers=headers, method="GET")
            try:
                with urlopen_limited(req, timeout=10, max_bytes=65536) as resp:
                    data = json.loads(resp.read().decode("utf-8") or "{}")
            except Exception:
                continue
            if not isinstance(data, dict):
                continue
            username = _username_from_payload(data)
            user_id = data.get("user_id")
            if user_id is None:
                user_id = data.get("id")
            if user_id is None:
                user_id = data.get("sub")
            if username or user_id is not None:
                return {
                    "username": username or (f"user-{user_id}" if user_id is not None else ""),
                    "user_id": user_id,
                    "enterprise_code": str(data.get("enterprise_code") or ""),
                }
    return None


@router.post(
    "/exchange",
    response_model=LoginResponse,
    summary="嵌入身份兑换",
    description=(
        "平台嵌入时 URL 上的宿主 token 不能直接当 WorkBuddy 会话。"
        "本接口用该 token 调用业务系统 /me 校验身份后，签发 WorkBuddy 会话 JWT。"
        "查数仍使用系统配置中的 MES 接口账号，不会把本会话 token 转给 MES。"
    ),
)
async def exchange(body: ExchangeBody):
    """校验宿主 token 后签发 WorkBuddy 会话。"""
    ident = _identity_from_foreign_token(body.token.strip())
    if not ident:
        raise HTTPException(
            status_code=401,
            detail="嵌入身份校验失败。请确认宿主 token 有效，且 MES 接口地址可达。",
        )
    username = ident.get("username") or body.username.strip() or "embed-user"
    user_id = ident.get("user_id")
    if user_id is None:
        user_id = username
    wb_token, exp = _issue_wb_session(
        user_id=user_id,
        username=username,
        enterprise_code=str(ident.get("enterprise_code") or ""),
    )
    return LoginResponse(
        access_token=wb_token,
        token_type="bearer",
        username=username,
        user_id=user_id,
        enterprise_code=str(ident.get("enterprise_code") or ""),
        expires_at=exp,
    )


def settings_admin_allowed(user: UserInfo) -> bool:
    """SETTINGS_ADMIN_USERS 为空时所有登录用户可改配置（兼容）；非空则仅名单内。"""
    raw = (os.getenv("SETTINGS_ADMIN_USERS") or "").strip()
    if not raw:
        return True
    names = {x.strip().lower() for x in raw.split(",") if x.strip()}
    uname = (user.username or "").strip().lower()
    uid = str(user.user_id if user.user_id is not None else "").strip().lower()
    return uname in names or (uid != "" and uid in names)


def assert_settings_admin(auth: tuple) -> None:
    _token, user = auth
    if not settings_admin_allowed(user):
        raise HTTPException(status_code=403, detail="仅管理员可修改系统配置与 MES 资料")


def require_auth(
    authorization: Annotated[str | None, Header()] = None,
    x_user_name: Annotated[str | None, Header(alias="X-User-Name")] = None,
) -> tuple[str, UserInfo]:
    """返回 (access_token, user)。AUTH_REQUIRED=false 时跳过（本地 Mock）。

    生产：校验 WorkBuddy HS256 会话 JWT；user_id 取 sub，username 取 claim。
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

    payload = verify_session_jwt(token)
    if not payload:
        raise HTTPException(status_code=401, detail="登录已过期或无效，请重新登录")

    sub = payload.get("sub")
    jwt_name = _username_from_payload(payload)
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
        enterprise_code=str(payload.get("enterprise_code") or ""),
        expires_at=int(payload["exp"]) if isinstance(payload.get("exp"), (int, float)) else None,
    )
    return token, user


@router.get(
    "/me",
    response_model=UserInfo,
    summary="当前登录用户",
    description="校验 WorkBuddy 会话 JWT 签名与有效期，返回用户名与 user_id。",
)
async def me(
    authorization: Annotated[str | None, Header()] = None,
    x_user_name: Annotated[str | None, Header(alias="X-User-Name")] = None,
):
    """校验 token 未过期，返回用户信息。"""
    _, user = require_auth(authorization, x_user_name)
    return user
