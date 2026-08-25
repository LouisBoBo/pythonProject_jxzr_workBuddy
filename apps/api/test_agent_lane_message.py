"""编排车道注入单测（无 LLM / 无 langchain）。"""
from __future__ import annotations

import unittest

from agent_lane_message import (
    append_lane_force_routes,
    compose_lane_user_text,
    platform_context_bits,
)
from stream_concurrency import (
    STREAM_BUSY_CODE,
    stream_busy_event,
    try_acquire_stream_lock,
)


class AgentLaneMessageTests(unittest.TestCase):
    def test_explicit_code_dev(self) -> None:
        out = compose_lane_user_text("加登录页", {"workbuddy_lane": "code_dev"})
        self.assertIn("workbuddy_lane=code_dev", out)
        self.assertIn("【路由·写码】", out)
        self.assertNotIn("【路由·Git 审核】", out)

    def test_explicit_paste(self) -> None:
        out = compose_lane_user_text("分析这段", {"workbuddy_lane": "paste_code"})
        self.assertIn("【路由·贴码】", out)
        self.assertNotIn("【路由·写码】", out)

    def test_git_review_bits_and_route(self) -> None:
        ctx = {
            "workbuddy_lane": "code_review",
            "git_repo_url": "https://github.com/a/b",
        }
        bits = platform_context_bits("【Git仓库已确认】", ctx)
        self.assertIn("workbuddy_lane=code_review", bits)
        self.assertTrue(any(b.startswith("git_repo_url=") for b in bits))
        body = append_lane_force_routes("【Git仓库已确认】", ctx)
        self.assertIn("【路由·Git 审核】", body)

    def test_ide_review_route(self) -> None:
        body = append_lane_force_routes(
            "【本机工程已确认】",
            {"workbuddy_lane": "code_review", "ide_workspace_root": "/tmp/p"},
        )
        self.assertIn("【路由·IDE 审核】", body)

    def test_mes_entity_no_force_dev(self) -> None:
        out = compose_lane_user_text("今天完工", {"entity": "work_orders"})
        self.assertIn("entity=work_orders", out)
        self.assertNotIn("【路由·写码】", out)
        self.assertNotIn("【路由·贴码】", out)


class StreamBusyContractTests(unittest.IsolatedAsyncioTestCase):
    """与 agent_wrapper.stream_chat 入口契约对齐（忙时 error + code）。"""

    async def test_busy_event_matches_wrapper_contract(self) -> None:
        import asyncio

        lock = asyncio.Lock()
        await lock.acquire()
        try:
            ok = await try_acquire_stream_lock(lock, wait_sec=0.05)
            self.assertFalse(ok)
            ev = stream_busy_event()
            self.assertEqual(ev["type"], "error")
            self.assertEqual(ev["code"], STREAM_BUSY_CODE)
        finally:
            lock.release()


if __name__ == "__main__":
    unittest.main()
