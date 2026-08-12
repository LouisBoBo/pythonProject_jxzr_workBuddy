"""沙箱内受限文件系统工具（供本机写码 Agent 调用）。"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from .config import LocalDevConfig, get_config
from .sandbox import is_sensitive_rel, resolve_in_sandbox


class SandboxFS:
    def __init__(
        self,
        sandbox: Path,
        *,
        cfg: LocalDevConfig | None = None,
    ) -> None:
        self.sandbox = Path(sandbox).resolve()
        self.cfg = cfg or get_config()
        self.changed: set[str] = set()
        self.bytes_written = 0

    def _rel_of(self, path: Path) -> str:
        return path.relative_to(self.sandbox).as_posix()

    def list_dir(self, rel: str = ".") -> dict[str, Any]:
        if rel in (".", "", "/"):
            target = self.sandbox
            show = "."
        else:
            target = resolve_in_sandbox(self.sandbox, rel)
            show = rel
        if not target.exists():
            return {"ok": False, "error": f"不存在：{show}"}
        if not target.is_dir():
            return {"ok": False, "error": f"不是目录：{show}"}
        entries: list[dict[str, str]] = []
        for child in sorted(target.iterdir(), key=lambda p: p.name.lower()):
            kind = "dir" if child.is_dir() else "file"
            entries.append({"name": child.name, "type": kind})
        return {"ok": True, "path": show, "entries": entries[:200]}

    def read_file(self, rel: str) -> dict[str, Any]:
        try:
            target = resolve_in_sandbox(self.sandbox, rel)
        except ValueError as e:
            return {"ok": False, "error": str(e)}
        if is_sensitive_rel(rel):
            return {"ok": False, "error": "敏感文件不可读"}
        if not target.is_file():
            return {"ok": False, "error": f"文件不存在：{rel}"}
        size = target.stat().st_size
        if size > self.cfg.max_file_bytes:
            return {"ok": False, "error": f"文件过大（>{self.cfg.max_file_bytes} 字节）"}
        try:
            text = target.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            return {"ok": False, "error": "非文本文件，跳过"}
        except OSError as e:
            return {"ok": False, "error": str(e)}
        # 截断过长展示
        if len(text) > 80_000:
            text = text[:80_000] + "\n…(截断)…"
        return {"ok": True, "path": rel, "content": text}

    def write_file(self, rel: str, content: str) -> dict[str, Any]:
        try:
            target = resolve_in_sandbox(self.sandbox, rel)
        except ValueError as e:
            return {"ok": False, "error": str(e)}
        if is_sensitive_rel(rel):
            return {"ok": False, "error": "禁止写入敏感文件（如 .env / 证书）"}
        data = content if isinstance(content, str) else str(content)
        encoded = data.encode("utf-8")
        if len(encoded) > self.cfg.max_file_bytes:
            return {"ok": False, "error": f"单文件超过上限 {self.cfg.max_file_bytes} 字节"}
        if self.bytes_written + len(encoded) > self.cfg.max_total_write_bytes:
            return {"ok": False, "error": "本任务累计写入字节超限"}
        if rel not in self.changed and len(self.changed) >= self.cfg.max_changed_files:
            return {"ok": False, "error": f"改动文件数超过上限 {self.cfg.max_changed_files}"}
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            target.write_text(data, encoding="utf-8")
        except OSError as e:
            return {"ok": False, "error": str(e)}
        self.changed.add(self._rel_of(target))
        self.bytes_written += len(encoded)
        return {"ok": True, "path": rel, "bytes": len(encoded)}

    def mkdir(self, rel: str) -> dict[str, Any]:
        try:
            target = resolve_in_sandbox(self.sandbox, rel)
        except ValueError as e:
            return {"ok": False, "error": str(e)}
        if is_sensitive_rel(rel):
            return {"ok": False, "error": "禁止在敏感路径下创建目录"}
        try:
            target.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            return {"ok": False, "error": str(e)}
        return {"ok": True, "path": rel}

    def changed_files(self) -> list[str]:
        return sorted(self.changed)
