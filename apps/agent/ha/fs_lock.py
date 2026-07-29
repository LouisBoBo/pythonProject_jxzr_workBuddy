"""跨进程文件锁：多 API 实例共享 DATA_DIR 时保护 writes / api_calls。

同一进程内可重入（兼容原先 threading.RLock 嵌套）；
进程间靠 flock（Unix）。Windows 无 fcntl 时退化为仅线程锁。
"""
from __future__ import annotations

import os
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

try:
    import fcntl
except ImportError:  # Windows
    fcntl = None  # type: ignore


def _lock_dir() -> Path:
    from config import Config

    root = Path(Config.DATA_DIR) / ".locks"
    root.mkdir(parents=True, exist_ok=True)
    return root


class InterProcessLock:
    """可重入的进程+线程锁。"""

    def __init__(self, name: str):
        safe = "".join(c for c in name if c.isalnum() or c in "-_") or "default"
        self._name = safe
        self._thread = threading.RLock()
        self._depth = 0
        self._fp = None

    def acquire(self, blocking: bool = True, timeout: float = -1) -> bool:
        ok = self._thread.acquire(blocking, timeout if timeout is not None and timeout >= 0 else -1)
        if not ok:
            return False
        try:
            if self._depth == 0:
                path = _lock_dir() / f"{self._name}.lock"
                self._fp = open(path, "a+", encoding="utf-8")
                if fcntl is not None:
                    if not blocking:
                        fcntl.flock(self._fp.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    elif timeout is not None and timeout > 0:
                        deadline = time.time() + timeout
                        while True:
                            try:
                                fcntl.flock(self._fp.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                                break
                            except BlockingIOError:
                                if time.time() >= deadline:
                                    self._fp.close()
                                    self._fp = None
                                    self._thread.release()
                                    return False
                                time.sleep(0.01)
                    else:
                        fcntl.flock(self._fp.fileno(), fcntl.LOCK_EX)
            self._depth += 1
            return True
        except Exception:
            if self._fp is not None:
                try:
                    self._fp.close()
                except Exception:
                    pass
                self._fp = None
            self._thread.release()
            raise

    def release(self) -> None:
        if self._depth <= 0:
            return
        self._depth -= 1
        if self._depth == 0 and self._fp is not None:
            try:
                if fcntl is not None:
                    fcntl.flock(self._fp.fileno(), fcntl.LOCK_UN)
            finally:
                try:
                    self._fp.close()
                except Exception:
                    pass
                self._fp = None
        self._thread.release()

    def __enter__(self) -> "InterProcessLock":
        self.acquire(True)
        return self

    def __exit__(self, *exc) -> None:
        self.release()


@contextmanager
def locked(name: str) -> Iterator[None]:
    lock = InterProcessLock(name)
    lock.acquire(True)
    try:
        yield
    finally:
        lock.release()


def instance_id() -> str:
    return (
        os.getenv("INSTANCE_ID")
        or os.getenv("HOSTNAME")
        or f"pid-{os.getpid()}"
    ).strip()
