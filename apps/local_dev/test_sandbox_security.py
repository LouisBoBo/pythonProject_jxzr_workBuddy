"""沙箱拷贝 / 同步 / FS 工具：符号链接与路径逃逸防护。"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from local_dev.config import LocalDevConfig
from local_dev.fs_snapshot import snapshot_sandbox
from local_dev.sandbox import (
    prepare_sandbox,
    resolve_regular_file_in_sandbox,
    sync_changed_to_target,
)
from local_dev.tools_fs import SandboxFS


class SandboxSymlinkTests(unittest.TestCase):
    def test_prepare_skips_symlink_to_outside(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            target = base / "project"
            secret = base / "secret.txt"
            data = base / "data"
            target.mkdir()
            secret.write_text("top-secret", encoding="utf-8")
            (target / "ok.txt").write_text("safe", encoding="utf-8")
            link = target / "leak.env"
            try:
                link.symlink_to(secret)
            except OSError:
                self.skipTest("symlink not allowed")

            meta = prepare_sandbox(
                data,
                "ldj-test-symlink-copy",
                target,
                empty_target=False,
                cfg=LocalDevConfig(),
            )
            sandbox = Path(meta["sandbox"])
            self.assertTrue((sandbox / "ok.txt").is_file())
            self.assertFalse((sandbox / "leak.env").exists())

    def test_sync_rejects_symlink_in_sandbox(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            sandbox = base / "sb"
            dest = base / "dst"
            outside = base / "outside.txt"
            sandbox.mkdir()
            dest.mkdir()
            outside.write_text("nope", encoding="utf-8")
            (sandbox / "good.txt").write_text("ok", encoding="utf-8")
            link = sandbox / "bad.txt"
            try:
                link.symlink_to(outside)
            except OSError:
                self.skipTest("symlink not allowed")

            # 混有不安全项：跳过链接，仍同步合法文件
            written = sync_changed_to_target(
                sandbox,
                dest,
                ["good.txt", "bad.txt"],
                cfg=LocalDevConfig(max_total_write_bytes=1_000_000),
            )
            self.assertEqual(written, ["good.txt"])
            self.assertEqual((dest / "good.txt").read_text(encoding="utf-8"), "ok")
            self.assertFalse((dest / "bad.txt").exists())
            self.assertEqual(outside.read_text(encoding="utf-8"), "nope")

    def test_sync_only_unsafe_raises(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            sandbox = base / "sb"
            dest = base / "dst"
            outside = base / "outside.txt"
            sandbox.mkdir()
            dest.mkdir()
            outside.write_text("x", encoding="utf-8")
            link = sandbox / "only.txt"
            try:
                link.symlink_to(outside)
            except OSError:
                self.skipTest("symlink not allowed")
            with self.assertRaises(RuntimeError) as ctx:
                sync_changed_to_target(sandbox, dest, ["only.txt"])
            self.assertIn("没有可同步的安全文件", str(ctx.exception))

    def test_resolve_regular_file_rejects_symlink(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            sandbox = Path(td)
            outside = sandbox / ".." / "out.txt"
            # use sibling file
            sib = Path(td).parent / f"out-{sandbox.name}.txt"
            sib.write_text("x", encoding="utf-8")
            self.addCleanup(lambda: sib.unlink(missing_ok=True))
            link = sandbox / "l.txt"
            try:
                link.symlink_to(sib)
            except OSError:
                self.skipTest("symlink not allowed")
            with self.assertRaises(ValueError):
                resolve_regular_file_in_sandbox(sandbox, "l.txt")

    def test_fs_read_write_reject_symlink(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            sandbox = Path(td)
            outside = Path(td).parent / f"secret-{sandbox.name}.txt"
            outside.write_text("SECRET", encoding="utf-8")
            self.addCleanup(lambda: outside.unlink(missing_ok=True))
            link = sandbox / "leak.txt"
            try:
                link.symlink_to(outside)
            except OSError:
                self.skipTest("symlink not allowed")
            fs = SandboxFS(sandbox)
            r = fs.read_file("leak.txt")
            self.assertFalse(r["ok"])
            self.assertTrue(
                "符号链接" in r["error"] or "逃逸" in r["error"],
                msg=r["error"],
            )
            w = fs.write_file("leak.txt", "pwned")
            self.assertFalse(w["ok"])
            self.assertTrue(
                "符号链接" in w["error"] or "逃逸" in w["error"],
                msg=w["error"],
            )
            self.assertEqual(outside.read_text(encoding="utf-8"), "SECRET")

    def test_snapshot_skips_symlink(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "a.txt").write_text("a", encoding="utf-8")
            outside = Path(td).parent / f"snap-{root.name}.txt"
            outside.write_text("x", encoding="utf-8")
            self.addCleanup(lambda: outside.unlink(missing_ok=True))
            link = root / "b.txt"
            try:
                link.symlink_to(outside)
            except OSError:
                self.skipTest("symlink not allowed")
            snap = snapshot_sandbox(root)
            self.assertIn("a.txt", snap)
            self.assertNotIn("b.txt", snap)


if __name__ == "__main__":
    unittest.main()
