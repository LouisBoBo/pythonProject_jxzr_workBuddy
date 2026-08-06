"""仓库白名单：统一为 owner/repo，并接受常见 Git URL。"""
from __future__ import annotations

import re
from urllib.parse import urlparse


_SSH_RE = re.compile(r"^git@([^:]+):(.+)$", re.IGNORECASE)


def normalize_repo(raw: str) -> str:
    """将 URL / SSH / owner/repo 规范为 ``owner/repo``（小写 owner 保持原样大小写）。"""
    s = (raw or "").strip().strip('"').strip("'")
    if not s:
        return ""

    m = _SSH_RE.match(s)
    if m:
        s = m.group(2)

    if "://" in s:
        parsed = urlparse(s)
        path = (parsed.path or "").lstrip("/")
        s = path

    s = s.removesuffix(".git").strip("/")
    parts = [p for p in s.split("/") if p]
    if len(parts) < 2:
        return ""
    return f"{parts[0]}/{parts[1]}"


def parse_allowlist(csv: str) -> list[str]:
    """解析逗号分隔白名单，去重且保持顺序。"""
    seen: set[str] = set()
    out: list[str] = []
    for chunk in (csv or "").split(","):
        repo = normalize_repo(chunk)
        if not repo or repo in seen:
            continue
        seen.add(repo)
        out.append(repo)
    return out


def is_allowed(repo: str, allowlist: list[str]) -> bool:
    """空白名单 = 不限制；非空则必须命中。"""
    target = normalize_repo(repo)
    if not target:
        return False
    if not allowlist:
        return True
    allowed = {normalize_repo(x) for x in allowlist if normalize_repo(x)}
    return target in allowed
