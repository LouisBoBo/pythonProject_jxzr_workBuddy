"""一用户一工作分支：命名与解析。"""
from __future__ import annotations

import re


_SAFE_RE = re.compile(r"[^a-zA-Z0-9._-]+")


def sanitize_user_slug(username: str | None, user_id: str | int | None = None) -> str:
    """Git 分支安全段：优先用户名，否则 u{id}。"""
    raw = (username or "").strip()
    if not raw and user_id not in (None, ""):
        raw = f"u{user_id}"
    if not raw:
        raw = "anon"
    # 去掉邮箱域名等
    if "@" in raw:
        raw = raw.split("@", 1)[0]
    raw = raw.replace(" ", "-").replace("/", "-")
    slug = _SAFE_RE.sub("-", raw).strip(".-_")
    if not slug:
        slug = f"u{user_id}" if user_id not in (None, "") else "anon"
    return slug[:64]


def user_work_branch(
    *,
    branch_prefix: str,
    username: str | None = None,
    user_id: str | int | None = None,
    fixed_branch: str | None = None,
) -> str:
    """固定工作分支名。

    - ``fixed_branch``（环境 CURSOR_DEV_WORK_BRANCH）优先：整机/单仓固定一支，如 ``hebo``。
    - 前缀为空：分支名即为用户名 slug（``hebo`` / ``admin``）。
    - 默认前缀 ``dev/wb/`` → ``dev/wb/admin``。
    """
    fixed = (fixed_branch or "").strip().strip("/")
    if fixed:
        return fixed
    prefix = (branch_prefix or "").strip()
    slug = sanitize_user_slug(username, user_id)
    if not prefix:
        return slug
    if prefix.endswith("/") or prefix.endswith("-") or prefix.endswith("_"):
        return f"{prefix}{slug}"
    return f"{prefix}/{slug}"
