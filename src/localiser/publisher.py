"""Publish a source folder as an immutable release on the share."""
import os
import shutil
import tempfile
import zipfile
from pathlib import Path

from .config import Manifest, validate_id, validate_python_root
from .errors import PublishError
from .fsutil import atomic_write_text, sha256_file
from .layout import HOSTS_DIR

ARTIFACT_NAME = "pipeline.zip"
EXCLUDED_DIRS = frozenset({"__pycache__"})
EXCLUDED_FILES = frozenset({"Thumbs.db"})
EXCLUDED_SUFFIXES = (".pyc",)
_FIXED_TIME = (1980, 1, 1, 0, 0, 0)


def _collect(source: Path) -> list[tuple[str, Path]]:
    """Return (archive name, path) for every file to publish, in a stable order."""
    entries = []
    for current, dirs, files in os.walk(source):
        dirs[:] = sorted(d for d in dirs if d not in EXCLUDED_DIRS)
        for name in dirs:
            if (Path(current) / name).is_symlink():
                raise PublishError(f"symlinks are not allowed in a release: {Path(current) / name}")
        for name in sorted(files):
            if name in EXCLUDED_FILES or name.endswith(EXCLUDED_SUFFIXES):
                continue
            path = Path(current) / name
            if path.is_symlink():
                raise PublishError(f"symlinks are not allowed in a release: {path}")
            entries.append((path.relative_to(source).as_posix(), path))
    return sorted(entries)


def publish_release(
    source: Path, repository_root: Path, package_id: str, release_id: str, *, python_root: str = "."
) -> Manifest:
    """Zip `source`, compute its SHA-256, write the manifest, and place both on the share.

    Refuses to overwrite an existing release ID. The zip is deterministic for identical content.
    """
    source = Path(source)
    package_id = validate_id(package_id, "package_id")
    release_id = validate_id(release_id, "release_id")
    python_root = validate_python_root(python_root)
    if not source.is_dir():
        raise PublishError(f"source folder not found: {source}")
    if not (source / python_root).is_dir():
        raise PublishError(f"python_root {python_root!r} not found in source folder")

    package_dir = Path(repository_root) / HOSTS_DIR / package_id
    destination = package_dir / release_id
    if destination.exists():
        raise PublishError(f"release already exists and is immutable: {package_id}/{release_id}")

    entries = _collect(source)
    package_dir.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(dir=package_dir, prefix=".publishing-"))
    try:
        artifact = staging / ARTIFACT_NAME
        with zipfile.ZipFile(artifact, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for arcname, path in entries:
                info = zipfile.ZipInfo(arcname, date_time=_FIXED_TIME)
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = 0o644 << 16
                with open(path, "rb") as handle, zf.open(info, "w") as sink:
                    shutil.copyfileobj(handle, sink)
        manifest = Manifest(
            package_id=package_id,
            release_id=release_id,
            artifact=ARTIFACT_NAME,
            sha256=sha256_file(artifact),
            python_root=python_root,
        )
        atomic_write_text(staging / "manifest.json", manifest.to_json())
        try:
            os.rename(staging, destination)
        except OSError as exc:
            raise PublishError(f"could not publish {package_id}/{release_id}: {exc}") from None
        return manifest
    finally:
        shutil.rmtree(staging, ignore_errors=True)
