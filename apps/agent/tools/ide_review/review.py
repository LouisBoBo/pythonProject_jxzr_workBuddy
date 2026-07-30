"""IDE 审核编排：mock（默认）或可选 MCP live。"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from tools.ide_review.mock_provider import mock_review_files
from tools.ide_review.mcp_provider import mcp_review_files
from tools.ide_review.paths import resolve_repo_paths

DEFAULT_REVIEW_PATHS = [
    "apps/api/routes/auth.py",
    "apps/web/src/embed.js",
]


def ide_review_mcp_wanted() -> bool:
    return os.getenv("IDE_REVIEW_MCP", "").strip().lower() in ("1", "true", "yes")


def run_ide_review(
    repo_root: Path,
    paths: list[str] | None = None,
    prompt: str = "",
    *,
    provider: str | None = None,
) -> dict[str, Any]:
    """执行一次审核。

    provider:
      - None: 若 IDE_REVIEW_MCP=1 则 mcp，否则 mock
      - "mock" / "mcp": 强制
    """
    files, errors = resolve_repo_paths(
        repo_root, paths, default_paths=DEFAULT_REVIEW_PATHS
    )
    if errors and not files:
        return {
            "status": "error",
            "provider": provider or ("mcp" if ide_review_mcp_wanted() else "mock"),
            "workspace_root": str(repo_root.resolve()),
            "files": [],
            "findings": [],
            "diagnostics_count": {"P0": 0, "P1": 0, "P2": 0},
            "raw_summary": "；".join(errors),
            "errors": errors,
        }

    use = (provider or "").strip().lower()
    if not use:
        use = "mcp" if ide_review_mcp_wanted() else "mock"

    if use == "mcp":
        result = mcp_review_files(repo_root, files, prompt=prompt)
    else:
        result = mock_review_files(repo_root, files, prompt=prompt)

    if errors:
        result = dict(result)
        result["path_warnings"] = errors
    return result
