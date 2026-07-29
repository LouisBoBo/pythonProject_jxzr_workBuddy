"""HA 辅助：跨进程锁与实例标识。"""
from ha.fs_lock import InterProcessLock, instance_id, locked

__all__ = ["InterProcessLock", "instance_id", "locked"]
