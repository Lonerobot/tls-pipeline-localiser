"""Subprocess helpers for multi-process tests. Run as: python _workers.py <command> ..."""
import logging
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

from localiser.config import parse_local_config  # noqa: E402
from localiser.install import ensure_release  # noqa: E402
from localiser.layout import DataLayout  # noqa: E402
from localiser.lock import FileLock  # noqa: E402


def hold_lock(path, ready_file):
    with FileLock(Path(path), timeout=5):
        Path(ready_file).write_text("locked")
        sys.stdin.readline()


def install(config_path, package_id, release_id, go_file):
    class Counter(logging.Handler):
        installed = 0

        def emit(self, record):
            if "event=release_installed" in record.getMessage():
                Counter.installed += 1

    logging.getLogger("localiser").addHandler(Counter())
    logging.getLogger("localiser").setLevel(logging.INFO)
    config = parse_local_config(Path(config_path).read_text(encoding="utf-8"), Path(config_path).parent)
    while not Path(go_file).exists():
        time.sleep(0.005)
    release = ensure_release(
        DataLayout(config.bundle_repository), config.remote_repository, package_id, release_id, lock_timeout=60
    )
    print("OK installed={} root={}".format(Counter.installed, release.release_root))


if __name__ == "__main__":
    command, args = sys.argv[1], sys.argv[2:]
    {"hold_lock": hold_lock, "install": install}[command](*args)
