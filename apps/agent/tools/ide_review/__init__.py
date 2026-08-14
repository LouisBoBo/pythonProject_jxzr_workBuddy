"""IDE / Git 代码审核工具。

- request_git_*：默认挂到 Agent（公开 HTTPS 仓审核；桌面不依赖 IDE_REVIEW_ENABLED）
- request_ide_*：仅当 Config.IDE_REVIEW_ENABLED 时由 create_agent 追加（VS Code Bridge）
"""
from tools.ide_review.review import DEFAULT_REVIEW_PATHS, run_ide_review
from tools.ide_review.tool import (
    request_git_list_source_files,
    request_git_read_batch,
    request_git_review,
    request_ide_list_source_files,
    request_ide_read_batch,
    request_ide_read_files,
    request_ide_review,
)

__all__ = [
    "DEFAULT_REVIEW_PATHS",
    "run_ide_review",
    "request_ide_review",
    "request_ide_list_source_files",
    "request_ide_read_batch",
    "request_ide_read_files",
    "request_git_review",
    "request_git_list_source_files",
    "request_git_read_batch",
]
