"""本机工作区安全读文件（供 Python Bridge 与冒烟复用）。"""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

# 单文件 / 总字节 / 文件数上限（单批读；全仓用 list + 多批循环）
MAX_FILE_BYTES = int(os.getenv("IDE_BRIDGE_MAX_FILE_BYTES", str(80 * 1024)))
MAX_TOTAL_BYTES = int(os.getenv("IDE_BRIDGE_MAX_TOTAL_BYTES", str(320 * 1024)))
MAX_FILES = int(os.getenv("IDE_BRIDGE_MAX_FILES", "5"))
BATCH_SIZE = int(os.getenv("IDE_BRIDGE_BATCH_SIZE", "5") or "5")
MAX_REPO_FILES = int(os.getenv("IDE_BRIDGE_MAX_REPO_FILES", "200") or "200")

# 仅功能/业务源码后缀（配置、锁文件、样式、文档不进审核队列）
_CODE_SUFFIXES = {
    ".java",
    ".cs",
    ".js",
    ".jsx",
    ".ts",
    ".tsx",
    ".vue",
    ".py",
    ".go",
    ".kt",
    ".kts",
    ".rs",
    ".php",
    ".rb",
    ".swift",
    ".c",
    ".cc",
    ".cpp",
    ".h",
    ".hpp",
    ".scala",
    ".groovy",
    ".sql",
}
_SKIP_DIRS = {
    ".git",
    "node_modules",
    "target",
    "bin",
    "obj",
    "dist",
    "build",
    "vendor",
    "__pycache__",
    ".idea",
    ".vs",
    "packages",
    "coverage",
    ".next",
    ".nuxt",
    "unpackage",
    "miniprogram_npm",
    "uni_modules",
    "wxcomponents",
    "nativeplugins",
    "uview-ui",
    "uview-plus",
    "colorui",
    "tuniao-ui",
    "static",
    "assets",
    "public",
    "locale",
    "locales",
    "i18n",
    "mock",
    "mocks",
    "fixtures",
    "__tests__",
    "e2e",
}
# 仅在仓库根或 src/ 下跳过（避免误伤 com/example 等业务包名）
_SKIP_DIRS_AT_SRC_OR_ROOT = {
    "test",
    "tests",
    "example",
    "examples",
    "docs",
    "doc",
}
_SKIP_BASENAMES = {
    "package-lock.json",
    "yarn.lock",
    "pnpm-lock.yaml",
    "composer.lock",
    "Gemfile.lock",
    "poetry.lock",
    "Cargo.lock",
    "package.json",
    "pom.xml",
    "build.gradle",
    "build.gradle.kts",
    "settings.gradle",
    "requirements.txt",
    "pyproject.toml",
    "go.mod",
    "go.sum",
    "Cargo.toml",
    "manifest.json",
    "pages.json",
    "Dockerfile",
    "docker-compose.yml",
    "docker-compose.yaml",
    "application.properties",
    "application.yml",
    "application.yaml",
    "appsettings.json",
    "vue.config.js",
    "vite.config.js",
    "vite.config.ts",
    "webpack.config.js",
    "babel.config.js",
    "babel.config.cjs",
    "jest.config.js",
    "jest.config.ts",
    "jsconfig.json",
    "tsconfig.json",
    "tsconfig.node.json",
    "project.config.json",
    "project.private.config.json",
    "uni.promisify.adaptor.js",
    "uni.scss",
    "README.md",
    "LICENSE",
    "CHANGELOG.md",
    "AGENTS.md",
    ".eslintrc.js",
    ".eslintrc.cjs",
    ".prettierrc",
    ".prettierrc.js",
    "prettier.config.js",
}
_SKIP_NAME_RE = re.compile(
    r"("
    r"\.(min|bundle)\.js$"
    r"|\.d\.ts$"
    r"|\.(test|spec)\.(js|jsx|ts|tsx)$"
    r"|(^|/)(mock|mocks|__mocks__)(/|$)"
    r"|(^|/)(locale|locales|i18n)(/|$)"
    r"|(^|/)(static|assets|public)(/|$)"
    r"|\.(css|scss|sass|less|styl)$"
    r"|\.(md|map|lock)$"
    r"|\.(json|yml|yaml|toml|properties|xml|gradle)$"
    r")",
    re.I,
)

# 敏感文件名（basename）与后缀：拒绝读入审核上下文
_SENSITIVE_BASENAMES = {
    ".env",
    ".env.local",
    ".env.production",
    ".env.development",
    ".env.staging",
    "id_rsa",
    "id_dsa",
    "id_ecdsa",
    "id_ed25519",
    "credentials.json",
    "service-account.json",
    "secrets.json",
    ".npmrc",
    ".pypirc",
}
_SENSITIVE_SUFFIXES = {
    ".pem",
    ".key",
    ".p12",
    ".pfx",
    ".jks",
    ".keystore",
}
_SENSITIVE_NAME_RE = re.compile(
    r"(^|/)(\.env(\.|$)|.*\.(pem|key|p12|pfx|jks)|id_(rsa|dsa|ecdsa|ed25519)|credentials\.json)$",
    re.I,
)


def is_sensitive_rel(rel: str) -> str | None:
    """若敏感则返回拒绝原因，否则 None。"""
    r = (rel or "").replace("\\", "/").strip()
    if not r:
        return None
    base = Path(r).name
    if base in _SENSITIVE_BASENAMES:
        return f"拒绝读取敏感文件: {rel}"
    low = base.lower()
    for suf in _SENSITIVE_SUFFIXES:
        if low.endswith(suf):
            return f"拒绝读取敏感文件: {rel}"
    if _SENSITIVE_NAME_RE.search(r):
        return f"拒绝读取敏感文件: {rel}"
    return None


def to_workspace_relative(workspace_root: Path, raw: str) -> tuple[str | None, str | None]:
    """返回 (relative_posix, error)。允许相对路径或位于 workspace 下的绝对路径。"""
    root = workspace_root.resolve()
    s = (raw or "").strip()
    if not s:
        return None, "空路径"
    p = Path(s)
    if p.is_absolute():
        try:
            cand = p.resolve()
            rel = cand.relative_to(root)
        except Exception:
            return None, f"路径不在工作区内: {s}"
    else:
        if ".." in Path(s).parts:
            return None, f"拒绝路径穿越: {s}"
        cand = (root / s).resolve()
        try:
            rel = cand.relative_to(root)
        except Exception:
            return None, f"路径不在工作区内: {s}"
    rel_s = rel.as_posix()
    sens = is_sensitive_rel(rel_s)
    if sens:
        return None, sens
    return rel_s, None


def read_workspace_files(
    workspace_root: Path,
    paths: list[str] | None,
    *,
    max_files: int = MAX_FILES,
    max_file_bytes: int = MAX_FILE_BYTES,
    max_total_bytes: int = MAX_TOTAL_BYTES,
    audit_user_id: Any = None,
) -> dict[str, Any]:
    """安全读取工作区文件，返回 file_contents 结构。"""
    root = workspace_root.resolve()
    raw_paths = [p for p in (paths or []) if p and str(p).strip()]
    items: list[dict[str, Any]] = []
    errors: list[str] = []
    total = 0

    for raw in raw_paths[: max(1, max_files)]:
        rel, err = to_workspace_relative(root, str(raw))
        if err or not rel:
            errors.append(err or f"无效路径: {raw}")
            if err and ("穿越" in err or "敏感" in err or "不在工作区" in err):
                try:
                    from tools.ide_review.ide_audit import append_ide_audit

                    append_ide_audit(
                        {
                            "event": "ide_path_rejected",
                            "user_id": audit_user_id,
                            "path": str(raw)[:500],
                            "reason": err,
                            "workspace_root": str(root),
                        }
                    )
                except Exception:
                    pass
            continue
        abs_path = (root / rel).resolve()
        if not abs_path.is_file():
            errors.append(f"文件不存在: {rel}")
            continue
        try:
            data = abs_path.read_bytes()
        except OSError as e:
            errors.append(f"读取失败 {rel}: {e}")
            continue
        truncated = False
        if len(data) > max_file_bytes:
            data = data[:max_file_bytes]
            truncated = True
        if total + len(data) > max_total_bytes:
            errors.append(f"达到总字节上限，跳过后续文件（已读 {len(items)} 个）")
            break
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            text = data.decode("utf-8", errors="replace")
            truncated = True
        total += len(data)
        items.append(
            {
                "path": rel,
                "content": text,
                "bytes": len(data),
                "truncated": truncated,
            }
        )

    return {
        "status": "ok" if items else "error",
        "workspace_root": str(root),
        "file_contents": items,
        "files": [i["path"] for i in items],
        "errors": errors,
        "provider": "bridge",
        "raw_summary": f"已读取 {len(items)} 个文件（共 {total} 字节）",
    }


def _should_skip_dir(name: str, rel_dir: str) -> bool:
    """目录是否跳过。example/test 仅在仓库根或 src 下跳过，避免误伤 com/example 包名。"""
    if name in _SKIP_DIRS:
        return True
    if name in _SKIP_DIRS_AT_SRC_OR_ROOT:
        parent = (rel_dir or "").replace("\\", "/").strip("/")
        if parent == "" or parent == "src" or parent.endswith("/src"):
            return True
    return False


def is_functional_source_rel(rel: str) -> bool:
    """是否纳入全仓审核：只要功能/业务源码，排除配置与非核心文件。"""
    r = (rel or "").replace("\\", "/").strip()
    if not r:
        return False
    base = Path(r).name
    if base in _SKIP_BASENAMES or base.startswith("."):
        return False
    if _SKIP_NAME_RE.search(r):
        return False
    if is_sensitive_rel(r):
        return False
    low = base.lower()
    return any(low.endswith(suf) for suf in _CODE_SUFFIXES)


def list_workspace_source_files(
    workspace_root: Path,
    *,
    max_files: int = MAX_REPO_FILES,
    batch_size: int = BATCH_SIZE,
) -> dict[str, Any]:
    """枚举工作区「功能源码」文件，并切成每批 batch_size 的路径列表。

    不含配置/锁文件/样式/文档/测试/静态资源等非核心文件。
    """
    root = workspace_root.resolve()
    if not root.is_dir():
        return {
            "status": "error",
            "message": f"工程目录不存在: {root}",
            "files": [],
            "batches": [],
            "total": 0,
            "batch_size": batch_size,
            "batch_count": 0,
        }

    bs = max(1, int(batch_size or BATCH_SIZE))
    limit = max(1, int(max_files or MAX_REPO_FILES))
    seen: set[str] = set()
    files: list[str] = []

    def add(rel: str) -> None:
        if not rel or rel in seen or len(files) >= limit:
            return
        if not is_functional_source_rel(rel):
            return
        abs_path = root / rel
        if abs_path.is_file():
            seen.add(rel)
            files.append(rel)

    truncated = False

    def walk(abs_dir: Path, rel_dir: str, depth: int) -> None:
        nonlocal truncated
        if len(files) >= limit or depth > 8:
            if len(files) >= limit:
                truncated = True
            return
        try:
            entries = sorted(abs_dir.iterdir(), key=lambda p: (not p.is_file(), p.name.lower()))
        except OSError:
            return
        for ent in entries:
            if len(files) >= limit:
                truncated = True
                return
            name = ent.name
            if name.startswith("."):
                continue
            if ent.is_dir():
                if _should_skip_dir(name, rel_dir):
                    continue
                walk(ent, f"{rel_dir}/{name}" if rel_dir else name, depth + 1)
                continue
            rel = f"{rel_dir}/{name}" if rel_dir else name
            add(rel.replace("\\", "/"))

    walk(root, "", 0)

    batches = [files[i : i + bs] for i in range(0, len(files), bs)] if files else []
    return {
        "status": "ok",
        "workspace_root": str(root),
        "files": files,
        "total": len(files),
        "batch_size": bs,
        "batch_count": len(batches),
        "batches": batches,
        "truncated": truncated,
        "provider": "local",
        "filter": "functional_source_only",
        "raw_summary": (
            f"共 {len(files)} 个功能源码文件（已排除配置/锁文件/样式/文档等），"
            f"分成 {len(batches)} 批（每批 {bs} 个）"
            + ("；已达枚举上限" if truncated else "")
        ),
        "next_step": (
            "按 batches 下标依次 request_ide_read_batch → 批纪要 → 终稿。"
            "禁止只审首批就结案。"
        ),
    }
