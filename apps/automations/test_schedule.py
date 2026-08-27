"""自动化调度计算单测。"""
from __future__ import annotations

import unittest
from datetime import datetime

from automations.schedule import compute_next_run_at, enrich_automation_schedule, should_run_now


class AutomationScheduleTests(unittest.TestCase):
    def test_daily_next_run(self):
        base = datetime(2026, 8, 27, 8, 0, 0)
        item = {
            "status": "active",
            "schedule_type": "recurring",
            "rrule": "FREQ=DAILY;BYHOUR=9;BYMINUTE=0",
        }
        nra = compute_next_run_at(item, base=base)
        self.assertEqual(nra, int(datetime(2026, 8, 27, 9, 0, 0).timestamp()))

    def test_weekly_friday(self):
        base = datetime(2026, 8, 27, 10, 0, 0)  # Thursday
        item = {
            "status": "active",
            "schedule_type": "recurring",
            "rrule": "FREQ=WEEKLY;BYDAY=FR;BYHOUR=17;BYMINUTE=0",
        }
        nra = compute_next_run_at(item, base=base)
        self.assertEqual(nra, int(datetime(2026, 8, 28, 17, 0, 0).timestamp()))

    def test_should_run_when_due(self):
        now = int(datetime(2026, 8, 27, 9, 5, 0).timestamp())
        item = {
            "status": "active",
            "schedule_type": "recurring",
            "rrule": "FREQ=DAILY;BYHOUR=9;BYMINUTE=0",
            "next_run_at": int(datetime(2026, 8, 27, 9, 0, 0).timestamp()),
        }
        self.assertTrue(should_run_now(item, now_ts=now))

    def test_enrich_on_create(self):
        item = enrich_automation_schedule(
            {
                "status": "active",
                "schedule_type": "recurring",
                "rrule": "FREQ=DAILY;BYHOUR=9;BYMINUTE=0",
            }
        )
        self.assertIsNotNone(item.get("next_run_at"))


if __name__ == "__main__":
    unittest.main()
