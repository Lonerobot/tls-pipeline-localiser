"""Safe zip extraction."""
import re
import shutil
import stat
import zipfile
from pathlib import Path, PurePosixPath

from .errors import UnsafeArchiveError

_DRIVE_RE = re.compile(r"^[A-Za-z]:")


def _member_parts(info: zipfile.ZipInfo) -> tuple[str, ...]:
    name = info.filename
    if "\x00" in name or "\\" in name or ":" in name or _DRIVE_RE.match(name):
        raise UnsafeArchiveError(f"unsafe archive member name: {name!r}")
    if name.startswith("/"):
        raise UnsafeArchiveError(f"absolute archive member path: {name!r}")
    if stat.S_ISLNK(info.external_attr >> 16):
        raise UnsafeArchiveError(f"symlink archive member rejected: {name!r}")
    parts = tuple(part for part in PurePosixPath(name).parts if part != ".")
    if not parts or ".." in parts or "//" in name:
        raise UnsafeArchiveError(f"unsafe archive member path: {name!r}")
    return parts


def safe_extract(archive: Path, destination: Path) -> None:
    """Validate every member first, then extract; nothing is written if any member is unsafe."""
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    root = destination.resolve()
    with zipfile.ZipFile(archive) as zf:
        plan = []
        seen = set()
        for info in zf.infolist():
            parts = _member_parts(info)
            key = tuple(part.lower() for part in parts)
            if key in seen:
                raise UnsafeArchiveError(f"duplicate archive member: {info.filename!r}")
            seen.add(key)
            target = root.joinpath(*parts)
            if root != target and root not in target.resolve().parents:
                raise UnsafeArchiveError(f"archive member escapes destination: {info.filename!r}")
            plan.append((info, target))
        for info, target in plan:
            if info.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(info) as source, open(target, "wb") as sink:
                shutil.copyfileobj(source, sink)
