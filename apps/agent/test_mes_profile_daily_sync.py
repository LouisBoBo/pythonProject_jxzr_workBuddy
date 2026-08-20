"""每日打开自动同步资料包 OpenAPI。"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

_AGENT = Path(__file__).resolve().parent
if str(_AGENT) not in sys.path:
    sys.path.insert(0, str(_AGENT))

from mes_profile_daily_sync import (  # noqa: E402
    _should_run,
    _write_stamp,
    maybe_daily_sync_openapi,
)


class DailySyncTests(unittest.TestCase):
    def test_skip_when_already_ok_today(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            pdir = Path(td)
            from datetime import date

            _write_stamp(
                pdir,
                {"date": date.today().isoformat(), "ok": True, "entity_count": 10},
            )
            run, reason = _should_run(pdir)
            self.assertFalse(run)
            self.assertEqual(reason, "already_synced_today")

    def test_run_when_no_stamp(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            run, reason = _should_run(Path(td))
            self.assertTrue(run)
            self.assertEqual(reason, "run")

    def test_maybe_sync_calls_refresh(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            pdir = Path(td)
            with patch("mes_profile.active_profile_id", return_value="demo"):
                with patch("mes_profile.profile_dir", return_value=pdir):
                    with patch(
                        "mes_profile_refresh.refresh_mes_profile_from_runtime",
                        return_value={
                            "ok": True,
                            "entity_count": 3,
                            "added": ["warehouse-inventory-stock"],
                            "fetched_from": "http://127.0.0.1:8009/openapi.json",
                        },
                    ) as refresh:
                        out = maybe_daily_sync_openapi(force=True)
            self.assertTrue(out.get("ok"))
            self.assertFalse(out.get("skipped"))
            refresh.assert_called_once()
            stamp = json.loads((pdir / ".daily_openapi_sync.json").read_text(encoding="utf-8"))
            self.assertTrue(stamp.get("ok"))
            self.assertEqual(stamp.get("entity_count"), 3)


if __name__ == "__main__":
    unittest.main()
