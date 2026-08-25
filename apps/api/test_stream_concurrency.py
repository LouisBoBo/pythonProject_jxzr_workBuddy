"""stream_concurrency 单测：忙时快速失败、空闲可抢锁。"""
from __future__ import annotations

import asyncio
import unittest

from stream_concurrency import (
    STREAM_BUSY_CODE,
    stream_busy_event,
    try_acquire_stream_lock,
)


class StreamConcurrencyTests(unittest.IsolatedAsyncioTestCase):
    async def test_acquire_when_free(self) -> None:
        lock = asyncio.Lock()
        ok = await try_acquire_stream_lock(lock, wait_sec=0.05)
        self.assertTrue(ok)
        self.assertTrue(lock.locked())
        lock.release()

    async def test_busy_fails_fast(self) -> None:
        lock = asyncio.Lock()
        await lock.acquire()
        try:
            ok = await try_acquire_stream_lock(lock, wait_sec=0.05)
            self.assertFalse(ok)
        finally:
            lock.release()

    async def test_busy_event_shape(self) -> None:
        ev = stream_busy_event()
        self.assertEqual(ev["type"], "error")
        self.assertEqual(ev["code"], STREAM_BUSY_CODE)
        self.assertIn("一路对话", ev["text"])


if __name__ == "__main__":
    unittest.main()
