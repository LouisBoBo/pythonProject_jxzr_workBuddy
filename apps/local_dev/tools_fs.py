"""沙箱内受限文件系统工具（供本机写码 Agent 调用）。"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from .config import LocalDevConfig, get_config
from .sandbox import is_sensitive_rel, sandbox_entry


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

    def _entry(self, rel: str) -> Path:
        """沙箱内入口路径；拒绝逃逸；读写前另检符号链接。"""
        return sandbox_entry(self.sandbox, rel)

    def list_dir(self, rel: str = ".") -> dict[str, Any]:
        if rel in (".", "", "/"):
            target = self.sandbox
            show = "."
        else:
            try:
                entry = self._entry(rel)
            except ValueError as e:
                return {"ok": False, "error": str(e)}
            if entry.is_symlink():
                return {"ok": False, "error": "拒绝符号链接目录"}
            target = entry.resolve()
            try:
                target.relative_to(self.sandbox)
            except ValueError:
                return {"ok": False, "error": "路径逃逸出沙箱"}
            show = rel
        if not target.exists():
            return {"ok": False, "error": f"不存在：{show}"}
        if not target.is_dir():
            return {"ok": False, "error": f"不是目录：{show}"}
        entries: list[dict[str, str]] = []
        for child in sorted(target.iterdir(), key=lambda p: p.name.lower()):
            if child.is_symlink():
                kind = "symlink"
            elif child.is_dir():
                kind = "dir"
            else:
                kind = "file"
            entries.append({"name": child.name, "type": kind})
        return {"ok": True, "path": show, "entries": entries[:200]}

    def read_file(self, rel: str) -> dict[str, Any]:
        try:
            entry = self._entry(rel)
        except ValueError as e:
            return {"ok": False, "error": str(e)}
        if is_sensitive_rel(rel):
            return {"ok": False, "error": "敏感文件不可读"}
        if entry.is_symlink():
            return {"ok": False, "error": "拒绝读取符号链接"}
        if not entry.is_file():
            return {"ok": False, "error": f"文件不存在：{rel}"}
        size = entry.stat().st_size
        if size > self.cfg.max_file_bytes:
            return {"ok": False, "error": f"文件过大（>{self.cfg.max_file_bytes} 字节）"}
        try:
            text = entry.read_text(encoding="utf-8")
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
            entry = self._entry(rel)
        except ValueError as e:
            return {"ok": False, "error": str(e)}
        if is_sensitive_rel(rel):
            return {"ok": False, "error": "禁止写入敏感文件（如 .env / 证书）"}
        # 已存在的符号链接：禁止跟随写出沙箱
        if entry.exists() and entry.is_symlink():
            return {"ok": False, "error": "拒绝写入符号链接"}
        data = content if isinstance(content, str) else str(content)
        encoded = data.encode("utf-8")
        if len(encoded) > self.cfg.max_file_bytes:
            return {"ok": False, "error": f"单文件超过上限 {self.cfg.max_file_bytes} 字节"}
        if self.bytes_written + len(encoded) > self.cfg.max_total_write_bytes:
            return {"ok": False, "error": "本任务累计写入字节超限"}
        if rel not in self.changed and len(self.changed) >= self.cfg.max_changed_files:
            return {"ok": False, "error": f"改动文件数超过上限 {self.cfg.max_changed_files}"}
        entry.parent.mkdir(parents=True, exist_ok=True)
        # 父路径若为外链，sandbox_entry 已拒绝；再写前确认 resolve 仍在沙箱内
        try:
            entry.resolve(strict=False).relative_to(self.sandbox)
        except ValueError:
            return {"ok": False, "error": "路径逃逸出沙箱"}
        try:
            # 写入未 resolve 的入口路径，避免跟随叶子符号链接
            entry.write_text(data, encoding="utf-8")
        except OSError as e:
            return {"ok": False, "error": str(e)}
        if entry.is_symlink():
            try:
                entry.unlink()
            except OSError:
                pass
            return {"ok": False, "error": "写入结果为符号链接，已拒绝"}
        self.changed.add(self._rel_of(entry.resolve()))
        self.bytes_written += len(encoded)
        return {"ok": True, "path": rel, "bytes": len(encoded)}

    def mkdir(self, rel: str) -> dict[str, Any]:
        try:
            entry = self._entry(rel)
        except ValueError as e:
            return {"ok": False, "error": str(e)}
        if is_sensitive_rel(rel):
            return {"ok": False, "error": "禁止在敏感路径下创建目录"}
        if entry.exists() and entry.is_symlink():
            return {"ok": False, "error": "拒绝在符号链接上创建目录"}
        try:
            entry.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            return {"ok": False, "error": str(e)}
        return {"ok": True, "path": rel}

    def changed_files(self) -> list[str]:
        return sorted(self.changed)
