"""Small filesystem helpers shared by the core and publisher."""
import hashlib
import os
import uuid
from pathlib import Path


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
