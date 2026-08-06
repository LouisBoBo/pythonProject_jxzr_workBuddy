"""Unit checks for cursor_dev allowlist + config (no live Cursor API)."""
from __future__ import annotations

import os
import sys
from pathlib import Path

APPS = Path(__file__).resolve().parents[1] / "apps"
sys.path.insert(0, str(APPS))

from cursor_dev.allowlist import is_allowed, normalize_repo, parse_allowlist  # noqa: E402
from cursor_dev.config import reload_config  # noqa: E402


def test_normalize() -> None:
    assert normalize_repo("LouisBoBo/py") == "LouisBoBo/py"
    assert normalize_repo("https://github.com/LouisBoBo/py") == "LouisBoBo/py"
    assert normalize_repo("https://github.com/LouisBoBo/py.git") == "LouisBoBo/py"
    assert normalize_repo("git@github.com:LouisBoBo/py.git") == "LouisBoBo/py"


def test_allowlist_url_and_slug() -> None:
    repos = parse_allowlist(
        "https://github.com/LouisBoBo/py, other/org, LouisBoBo/py"
    )
    assert repos == ["LouisBoBo/py", "other/org"]
    assert is_allowed("https://github.com/LouisBoBo/py", repos)
    assert is_allowed("LouisBoBo/py", repos)
    assert not is_allowed("evil/repo", repos)


def test_availability_without_key() -> None:
    os.environ["CURSOR_DEV_ENABLED"] = "1"
    os.environ.pop("CURSOR_API_KEY", None)
    os.environ["CURSOR_DEV_REPO_ALLOWLIST"] = "LouisBoBo/py"
    cfg = reload_config()
    ok, reason = cfg.availability()
    assert ok is False
    assert "CURSOR_API_KEY" in reason


def test_availability_allowlist_optional() -> None:
    os.environ["CURSOR_DEV_ENABLED"] = "1"
    os.environ["CURSOR_API_KEY"] = "crsr_test"
    os.environ["CURSOR_DEV_REPO_ALLOWLIST"] = ""
    cfg = reload_config()
    # 无 sdk 时仍可能 false，但原因不应再是「未配置白名单」
    ok, reason = cfg.availability()
    assert "ALLOWLIST" not in reason.upper()
    if not ok:
        assert "cursor-sdk" in reason or "CURSOR" in reason


def main() -> int:
    test_normalize()
    test_allowlist_url_and_slug()
    test_availability_without_key()
    test_availability_allowlist_optional()
    print("smoke_cursor_dev_d1: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
