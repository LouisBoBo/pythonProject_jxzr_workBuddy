"""登录身份映射：alg=none 仅 sandbox；会话仍走 HS256。"""
from __future__ import annotations

import base64
import json
import sys
import unittest
from pathlib import Path

_API = Path(__file__).resolve().parent
_APPS = _API.parent
if str(_API) not in sys.path:
    sys.path.insert(0, str(_API))
if str(_APPS / "agent") not in sys.path:
    sys.path.insert(0, str(_APPS / "agent"))

from routes.auth import _identity_from_login_result  # noqa: E402


def _b64(obj: dict) -> str:
    raw = json.dumps(obj, separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _unsigned(sub: str, username: str) -> str:
    return (
        f"{_b64({'alg': 'none', 'typ': 'JWT'})}."
        f"{_b64({'sub': sub, 'preferred_username': username})}."
    )


def _signed_looking(sub: str, username: str) -> str:
    """伪造带 alg=HS256 的三段式（本测试不验签，只测读取路径）。"""
    return (
        f"{_b64({'alg': 'HS256', 'typ': 'JWT'})}."
        f"{_b64({'sub': sub, 'preferred_username': username})}."
        f"{_b64({'sig': 'fake'})}"
    )


class AuthIdentityTests(unittest.TestCase):
    def test_sandbox_alg_none_reads_sub(self) -> None:
        uid, uname = _identity_from_login_result(
            {
                "access_token": _unsigned("42", "alice"),
                "sandbox": True,
            },
            "",
        )
        self.assertEqual(str(uid), "42")
        self.assertEqual(uname, "alice")

    def test_nonsandbox_alg_none_ignored(self) -> None:
        uid, uname = _identity_from_login_result(
            {
                "access_token": _unsigned("evil", "attacker"),
            },
            "fallback",
        )
        self.assertEqual(uid, "fallback")
        self.assertEqual(uname, "fallback")

    def test_signed_alg_reads_sub_after_login(self) -> None:
        uid, uname = _identity_from_login_result(
            {
                "access_token": _signed_looking("7", "bob"),
            },
            "",
        )
        self.assertEqual(str(uid), "7")
        self.assertEqual(uname, "bob")

    def test_explicit_user_id_wins(self) -> None:
        uid, uname = _identity_from_login_result(
            {
                "user_id": 1,
                "username": "admin",
                "access_token": _unsigned("999", "other"),
                "sandbox": True,
            },
            "fallback",
        )
        self.assertEqual(uid, 1)
        self.assertEqual(uname, "admin")


if __name__ == "__main__":
    unittest.main()
