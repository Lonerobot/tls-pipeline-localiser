"""Small filesystem helpers shared by the core and publisher."""
import hashlib
import os
import time
import uuid
from pathlib import Path


def rename_with_retry(source: Path, destination: Path, attempts: int = 20) -> None:
    """Rename, retrying for up to about half a minute on Windows PermissionError.

    A virus scanner or indexer can hold a handle on a freshly written folder while it scans it, which makes
    the rename fail with 'Access is denied' although nothing is wrong. It clears by itself, so wait for
    it. Other errors are not retried.
    """
    for attempt in range(1, attempts + 1):
        try:
            os.rename(source, destination)
            return
        except PermissionError:
            if attempt == attempts:
                raise
            time.sleep(min(0.25 * attempt, 2.0))


def atomic_write_text(path: Path, text: str) -> None:
    """Write a temp file next to `path`, then replace it, so readers never see a partial file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f"{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        temp.write_text(text, encoding="utf-8", newline="\n")
        os.replace(temp, path)
    except BaseException:
        temp.unlink(missing_ok=True)
        raise


def sha256_file(path: Path) -> str:
    with open(path, "rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()
