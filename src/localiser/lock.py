"""Cross-process exclusive lock using OS byte-range locks.

The OS releases the lock when the holding process dies, so a crash never leaves a stale lock.
"""
import os
import time
from pathlib import Path

from .errors import LockTimeoutError

if os.name == "nt":
    import msvcrt

    def _try_lock(handle) -> None:
        handle.seek(0)
        msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)

    def _unlock(handle) -> None:
        handle.seek(0)
        msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)

else:
    import fcntl

    def _try_lock(handle) -> None:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)

    def _unlock(handle) -> None:
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


class FileLock:
    def __init__(self, path: Path, timeout: float = 60.0, poll_interval: float = 0.1):
        self.path = Path(path)
        self.timeout = timeout
        self.poll_interval = poll_interval
        self._handle = None

    def acquire(self) -> None:
        if self._handle is not None:
            raise RuntimeError("lock already held by this object")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        handle = open(self.path, "a+b")
        try:
            if handle.seek(0, os.SEEK_END) == 0:
                handle.write(b"\0")  # Windows byte-range locking needs a byte to lock
                handle.flush()
            deadline = time.monotonic() + self.timeout
            while True:
                try:
                    _try_lock(handle)
                    break
                except OSError:
                    if time.monotonic() >= deadline:
                        raise LockTimeoutError(
                            f"timed out after {self.timeout:.1f}s waiting for lock {self.path.name}"
                        ) from None
                    time.sleep(self.poll_interval)
        except BaseException:
            handle.close()
            raise
        self._handle = handle

    def release(self) -> None:
        handle, self._handle = self._handle, None
        if handle is None:
            return
        try:
            _unlock(handle)
        finally:
            handle.close()

    def __enter__(self) -> "FileLock":
        self.acquire()
        return self

    def __exit__(self, *exc_info) -> None:
        self.release()
