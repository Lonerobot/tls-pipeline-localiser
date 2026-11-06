import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

from localiser import LockTimeoutError
from localiser.lock import FileLock

WORKERS = str(Path(__file__).with_name("_workers.py"))


class FileLockTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.lock_path = Path(tmp.name) / "locks" / "x.lock"

    def test_second_acquirer_times_out_then_succeeds_after_release(self):
        ready = self.lock_path.with_name("ready")
        holder = subprocess.Popen(
            [sys.executable, WORKERS, "hold_lock", str(self.lock_path), str(ready)],
            stdin=subprocess.PIPE,
            text=True,
        )
        try:
            deadline = time.monotonic() + 10
            while not ready.exists():
                self.assertLess(time.monotonic(), deadline, "holder never locked")
                time.sleep(0.02)
            with self.assertRaises(LockTimeoutError):
                FileLock(self.lock_path, timeout=0.3, poll_interval=0.05).acquire()
        finally:
            holder.stdin.close()
            holder.wait(timeout=10)
        with FileLock(self.lock_path, timeout=2):
            pass

    def test_lock_is_released_when_holder_dies(self):
        ready = self.lock_path.with_name("ready")
        holder = subprocess.Popen(
            [sys.executable, WORKERS, "hold_lock", str(self.lock_path), str(ready)],
            stdin=subprocess.PIPE,
            text=True,
        )
        deadline = time.monotonic() + 10
        while not ready.exists():
            self.assertLess(time.monotonic(), deadline, "holder never locked")
            time.sleep(0.02)
        holder.kill()
        holder.wait(timeout=10)
        holder.stdin.close()
        with FileLock(self.lock_path, timeout=5):
            pass

    def test_not_reentrant(self):
        lock = FileLock(self.lock_path, timeout=1)
        with lock:
            with self.assertRaises(RuntimeError):
                lock.acquire()


if __name__ == "__main__":
    unittest.main()
