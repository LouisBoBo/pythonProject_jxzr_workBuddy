"""查数客户端：路径/分页随资料包变化，不写死 /api/v1。"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

_AGENT = Path(__file__).resolve().parents[1]
if str(_AGENT) not in sys.path:
    sys.path.insert(0, str(_AGENT))

from tools.platform_api import (
    _collection_path,
    _list_query_string,
    _login_paths,
    _records_from_payload,
    _token_from_login_payload,
)


class PlatformApiAdaptTests(unittest.TestCase):
    def test_absolute_path_kept(self) -> None:
        self.assertEqual(_collection_path("/api/work-orders"), "/api/work-orders")
        self.assertEqual(_collection_path("/erp/mo/list"), "/erp/mo/list")

    def test_relative_uses_profile_prefix(self) -> None:
        self.assertEqual(_collection_path("devices", prefix="/api"), "/api/devices")
        self.assertEqual(_collection_path("mo/list", prefix="/erp"), "/erp/mo/list")
        self.assertEqual(_collection_path("items", prefix=""), "/items")

    def test_paging_from_openapi_names(self) -> None:
        qs = _list_query_string({"page": "pageNo", "page_size": "pageSize"}, None, 20)
        self.assertIn("pageNo=1", qs)
        self.assertIn("pageSize=20", qs)
        self.assertNotIn("limit=", qs)

    def test_paging_limit_style(self) -> None:
        qs = _list_query_string({"limit": "limit"}, {"status": "open"}, 10)
        self.assertIn("limit=10", qs)
        self.assertIn("status=open", qs)

    def test_query_values_are_urlencoded(self) -> None:
        qs = _list_query_string({"limit": "limit"}, {"q": "a b&c"}, 10)
        self.assertIn("q=a+b%26c", qs)
        self.assertNotIn("q=a b&c", qs)

    def test_unsafe_paging_name_ignored(self) -> None:
        qs = _list_query_string({"page_size": "size=1&x"}, None, 20)
        self.assertIn("limit=20", qs)
        self.assertNotIn("size=1", qs)

    def test_login_paths_no_generic_when_discovered(self) -> None:
        from unittest.mock import patch

        with patch("mes_profile.resolve_login_paths", return_value=["/api/auth/login"]):
            paths = _login_paths()
        self.assertEqual(paths, ["/api/auth/login"])
        self.assertNotIn("/login", paths)
        self.assertNotIn("/api/login", paths)

    def test_nested_data_items(self) -> None:
        records, total = _records_from_payload(
            {"data": {"items": [{"id": 1}], "total": 9}},
            ["data"],
        )
        self.assertEqual(len(records), 1)
        self.assertEqual(total, 9)

    def test_token_from_nested_login_payload(self) -> None:
        self.assertEqual(
            _token_from_login_payload({"access_token": "abc"}),
            "abc",
        )
        self.assertEqual(
            _token_from_login_payload({"data": {"token": "xyz"}}),
            "xyz",
        )

    def test_401_clears_token_and_retries(self) -> None:
        from io import BytesIO
        from unittest.mock import patch
        from urllib.error import HTTPError
        from urllib.request import Request

        from tools.platform_api import ERPClient

        client = ERPClient.__new__(ERPClient)
        client.base = "http://127.0.0.1:8009"
        client._token = "stale"
        client._login_paths = ["/api/auth/login"]
        client.ENTITY_MAP = {}
        gets = {"n": 0}

        class _Resp:
            def __init__(self, raw: bytes, status: int = 200):
                self._raw = raw
                self.status = status

            def read(self, n: int = -1) -> bytes:  # noqa: ARG002
                return self._raw

            def __enter__(self) -> "_Resp":
                return self

            def __exit__(self, *args: object) -> None:
                return None

        def fake_open(req: Request, timeout: float = 15, max_bytes: int | None = None):  # noqa: ARG001
            method = req.get_method()
            if method == "POST":
                return _Resp(b'{"access_token":"fresh"}')
            gets["n"] += 1
            if gets["n"] == 1:
                raise HTTPError(req.full_url, 401, "Unauthorized", hdrs=None, fp=BytesIO())
            return _Resp(b'{"items":[{"id":1}]}')

        with patch("tools.platform_api.urlopen_limited", side_effect=fake_open):
            out = client._request("GET", "/api/work-orders?limit=1")
        self.assertEqual(client._token, "fresh")
        self.assertEqual(gets["n"], 2)
        self.assertNotIn("error", out if isinstance(out, dict) else {})


if __name__ == "__main__":
    unittest.main()
