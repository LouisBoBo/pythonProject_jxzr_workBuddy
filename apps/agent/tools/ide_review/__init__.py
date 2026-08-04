"""IDE 代码审核（M0/M1）。

默认不挂到 Agent；仅当 Config.IDE_REVIEW_ENABLED 时由 create_agent 追加工具。
本机文件经 Bridge 读取：list → 分批 read → review / git_review。
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
