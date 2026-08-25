#!/usr/bin/env python3
"""无 LLM / 无外网：依赖降级文案与分级契约。"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AGENT = ROOT / "apps" / "agent"
sys.path.insert(0, str(AGENT))


def main() -> None:
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromName("test_dependency_status")
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    if not result.wasSuccessful():
        raise SystemExit(1)
    print("OK   smoke-dependency-degrade")


if __name__ == "__main__":
    main()
