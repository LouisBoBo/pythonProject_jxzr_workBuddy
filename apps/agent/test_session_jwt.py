"""WorkBuddy 会话 JWT：拒绝 alg=none 与篡改。"""
from __future__ import annotations

import base64
import json
import os
import sys
import unittest
from pathlib import Path

_AGENT = Path(__file__).resolve().parent
if str(_AGENT) not in sys.path:
    sys.path.insert(0, str(_AGENT))


class SessionJwtTests(unittest.TestCase):
    def setUp(self) -> None:
        os.environ["WORKBUDDY_JWT_SECRET"] = "unit-test-jwt-secret"

    def tearDown(self) -> None:
        os.environ.pop("WORKBUDDY_JWT_SECRET", None)

    def test_roundtrip(self) -> None:
        from session_jwt import issue_session_jwt, verify_session_jwt

        token, exp = issue_session_jwt(user_id="42", username="alice")
        payload = verify_session_jwt(token)
        self.assertIsNotNone(payload)
        assert payload is not None
        self.assertEqual(str(payload.get("sub")), "42")
        self.assertEqual(payload.get("username"), "alice")
        self.assertEqual(int(payload.get("exp") or 0), exp)

    def test_rejects_alg_none(self) -> None:
        from session_jwt import verify_session_jwt

        header = base64.urlsafe_b64encode(b'{"alg":"none","typ":"JWT"}').decode().rstrip("=")
        body = base64.urlsafe_b64encode(
            json.dumps({"iss": "zr-workbuddy", "typ": "wb_session", "sub": "1", "exp": 9999999999}).encode()
        ).decode().rstrip("=")
        self.assertIsNone(verify_session_jwt(f"{header}.{body}."))
        self.assertIsNone(verify_session_jwt(f"{header}.{body}.x"))

    def test_rejects_tamper(self) -> None:
        from session_jwt import issue_session_jwt, verify_session_jwt

        token, _exp = issue_session_jwt(user_id="1", username="alice")
        parts = token.split(".")
        raw = json.loads(base64.urlsafe_b64decode(parts[1] + "=" * (-len(parts[1]) % 4)))
        raw["username"] = "admin"
        fake = base64.urlsafe_b64encode(json.dumps(raw).encode()).decode().rstrip("=")
        self.assertIsNone(verify_session_jwt(f"{parts[0]}.{fake}.{parts[2]}"))


if __name__ == "__main__":
    unittest.main()
