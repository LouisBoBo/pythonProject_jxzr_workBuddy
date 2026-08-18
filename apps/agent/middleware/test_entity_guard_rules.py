"""实体守卫：对照当前资料包目录，不写死 work-orders / production-plans。"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

_AGENT = Path(__file__).resolve().parents[1]
if str(_AGENT) not in sys.path:
    sys.path.insert(0, str(_AGENT))

from middleware.entity_guard_rules import guard_mismatch_tip

_CATALOG = [
    {
        "id": "mo-list",
        "label": "生产工单",
        "aliases": ["生产工单", "工单", "派工单"],
    },
    {
        "id": "aps-plans",
        "label": "排产计划",
        "aliases": ["排产计划", "排程计划", "排产"],
    },
]


class EntityGuardCatalogTests(unittest.TestCase):
    def test_wrong_entity_redirects_to_catalog_id(self) -> None:
        with patch("middleware.entity_guard_rules._load_catalog", return_value=_CATALOG):
            tip = guard_mismatch_tip("mo-list", "查一下排程计划")
        self.assertIsNotNone(tip)
        self.assertIn("aps-plans", tip)
        self.assertNotIn("production-plans", tip)
        self.assertNotIn("work-orders", tip)

    def test_no_fake_id_when_catalog_lacks_peer(self) -> None:
        only_mo = [_CATALOG[0]]
        with patch("middleware.entity_guard_rules._load_catalog", return_value=only_mo):
            tip = guard_mismatch_tip("mo-list", "查一下排程计划")
        self.assertIsNone(tip)

    def test_matching_entity_not_blocked(self) -> None:
        with patch("middleware.entity_guard_rules._load_catalog", return_value=_CATALOG):
            self.assertIsNone(guard_mismatch_tip("mo-list", "查生产工单列表"))

    def test_ambiguous_mentions_both_not_blocked(self) -> None:
        with patch("middleware.entity_guard_rules._load_catalog", return_value=_CATALOG):
            self.assertIsNone(guard_mismatch_tip("mo-list", "工单和排产计划各查一下"))

    def test_empty_catalog_never_hardcodes(self) -> None:
        with patch("middleware.entity_guard_rules._load_catalog", return_value=[]):
            self.assertIsNone(guard_mismatch_tip("work-orders", "查排产计划"))


if __name__ == "__main__":
    unittest.main()
