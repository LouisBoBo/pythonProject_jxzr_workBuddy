"""现场读取 GitHub 仓库结构摘要，供新开对话衔接旧项目（不落库画像）。

优先：多分支探测 + 本机写码 job 连续性（同仓上次已确认的技术栈/工作分支）。
"""
from __future__ import annotations

import base64
import os
import re
import urllib.parse
from pathlib import Path
from typing import Any

from .allowlist import normalize_repo
from .github_preflight import _get_json, _github_token, resolve_starting_ref
from . import jobs as job_store


_STACK_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"FastAPI|fastapi", re.I), "Python FastAPI"),
    (re.compile(r"Django|django", re.I), "Django"),
    (re.compile(r"Spring\s*Boot|SpringBoot", re.I), "Java Spring Boot"),
    (re.compile(r"\bNestJS\b|\bExpress\b", re.I), "Node.js"),
    (re.compile(r"\bGin\b", re.I), "Go Gin"),
    (re.compile(r"Vue\s*3|Vue3|\bVue\b", re.I), "Vue"),
    (re.compile(r"\bReact\b", re.I), "React"),
    (re.compile(r"Thymeleaf", re.I), "Thymeleaf"),
    (re.compile(r"Element\s*Plus", re.I), "Element Plus"),
    (re.compile(r"\bVite\b", re.I), "Vite"),
    (re.compile(r"SQLAlchemy", re.I), "SQLAlchemy"),
    (re.compile(r"\bJWT\b", re.I), "JWT"),
]

_BRANCH_RE = re.compile(r"`?((?:dev/wb/|dev/workbuddy/)[A-Za-z0-9._-]+|dev/workbuddy-[A-Za-z0-9._/-]+)`?")


def _file_text(repo: str, path: str, ref: str, max_chars: int = 2500) -> str:
    try:
        data = _get_json(
            f"https://api.github.com/repos/{repo}/contents/{urllib.parse.quote(path)}"
            f"?ref={urllib.parse.quote(ref)}"
        )
    except Exception:
        return ""
    if not isinstance(data, dict) or data.get("type") != "file":
        return ""
    content = data.get("content") or ""
    encoding = (data.get("encoding") or "").lower()
    try:
        if encoding == "base64":
            raw = base64.b64decode(content)
            text = raw.decode("utf-8", errors="replace")
        else:
            text = str(content)
    except Exception:
        return ""
    text = text.strip()
    if len(text) > max_chars:
        return text[:max_chars] + "\n…(截断)"
    return text


def _root_names(repo: str, ref: str) -> list[str]:
    try:
        data = _get_json(
            f"https://api.github.com/repos/{repo}/contents/?ref={urllib.parse.quote(ref)}"
        )
    except Exception:
        return []
    if not isinstance(data, list):
        return []
    names: list[str] = []
    for item in data:
        if isinstance(item, dict) and item.get("name"):
            names.append(str(item["name"]))
    return names[:40]


def _dir_names(repo: str, path: str, ref: str) -> list[str]:
    """列目录下文件/子目录名（失败返回空）。"""
    path = (path or "").strip().strip("/")
    try:
        url = (
            f"https://api.github.com/repos/{repo}/contents/"
            f"{urllib.parse.quote(path)}?ref={urllib.parse.quote(ref)}"
            if path
            else f"https://api.github.com/repos/{repo}/contents/?ref={urllib.parse.quote(ref)}"
        )
        data = _get_json(url)
    except Exception:
        return []
    if not isinstance(data, list):
        return []
    names: list[str] = []
    for item in data:
        if isinstance(item, dict) and item.get("name"):
            names.append(str(item["name"]))
    return names[:60]


_LAYOUT_NAME_RE = re.compile(
    r"^(App|Layout|MainLayout|DefaultLayout|Home|HomeView|Index|Dashboard|Aside|Sidebar|Frame)",
    re.I,
)


def probe_layout_anchors(
    repo: str,
    ref: str,
    *,
    root: list[str] | None = None,
    page_hints: list[str] | None = None,
    limit: int = 8,
) -> list[str]:
    """轻量探测布局/目标页路径。page_hints 命中时优先于通用 App/Home。"""
    repo = normalize_repo(repo)
    ref = (ref or "").strip() or "main"
    if not repo:
        return []
    root_l = {n.lower() for n in (root or _root_names(repo, ref))}
    prefixes: list[str] = []
    if "frontend" in root_l:
        prefixes.append("frontend/")
    if "src" in root_l or "app" in root_l:
        prefixes.append("")
    if not prefixes:
        prefixes = ["frontend/", ""]

    found: list[str] = []
    seen: set[str] = set()
    hints = [str(h).strip() for h in (page_hints or []) if str(h).strip()]

    def _add(path: str) -> None:
        p = path.replace("\\", "/").strip().lstrip("./")
        if not p or p in seen:
            return
        seen.add(p)
        found.append(p)

    def _name_matches_hints(name: str) -> bool:
        low = name.lower()
        for h in hints:
            hl = h.lower()
            if hl and hl in low:
                return True
        return False

    # 0) 页面关键词：先扫 views/pages，命中则置顶（避免先读错 App.vue 浪费回合）
    if hints:
        scan_dirs: list[str] = []
        for pfx in prefixes:
            scan_dirs.extend(
                [
                    f"{pfx}src/views",
                    f"{pfx}src/pages",
                    f"{pfx}src/views/board",
                    f"{pfx}src/views/kanban",
                    f"{pfx}src/views/dashboard",
                ]
            )
        for d in scan_dirs:
            if len(found) >= limit:
                break
            for name in _dir_names(repo, d, ref):
                if not re.search(r"\.(vue|tsx?|jsx?|css|scss)$", name, re.I):
                    continue
                if _name_matches_hints(name):
                    _add(f"{d.rstrip('/')}/{name}")
                    if len(found) >= limit:
                        break

    # 1) 固定候选：存在性用短读探测（有内容才收录）
    candidates: list[str] = []
    for pfx in prefixes:
        candidates.extend(
            [
                f"{pfx}src/App.vue",
                f"{pfx}src/App.tsx",
                f"{pfx}src/layouts/MainLayout.vue",
                f"{pfx}src/layouts/Layout.vue",
                f"{pfx}src/layout/index.vue",
                f"{pfx}src/views/Home.vue",
                f"{pfx}src/views/HomeView.vue",
                f"{pfx}src/views/Dashboard.vue",
                f"{pfx}src/views/Index.vue",
                f"{pfx}src/components/Layout.vue",
            ]
        )
    for path in candidates:
        if len(found) >= limit:
            break
        # 已有页面锚点时，通用壳文件最多再补 2 个
        if hints and sum(1 for p in found if "/views/" in p or "/pages/" in p) >= 1:
            shell_count = sum(
                1
                for p in found
                if re.search(r"/(App|Layout|MainLayout|layout/index)\.", p, re.I)
            )
            if shell_count >= 2 and not re.search(
                r"/(App|Layout|MainLayout|layout/index)\.", path, re.I
            ):
                continue
            if shell_count >= 2:
                break
        if _file_text(repo, path, ref, max_chars=80):
            _add(path)

    # 2) 列目录启发式补锚点
    if len(found) < limit:
        scan_dirs2: list[str] = []
        for pfx in prefixes:
            scan_dirs2.extend(
                [
                    f"{pfx}src",
                    f"{pfx}src/layouts",
                    f"{pfx}src/layout",
                    f"{pfx}src/views",
                ]
            )
        for d in scan_dirs2:
            if len(found) >= limit:
                break
            for name in _dir_names(repo, d, ref):
                if not _LAYOUT_NAME_RE.search(name) and not (
                    hints and _name_matches_hints(name)
                ):
                    continue
                if not re.search(r"\.(vue|tsx?|jsx?|css|scss)$", name, re.I):
                    continue
                _add(f"{d.rstrip('/')}/{name}")
                if len(found) >= limit:
                    break

    return found[:limit]


def _list_branch_names(repo: str, limit: int = 30) -> list[str]:
    try:
        data = _get_json(f"https://api.github.com/repos/{repo}/branches?per_page={limit}")
    except Exception:
        return []
    if not isinstance(data, list):
        return []
    names: list[str] = []
    for item in data:
        if isinstance(item, dict) and item.get("name"):
            names.append(str(item["name"]))
    return names


def extract_stack_labels(text: str) -> list[str]:
    t = str(text or "")
    found: list[str] = []
    seen: set[str] = set()
    for pat, label in _STACK_PATTERNS:
        if pat.search(t) and label not in seen:
            seen.add(label)
            found.append(label)
    return found


def _infer_stack(root: list[str], snippets: dict[str, str]) -> list[str]:
    hints: list[str] = []
    lower = {n.lower() for n in root}
    if "package.json" in lower or "frontend" in lower or "vite.config.js" in lower or "vite.config.ts" in lower:
        hints.append("疑似 Node/前端工程（package.json / frontend / vite）")
    if "requirements.txt" in lower or "pyproject.toml" in lower or "backend" in lower:
        hints.append("疑似 Python 工程（requirements / pyproject / backend）")
    if "pom.xml" in lower or "build.gradle" in lower:
        hints.append("疑似 Java 工程")
    if "go.mod" in lower:
        hints.append("疑似 Go 工程")
    blob = "\n".join(snippets.values())
    hints.extend(extract_stack_labels(blob))
    # de-dupe preserve order
    out: list[str] = []
    seen: set[str] = set()
    for h in hints:
        if h not in seen:
            seen.add(h)
            out.append(h)
    return out


def _is_emptyish(root: list[str], hints: list[str]) -> bool:
    if hints:
        return False
    if not root:
        return True
    meaningful = {
        "package.json",
        "requirements.txt",
        "pyproject.toml",
        "pom.xml",
        "go.mod",
        "frontend",
        "backend",
        "src",
        "app",
        "apps",
    }
    return not any(n.lower() in meaningful for n in root)


def _score_snapshot(root: list[str], hints: list[str], snippets: dict[str, str]) -> int:
    score = len(hints) * 10 + len(root)
    if any(n.lower() in {"frontend", "backend"} for n in root):
        score += 20
    if snippets.get("frontend/package.json") or snippets.get("backend/requirements.txt"):
        score += 15
    if snippets.get("requirements.txt") or snippets.get("package.json"):
        score += 8
    return score


def _snapshot_ref(repo: str, ref: str) -> dict[str, Any]:
    root = _root_names(repo, ref)
    snippets: dict[str, str] = {}
    for path in (
        "README.md",
        "readme.md",
        "package.json",
        "requirements.txt",
        "pyproject.toml",
        "frontend/package.json",
        "backend/requirements.txt",
        "backend/pyproject.toml",
        "app/main.py",
        "backend/app/main.py",
    ):
        text = _file_text(repo, path, ref)
        if text:
            snippets[path] = text
    infer_map = {
        "package.json": snippets.get("package.json") or snippets.get("frontend/package.json") or "",
        "requirements.txt": snippets.get("requirements.txt")
        or snippets.get("backend/requirements.txt")
        or "",
        "README.md": snippets.get("README.md") or snippets.get("readme.md") or "",
        "main.py": snippets.get("app/main.py") or snippets.get("backend/app/main.py") or "",
    }
    hints = _infer_stack(root, {**snippets, **infer_map})
    return {
        "ref": ref,
        "root": root,
        "snippets": snippets,
        "infer_map": infer_map,
        "hints": hints,
        "emptyish": _is_emptyish(root, hints),
        "score": _score_snapshot(root, hints, snippets),
    }


def continuity_from_jobs(
    data_dir: Path | None,
    repo: str,
    *,
    username: str | None = None,
    user_id: str | int | None = None,
    preferred_work_branch: str | None = None,
) -> dict[str, Any]:
    """从本机写码 job 提取同仓最近一次已落地的技术栈与工作分支（不另建画像库）。"""
    empty = {"stack_labels": [], "work_branch": "", "job_id": "", "requirement_snip": ""}
    if data_dir is None:
        return empty
    repo = normalize_repo(repo)
    try:
        all_jobs = job_store.list_jobs(data_dir)
    except Exception:
        return empty

    preferred_status = {
        "idle_for_followup",
        "awaiting_pr_confirm",
        "succeeded",
        "creating_pr",
        "running",
    }
    uid = "" if user_id is None else str(user_id)
    uname = (username or "").strip()
    candidates: list[dict[str, Any]] = []
    for job in all_jobs:
        if normalize_repo(str(job.get("repo") or "")) != repo:
            continue
        status = str(job.get("status") or "")
        msgs = job.get("messages") or []
        blob = "\n".join(str(m.get("content") or "") for m in msgs if isinstance(m, dict))
        blob += "\n" + str(job.get("system_prompt") or "")
        labels = extract_stack_labels(blob)
        # 优先 job.ref（一人一支），再从助手正文里抠旧功能分支
        work_branch = str(job.get("ref") or "").strip()
        if not work_branch or work_branch in {"main", "master"}:
            work_branch = ""
            for m in reversed(msgs):
                if not isinstance(m, dict):
                    continue
                if m.get("role") != "assistant":
                    continue
                hit = _BRANCH_RE.search(str(m.get("content") or ""))
                if hit:
                    work_branch = hit.group(1)
                    break
        user0 = ""
        for m in msgs:
            if isinstance(m, dict) and m.get("role") == "user":
                user0 = str(m.get("content") or "")[:500]
                break
        same_user = False
        if uid and str(job.get("user_id") or "") == uid:
            same_user = True
        if uname and str(job.get("username") or "") == uname:
            same_user = True
        rank = (
            (4 if same_user else 0)
            + (2 if status in preferred_status else 0)
            + (1 if labels else 0)
            + (1 if work_branch else 0)
            + (2 if preferred_work_branch and work_branch == preferred_work_branch else 0)
        )
        candidates.append(
            {
                "job": job,
                "status": status,
                "stack_labels": labels,
                "work_branch": work_branch,
                "requirement_snip": user0,
                "updated_at": int(job.get("updated_at") or 0),
                "rank": rank,
            }
        )

    if not candidates:
        return empty
    candidates.sort(key=lambda c: (c["rank"], c["updated_at"]), reverse=True)
    best = candidates[0]
    # 一人一支：若传入 preferred_work_branch，输出时优先该名（即使历史任务还是旧功能分支）
    out_branch = preferred_work_branch or best["work_branch"]
    return {
        "stack_labels": best["stack_labels"],
        "work_branch": out_branch or best["work_branch"],
        "job_id": str(best["job"].get("id") or ""),
        "requirement_snip": best["requirement_snip"],
        "status": best["status"],
        "legacy_branch": best["work_branch"] if preferred_work_branch and best["work_branch"] != preferred_work_branch else "",
    }


def inspect_repo(
    repo: str,
    preferred_ref: str | None = None,
    *,
    data_dir: Path | None = None,
    username: str | None = None,
    user_id: str | int | None = None,
    branch_prefix: str = "dev/wb/",
) -> dict[str, Any]:
    """返回 {ok, repo, ref, summary, prompt_block, treat_as_new, locked_stack, ...}。"""
    from .user_branch import user_work_branch

    repo = normalize_repo(repo)
    if not repo:
        return {
            "ok": False,
            "error": "仓库格式无效",
            "repo": "",
            "ref": "",
            "summary": "",
            "prompt_block": "",
            "treat_as_new": True,
            "locked_stack": [],
        }

    preferred_work = user_work_branch(
        branch_prefix=branch_prefix,
        username=username,
        user_id=user_id,
        fixed_branch=os.getenv("CURSOR_DEV_WORK_BRANCH") or "",
    )
    continuity = continuity_from_jobs(
        data_dir,
        repo,
        username=username,
        user_id=user_id,
        preferred_work_branch=preferred_work,
    )
    # 读仓探测顺序：用户固定分支 → 历史功能分支 → 默认分支
    legacy = str(continuity.get("legacy_branch") or "").strip()
    preferred_ref = (preferred_ref or "").strip() or None
    probe_first = preferred_ref or preferred_work or None

    pre = resolve_starting_ref(repo, probe_first)
    if not pre.get("ok"):
        # GitHub 读失败时，若本机 job 已有技术栈，仍可衔接（避免又问一遍）
        if continuity.get("stack_labels"):
            locked = continuity["stack_labels"]
            stack_line = "、".join(locked)
            branch = preferred_work or continuity.get("work_branch") or preferred_ref or "main"
            summary = (
                f"仓库 {repo}（GitHub 预检失败：{pre.get('error')}）\n"
                f"根据本仓最近写码任务锁定技术栈：{stack_line}\n"
                f"固定工作分支（一人一支）：{preferred_work}\n"
                + (f"历史功能分支（仅作代码来源）：{legacy}\n" if legacy else "")
            )
            prompt_block = (
                "【已有项目 · 技术栈已锁定 · 禁止再问技术栈】\n"
                f"{summary}\n"
                "规则：\n"
                f"1. 已锁定技术栈：{stack_line}。绝对不要再输出技术栈选项组。\n"
                f"2. 写码必须落在固定分支 `{preferred_work}`（一人一支），禁止再开功能后缀分支。\n"
                "3. 正文最多 1～2 句；未决点只用 :::cursor_dev_options 问本轮增量。\n"
                f"4. :::cursor_dev_propose 的 repo 填 `{repo}`，ref 填 `{preferred_work}`。\n"
                "5. 新界面与已有登录页同风格；不要自动开 PR（除非用户要求）。"
            )
            return {
                "ok": True,
                "repo": repo,
                "ref": branch,
                "sha": None,
                "root": [],
                "stack_hints": locked,
                "locked_stack": locked,
                "treat_as_new": False,
                "summary": summary,
                "prompt_block": prompt_block,
                "error": None,
                "authenticated": bool(_github_token()),
                "continuity_job_id": continuity.get("job_id"),
                "work_branch": preferred_work,
                "legacy_branch": legacy,
            }
        return {
            "ok": False,
            "error": pre.get("error") or "无法读取仓库",
            "repo": repo,
            "ref": "",
            "summary": "",
            "prompt_block": "",
            "treat_as_new": True,
            "locked_stack": [],
        }

    default_ref = str(pre.get("ref") or preferred_ref or "main")
    candidate_refs: list[str] = []
    for r in (
        preferred_work,
        legacy,
        preferred_ref,
        continuity.get("work_branch"),
        default_ref,
        pre.get("default_branch"),
        "main",
        "master",
    ):
        s = str(r or "").strip()
        if s and s not in candidate_refs:
            candidate_refs.append(s)
    # 补扫少量旧功能分支，便于从历史 tip 读栈
    if not continuity.get("stack_labels"):
        for name in _list_branch_names(repo, limit=15):
            if (name.startswith("dev/workbuddy-") or name.startswith("dev/wb/")) and name not in candidate_refs:
                candidate_refs.append(name)
            if len(candidate_refs) >= 8:
                break

    snapshots = [_snapshot_ref(repo, r) for r in candidate_refs[:8]]
    snapshots.sort(key=lambda s: s["score"], reverse=True)
    best = snapshots[0] if snapshots else _snapshot_ref(repo, default_ref)

    locked: list[str] = []
    for label in continuity.get("stack_labels") or []:
        if label not in locked:
            locked.append(label)
    for label in best.get("hints") or []:
        # keep concrete labels, skip vague 疑似
        if label.startswith("疑似"):
            continue
        if label not in locked:
            locked.append(label)

    emptyish = bool(best.get("emptyish")) and not locked
    treat_as_new = emptyish and not locked

    ref = str(best.get("ref") or default_ref)
    root = list(best.get("root") or [])
    infer_map = best.get("infer_map") or {}
    hints = list(best.get("hints") or [])
    if locked:
        for label in locked:
            if label not in hints:
                hints.append(label)

    lines = [
        f"仓库 {repo}（读码参考 @{ref}）",
        f"固定工作分支（一人一支）：{preferred_work}",
        f"根目录文件：{', '.join(root) if root else '（空或不详）'}",
    ]
    if legacy and legacy != preferred_work:
        lines.append(f"历史功能分支（代码来源，勿再新开同类分支）：{legacy}")
    if locked:
        lines.append("已锁定技术栈（禁止再问）：" + "、".join(locked))
    elif hints:
        lines.append("技术栈线索：" + "；".join(hints))
    if continuity.get("requirement_snip"):
        lines.append("前序需求摘要：\n" + str(continuity["requirement_snip"])[:400])
    if infer_map.get("README.md"):
        lines.append("README 摘要：\n" + infer_map["README.md"][:500])
    if treat_as_new:
        lines.append("判定：各探测分支几乎无工程文件，且无前序写码技术栈 → 按新项目收集技术栈。")
    else:
        lines.append("判定：沿用已有技术栈与风格；写码落在固定用户分支，手动合 main。")
    summary = "\n".join(lines)

    layout_anchors: list[str] = []
    if not treat_as_new:
        try:
            layout_anchors = probe_layout_anchors(repo, ref, root=root, limit=8)
        except Exception:
            layout_anchors = []
        if layout_anchors:
            lines.append("布局锚点（写码优先打开）：" + "、".join(layout_anchors[:8]))
            summary = "\n".join(lines)

    if treat_as_new:
        prompt_block = (
            "【本会话已选定仓库 · 确为空仓新项目】\n"
            f"{summary}\n"
            "规则：\n"
            "1. 正文最多 1～2 句，然后必须输出 :::cursor_dev_options。\n"
            "2. 选项卡须含技术栈 + 本轮范围；不要问仓库地址。\n"
            f"3. :::cursor_dev_propose 的 repo 填 `{repo}`，ref 填 `{preferred_work}`。\n"
            f"4. 写码必须使用固定分支 `{preferred_work}`（一人一支），禁止功能后缀分支；不要自动开 PR。\n"
            "5. 禁止用表格/A~D 让用户打字。"
        )
    else:
        stack_line = "、".join(locked) if locked else "（见仓库现有工程）"
        fork_hint = (
            f"若 `{preferred_work}` 尚不存在，从有代码的分支 `{ref}` 创建 `{preferred_work}` 再改。"
            if ref != preferred_work
            else f"在 `{preferred_work}` 上继续提交。"
        )
        anchor_rule = ""
        if layout_anchors:
            anchor_rule = (
                "6. 纯样式/滚动/布局壳需求：requirement 开头写【任务档位：css_layout】，"
                "并尽量带上布局锚点路径："
                + "、".join(f"`{p}`" for p in layout_anchors[:6])
                + "。\n"
            )
        prompt_block = (
            "【已有项目 · 技术栈已锁定 · 一人一支 · 禁止再问技术栈】\n"
            f"{summary}\n"
            "规则：\n"
            f"1. 已锁定技术栈：{stack_line}。不要再问/输出技术栈选项组。\n"
            f"2. 写码固定分支：`{preferred_work}`。{fork_hint} 严禁再开 dev/workbuddy-功能名-xxxx。\n"
            "3. 增量须与已有登录页同风格；正文最多 1～2 句；未决点只用范围类 :::cursor_dev_options。\n"
            f"4. :::cursor_dev_propose 的 repo 填 `{repo}`，ref 填 `{preferred_work}`。\n"
            "5. 不要自动开 PR（用户手动合 main）；禁止表格/A~D 打字作答。\n"
            f"{anchor_rule}"
        )

    return {
        "ok": True,
        "repo": repo,
        "ref": preferred_work,
        "code_ref": ref,
        "sha": pre.get("sha"),
        "root": root,
        "stack_hints": hints,
        "locked_stack": locked,
        "treat_as_new": treat_as_new,
        "summary": summary,
        "prompt_block": prompt_block,
        "layout_anchors": layout_anchors,
        "error": None,
        "authenticated": bool(_github_token()),
        "continuity_job_id": continuity.get("job_id"),
        "work_branch": preferred_work,
        "legacy_branch": legacy,
        "probed_refs": [s.get("ref") for s in snapshots],
    }
