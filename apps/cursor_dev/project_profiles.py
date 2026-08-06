"""按用户 + 仓库持久化「项目画像」，供新开对话衔接技术栈与风格（不改 jobs 契约）。"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any

from .allowlist import normalize_repo

_REPO_IN_TEXT = re.compile(
    r"(?:https?://github\.com/)?([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)(?:\.git)?",
    re.IGNORECASE,
)


def profiles_root(data_dir: Path) -> Path:
    d = data_dir / "cursor_dev" / "profiles"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _user_dir(data_dir: Path, user_id: str) -> Path:
    safe = "".join(c for c in str(user_id or "anon") if c.isalnum() or c in "-_") or "anon"
    d = profiles_root(data_dir) / safe
    d.mkdir(parents=True, exist_ok=True)
    return d


def _repo_file(data_dir: Path, user_id: str, repo: str) -> Path | None:
    repo = normalize_repo(repo)
    if not repo:
        return None
    safe = repo.replace("/", "__")
    return _user_dir(data_dir, user_id) / f"{safe}.json"


def _meta_path(data_dir: Path, user_id: str) -> Path:
    return _user_dir(data_dir, user_id) / "_meta.json"


def extract_repo_from_text(text: str) -> str:
    s = (text or "").strip()
    if not s:
        return ""
    # 先匹配文本中的 owner/repo，避免「见 xxx/yyy 仓」被整句误当作 repo
    m = _REPO_IN_TEXT.search(s)
    if m:
        return normalize_repo(f"{m.group(1)}/{m.group(2)}")
    return normalize_repo(s)


def get_profile(data_dir: Path, user_id: str, repo: str) -> dict[str, Any] | None:
    path = _repo_file(data_dir, user_id, repo)
    if not path or not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except (OSError, json.JSONDecodeError):
        return None


def get_last_profile(data_dir: Path, user_id: str) -> dict[str, Any] | None:
    meta_path = _meta_path(data_dir, user_id)
    last_repo = ""
    if meta_path.is_file():
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            last_repo = str((meta or {}).get("last_repo") or "")
        except (OSError, json.JSONDecodeError):
            last_repo = ""
    if last_repo:
        hit = get_profile(data_dir, user_id, last_repo)
        if hit:
            return hit
    udir = _user_dir(data_dir, user_id)
    newest: dict[str, Any] | None = None
    newest_ts = -1
    for path in udir.glob("*.json"):
        if path.name.startswith("_"):
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(data, dict):
            continue
        ts = int(data.get("updated_at") or 0)
        if ts >= newest_ts:
            newest_ts = ts
            newest = data
    return newest


def list_profiles(data_dir: Path, user_id: str, *, limit: int = 20) -> list[dict[str, Any]]:
    udir = _user_dir(data_dir, user_id)
    rows: list[dict[str, Any]] = []
    for path in udir.glob("*.json"):
        if path.name.startswith("_"):
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(data, dict) and data.get("repo"):
            rows.append(data)
    rows.sort(key=lambda r: int(r.get("updated_at") or 0), reverse=True)
    return rows[: max(1, min(int(limit or 20), 100))]


def upsert_profile(
    data_dir: Path,
    *,
    user_id: str,
    repo: str,
    tech_stack: str = "",
    frontend: str = "",
    backend: str = "",
    style_notes: str = "",
    selections: dict[str, Any] | None = None,
    selection_labels: dict[str, Any] | None = None,
    notes: str = "",
    last_requirement: str = "",
) -> dict[str, Any]:
    repo = normalize_repo(repo)
    if not repo:
        raise ValueError("repo 无效")
    path = _repo_file(data_dir, user_id, repo)
    assert path is not None
    prev = get_profile(data_dir, user_id, repo) or {}
    now = int(time.time())
    labels = selection_labels if selection_labels is not None else (prev.get("selection_labels") or {})
    stack_bits: list[str] = []
    if isinstance(labels, dict):
        for key in ("backend", "frontend", "render", "stack", "tech"):
            vals = labels.get(key)
            if isinstance(vals, list) and vals:
                stack_bits.extend(str(v) for v in vals if v)
            elif isinstance(vals, str) and vals.strip():
                stack_bits.append(vals.strip())
    tech = (tech_stack or prev.get("tech_stack") or "、".join(stack_bits)).strip()
    profile: dict[str, Any] = {
        "repo": repo,
        "user_id": str(user_id or ""),
        "tech_stack": tech,
        "frontend": (frontend or prev.get("frontend") or "").strip(),
        "backend": (backend or prev.get("backend") or "").strip(),
        "style_notes": (style_notes or prev.get("style_notes") or "").strip(),
        "selections": selections if selections is not None else (prev.get("selections") or {}),
        "selection_labels": labels,
        "notes": (notes if notes is not None else prev.get("notes") or "").strip(),
        "last_requirement": (last_requirement or prev.get("last_requirement") or "").strip()[:2000],
        "created_at": int(prev.get("created_at") or now),
        "updated_at": now,
    }
    if not profile["backend"] and isinstance(labels, dict):
        b = labels.get("backend")
        if isinstance(b, list) and b:
            profile["backend"] = str(b[0])
    if not profile["frontend"] and isinstance(labels, dict):
        for key in ("frontend", "render", "ui"):
            f = labels.get(key)
            if isinstance(f, list) and f:
                profile["frontend"] = str(f[0])
                break
    path.write_text(json.dumps(profile, ensure_ascii=False, indent=2), encoding="utf-8")
    meta_path = _meta_path(data_dir, user_id)
    meta_path.write_text(
        json.dumps({"last_repo": repo, "updated_at": now}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return profile


def profile_prompt_block(profile: dict[str, Any] | None) -> str:
    if not profile or not profile.get("repo"):
        return ""
    lines = [
        "【已锁定项目画像 · 新开窗口请直接衔接，勿重复询问】",
        f"- 仓库：{profile.get('repo')}",
    ]
    if profile.get("tech_stack"):
        lines.append(f"- 技术栈：{profile['tech_stack']}")
    if profile.get("backend"):
        lines.append(f"- 后端：{profile['backend']}")
    if profile.get("frontend"):
        lines.append(f"- 前端/渲染：{profile['frontend']}")
    if profile.get("style_notes"):
        lines.append(f"- 风格约定：{profile['style_notes']}")
    labels = profile.get("selection_labels") or {}
    if isinstance(labels, dict) and labels:
        bits = []
        for k, vals in labels.items():
            if isinstance(vals, list) and vals:
                bits.append(f"{k}={'/'.join(str(v) for v in vals)}")
            elif isinstance(vals, str) and vals.strip():
                bits.append(f"{k}={vals.strip()}")
        if bits:
            lines.append(f"- 历史选项：{'; '.join(bits)}")
    if profile.get("notes"):
        lines.append(f"- 备注：{profile['notes']}")
    if profile.get("last_requirement"):
        lines.append(f"- 最近需求摘要：{str(profile['last_requirement'])[:400]}")
    lines.extend(
        [
            "规则：",
            "1. 技术栈/渲染方式/仓库已锁定：除非用户明确说要更换，否则不要再问、不要再输出这些选项组。",
            "2. 新界面必须与已有登录页/布局保持同一视觉与工程风格（组件、路由、目录结构、命名）。",
            "3. 选项卡只问本轮新增范围（例如首页内容、要不要图表），不要重复已确认项。",
            "4. 输出 :::cursor_dev_propose 时 repo 必须填画像中的仓库。",
            "5. 在正文开头用一两句话确认「沿用已有项目画像」，让用户知道不会推倒重来。",
        ]
    )
    return "\n".join(lines)
