"""本机写码：相对 import 落盘校验（防 Vite Failed to resolve）。"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

# from './x' | import './x' | import('./x') | require('./x')
_REL_IMPORT_RE = re.compile(
    r"""(?<![\w$])(?:import\s*\(\s*|from\s+|import\s+|require\s*\(\s*)"""
    r"""['"](\.[^'"]+)['"]""",
)

_SCAN_SUFFIXES = {".vue", ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs"}

_FILE_EXTS = (".js", ".ts", ".vue", ".jsx", ".tsx", ".mjs", ".cjs", ".json")
_INDEX_NAMES = (
    "index.js",
    "index.ts",
    "index.vue",
    "index.jsx",
    "index.tsx",
    "index.mjs",
)


def _strip_query_hash(spec: str) -> str:
    s = (spec or "").strip()
    for sep in ("?", "#"):
        if sep in s:
            s = s.split(sep, 1)[0]
    return s


def resolve_relative_import(importer: Path, spec: str) -> Path | None:
    """按 Node/Vite 常见规则解析相对模块；找不到返回 None。"""
    raw = _strip_query_hash(spec)
    if not raw.startswith("."):
        return None
    base = (importer.parent / raw).resolve()
    candidates: list[Path] = [base]
    for ext in _FILE_EXTS:
        candidates.append(Path(str(base) + ext))
    for name in _INDEX_NAMES:
        candidates.append(base / name)
    seen: set[str] = set()
    for cand in candidates:
        key = str(cand)
        if key in seen:
            continue
        seen.add(key)
        try:
            if cand.is_file():
                return cand
        except OSError:
            continue
    return None


def extract_relative_specs(source: str) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for m in _REL_IMPORT_RE.finditer(source or ""):
        spec = (m.group(1) or "").strip()
        if not spec or spec in seen:
            continue
        seen.add(spec)
        out.append(spec)
    return out


def check_file_relative_imports(
    sandbox: Path,
    rel_path: str,
) -> list[dict[str, Any]]:
    """检查单个沙箱相对文件；返回破损 import 列表。"""
    root = Path(sandbox).resolve()
    rel = str(rel_path or "").replace("\\", "/").lstrip("./")
    if not rel:
        return []
    suffix = Path(rel).suffix.lower()
    if suffix not in _SCAN_SUFFIXES:
        return []
    target = (root / rel).resolve()
    try:
        target.relative_to(root)
    except ValueError:
        return []
    if not target.is_file():
        return []
    try:
        text = target.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []

    issues: list[dict[str, Any]] = []
    for spec in extract_relative_specs(text):
        raw = _strip_query_hash(spec)
        if not raw.startswith("."):
            continue
        # 先约束在沙箱内再探测 is_file，避免相对路径逃逸做宿主机探测
        try:
            tentative = (target.parent / raw).resolve()
            tentative.relative_to(root)
        except (OSError, ValueError):
            issues.append(
                {
                    "file": rel,
                    "import": spec,
                    "hint": "相对路径逃出沙箱，禁止。",
                }
            )
            continue
        resolved = resolve_relative_import(target, spec)
        if resolved is None:
            issues.append(
                {
                    "file": rel,
                    "import": spec,
                    "hint": (
                        "相对路径解析失败：请按「当前文件目录」数清 ../ 层数，"
                        "或改用工程别名（如 @/api/...）并确保目标文件已写入。"
                    ),
                }
            )
            continue
        try:
            resolved.relative_to(root)
        except ValueError:
            issues.append(
                {
                    "file": rel,
                    "import": spec,
                    "hint": "相对路径逃出沙箱，禁止。",
                }
            )
    return issues


def find_broken_relative_imports(
    sandbox: Path,
    rel_files: list[str] | None = None,
) -> list[dict[str, Any]]:
    """扫描变更文件（或整仓前端常见后缀）中的破损相对 import。"""
    root = Path(sandbox).resolve()
    files = [str(p).replace("\\", "/").lstrip("./") for p in (rel_files or []) if str(p).strip()]
    if not files:
        return []
    issues: list[dict[str, Any]] = []
    seen_pair: set[tuple[str, str]] = set()
    for rel in files:
        for item in check_file_relative_imports(root, rel):
            key = (item["file"], item["import"])
            if key in seen_pair:
                continue
            seen_pair.add(key)
            issues.append(item)
    return issues


def format_repair_prompt(issues: list[dict[str, Any]]) -> str:
    if not issues:
        return ""
    lines = [
        "【闸门失败 · 相对 import 无法解析】以下写法会让 Vite/打包直接红屏，必须立刻修好再收工：",
        "",
    ]
    for i, item in enumerate(issues[:30], 1):
        lines.append(
            f"{i}. 文件 `{item['file']}` 中的 `{item['import']}` → {item.get('hint') or '目标不存在'}"
        )
    lines.extend(
        [
            "",
            "硬性要求：",
            "- 只修 import 路径或补写缺失模块文件，禁止无关大改。",
            "- 从 `src/views/kanban/Xxx.vue` 引用 `src/api/foo` 必须是 `../../api/foo`（两层），"
            "不是 `../api/foo`（那会落到 `src/views/api`）。",
            "- 优先与仓库已有页面同风格：若其它视图用 `@/api/...`，新建页也用别名。",
            "- 修好后可用 list_dir/read_file 核对目标文件确实存在。",
        ]
    )
    return "\n".join(lines)
