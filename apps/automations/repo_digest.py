"""本周 ZR WorkBuddy 仓库变更依据（供周报自动化，禁止 Agent 臆造）。"""
from __future__ import annotations

import logging
import subprocess
from datetime import datetime, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)

_MAX_COMMITS = 40
_MAX_FILES = 80


def _repo_root(cwd: str | None = None) -> Path | None:
    if cwd:
        p = Path(cwd).expanduser().resolve()
        if p.is_dir():
            return p
    default = Path(__file__).resolve().parents[2]
    try:
        import sys

        agent_dir = default / "apps" / "agent"
        agent_str = str(agent_dir)
        if agent_dir.is_dir() and agent_str not in sys.path:
            sys.path.insert(0, agent_str)
        from bundle_root import resolve_repo_root

        return resolve_repo_root()
    except Exception:
        return default


def _run_git(repo: Path, *args: str, timeout: int = 30) -> tuple[int, str, str]:
    try:
        proc = subprocess.run(
            ["git", *args],
            cwd=str(repo),
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        out = (proc.stdout or "").strip()
        err = (proc.stderr or "").strip()
        return proc.returncode, out, err
    except (OSError, subprocess.TimeoutExpired) as exc:
        return 1, "", f"{type(exc).__name__}: {exc}"


def _week_start_date() -> str:
    """本周一 00:00（本地）。"""
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    monday = today - timedelta(days=today.weekday())
    return monday.strftime("%Y-%m-%d")


def build_weekly_repo_digest(cwd: str | None = None) -> str:
    """拉取本周 git 提交与变更文件，作为周报唯一可信依据。"""
    repo = _repo_root(cwd)
    if repo is None:
        return (
            "【本周代码变更依据】\n"
            "无法定位 ZR WorkBuddy 仓库根目录；本周已完成工作请如实写「暂无代码依据」，勿编造功能。\n"
        )

    code, inside, _ = _run_git(repo, "rev-parse", "--is-inside-work-tree")
    if code != 0 or inside.lower() != "true":
        return (
            f"【本周代码变更依据】\n"
            f"目录 {repo} 不是 git 仓库；本周已完成工作请如实写「暂无代码提交记录」，勿编造。\n"
        )

    since = _week_start_date()
    today = datetime.now().strftime("%Y-%m-%d")

    code, log_out, log_err = _run_git(
        repo,
        "log",
        f"--since={since}",
        "--until=2099-01-01",
        "--no-merges",
        f"--max-count={_MAX_COMMITS}",
        "--pretty=format:%h|%ad|%an|%s",
        "--date=short",
    )
    commits: list[dict[str, str]] = []
    if code == 0 and log_out:
        for line in log_out.splitlines():
            parts = line.split("|", 3)
            if len(parts) == 4:
                commits.append(
                    {
                        "hash": parts[0],
                        "date": parts[1],
                        "author": parts[2],
                        "subject": parts[3],
                    }
                )

    code, files_out, _ = _run_git(
        repo,
        "log",
        f"--since={since}",
        "--no-merges",
        "--name-only",
        "--pretty=format:",
    )
    files: list[str] = []
    if code == 0 and files_out:
        seen: set[str] = set()
        for line in files_out.splitlines():
            p = line.strip()
            if not p or p in seen:
                continue
            seen.add(p)
            files.append(p)
            if len(files) >= _MAX_FILES:
                break

    code, shortstat, _ = _run_git(
        repo,
        "log",
        f"--since={since}",
        "--no-merges",
        "--shortstat",
        "--pretty=format:",
    )
    insertions = 0
    deletions = 0
    if code == 0 and shortstat:
        import re

        for m in re.finditer(r"(\d+)\s+insertion", shortstat):
            insertions += int(m.group(1))
        for m in re.finditer(r"(\d+)\s+deletion", shortstat):
            deletions += int(m.group(1))

    lines = [
        "【本周代码变更依据 · 来自 git，周报只能据此归纳，禁止编造】",
        f"仓库：{repo}",
        f"统计窗口：{since} ～ {today}（本周一至今日）",
        f"提交数：{len(commits)}；变更文件（去重）：{len(files)}；约 +{insertions}/-{deletions} 行",
        "",
    ]

    if commits:
        lines.append("提交列表（hash|日期|作者|说明）：")
        for c in commits:
            lines.append(f"- {c['hash']} | {c['date']} | {c['author']} | {c['subject']}")
    else:
        lines.append("提交列表：本周（自周一起）暂无 git 提交。")

    if files:
        lines.append("")
        lines.append("主要变更文件（节选）：")
        for f in files[:_MAX_FILES]:
            lines.append(f"- {f}")
        if len(files) > _MAX_FILES:
            lines.append(f"- … 另有 {len(files) - _MAX_FILES} 个文件")

    code, status_out, _ = _run_git(repo, "status", "--porcelain")
    pending: list[str] = []
    if code == 0 and status_out:
        for line in status_out.splitlines()[:40]:
            p = line[3:].strip() if len(line) > 3 else line.strip()
            if p:
                pending.append(p)
    if pending:
        lines.append("")
        lines.append("工作区未提交变更（节选，亦属本周工作依据）：")
        for p in pending[:40]:
            lines.append(f"- {p}")
        code, diff_stat, _ = _run_git(repo, "diff", "--stat", "HEAD")
        if code == 0 and diff_stat:
            lines.append(f"未提交 diff 统计：{diff_stat.splitlines()[-1] if diff_stat.splitlines() else diff_stat}")

    if log_err and not commits:
        lines.append("")
        lines.append(f"（git log 提示：{log_err[:200]}）")

    lines.append("")
    lines.append(
        "归纳规则：每条「已完成工作」须能对应上述提交、变更文件或未提交路径；"
        "勿写 MES 查数/接口探活等运维操作冒充本周产品开发；无依据则写「本周无代码变更」。"
    )
    return "\n".join(lines)
