"""Localise a release: check the local store, otherwise copy, verify, extract and publish atomically."""
import json
import logging
import os
import shutil
import tempfile
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .archive import safe_extract
from .config import Manifest, parse_manifest, validate_python_root
from .errors import LocaliserError, ReleaseUnavailableError, VerificationError
from .fsutil import atomic_write_text, rename_with_retry, sha256_file
from .layout import COMPLETE_MARKER, HOSTS_DIR, DataLayout
from .lock import FileLock
from .logs import log_event
from .repository import Repository, as_repository

PAYLOAD_DIR = "payload"


@dataclass(frozen=True)
class LocalRelease:
    package_id: str
    release_id: str
    release_root: Path
    python_root: Path


def _read_marker(release_dir: Path, package_id: str, release_id: str) -> LocalRelease | None:
    """Return the release if it has a valid completion marker, else None (treated as not installed)."""
    try:
        text = (release_dir / COMPLETE_MARKER).read_text(encoding="utf-8")
    except OSError:
        return None
    try:
        data = json.loads(text)
        if data["package_id"] != package_id or data["release_id"] != release_id:
            raise ValueError("identity mismatch")
        python_root = validate_python_root(data["python_root"])
    except (ValueError, KeyError, TypeError, LocaliserError) as exc:
        log_event(logging.WARNING, "invalid_completion_marker", release=release_id, error=exc)
        return None
    return LocalRelease(package_id, release_id, release_dir, release_dir / python_root)


def _quarantine(layout: DataLayout, release_dir: Path) -> None:
    """Move a directory that has no valid marker out of the way. It is not a release, so nothing may rely on it."""
    if not release_dir.exists():
        return
    target = layout.staging / f"orphan__{uuid.uuid4().hex}"
    try:
        os.rename(release_dir, target)
    except OSError as exc:
        raise LocaliserError(
            f"release directory has no valid completion marker and could not be moved aside ({exc}); "
            f"repair required: {release_dir}"
        ) from None
    log_event(logging.WARNING, "orphan_release_quarantined", path=release_dir)
    shutil.rmtree(target, ignore_errors=True)


def ensure_release(
    layout: DataLayout,
    repository_root,
    package_id: str,
    release_id: str,
    *,
    host: str | None = None,
    lock_timeout: float = 60.0,
) -> LocalRelease:
    """`repository_root` is the remote: a folder path or a repository from localiser.repository."""
    release_dir = layout.release_dir(package_id, release_id)

    existing = _read_marker(release_dir, package_id, release_id)
    if existing is not None:
        return existing

    layout.ensure()
    with FileLock(layout.release_lock(package_id, release_id), timeout=lock_timeout):
        # Another process may have finished the install while we waited for the lock.
        existing = _read_marker(release_dir, package_id, release_id)
        if existing is not None:
            return existing
        _quarantine(layout, release_dir)
        return _install(layout, as_repository(repository_root), package_id, release_id, host)


def _install(
    layout: DataLayout, repository: Repository, package_id: str, release_id: str, host: str | None
) -> LocalRelease:
    staging = Path(tempfile.mkdtemp(dir=layout.staging, prefix=f"{package_id}__{release_id}__"))
    try:
        manifest = _fetch(repository, staging, package_id, release_id, host)
        payload = staging / PAYLOAD_DIR
        safe_extract(staging / manifest.artifact, payload)
        if not (payload / manifest.python_root).is_dir():
            raise VerificationError(
                f"python_root {manifest.python_root!r} not found in release {package_id}/{release_id}"
            )
        marker = {
            "schema_version": 1,
            "package_id": package_id,
            "release_id": release_id,
            "python_root": manifest.python_root,
            "sha256": manifest.sha256,
            "completed_at": datetime.now(timezone.utc).isoformat(),
        }
        atomic_write_text(payload / COMPLETE_MARKER, json.dumps(marker, indent=2, sort_keys=True) + "\n")

        final = layout.release_dir(package_id, release_id)
        final.parent.mkdir(parents=True, exist_ok=True)
        rename_with_retry(payload, final)
        atomic_write_text(layout.manifest_cache(package_id, release_id), manifest.to_json())
        log_event(logging.INFO, "release_installed", host=host, package=package_id, release=release_id, root=final)
        return LocalRelease(package_id, release_id, final, final / manifest.python_root)
    finally:
        shutil.rmtree(staging, ignore_errors=True)


def _fetch(repository: Repository, staging: Path, package_id: str, release_id: str, host: str | None) -> Manifest:
    """Copy the artifact from the repository into staging and check it against the manifest."""
    name = f"{package_id}/{release_id}"
    folder = f"{HOSTS_DIR}/{package_id}/{release_id}"
    try:
        manifest_text = repository.read_text(f"{folder}/manifest.json")
    except OSError as exc:
        raise ReleaseUnavailableError(
            f"release {name} is not cached and cannot be fetched ({exc})", host=host, release_id=release_id
        ) from None
    manifest = parse_manifest(manifest_text)
    if (manifest.package_id, manifest.release_id) != (package_id, release_id):
        raise VerificationError(
            f"manifest identity {manifest.package_id}/{manifest.release_id} does not match requested {name}"
        )
    local_artifact = staging / manifest.artifact
    try:
        repository.fetch(f"{folder}/{manifest.artifact}", local_artifact)
    except OSError as exc:
        raise ReleaseUnavailableError(
            f"artifact for {name} cannot be fetched ({exc})", host=host, release_id=release_id
        ) from None
    actual = sha256_file(local_artifact)
    if actual != manifest.sha256:
        raise VerificationError(f"checksum mismatch for {name}: expected {manifest.sha256}, got {actual}")
    return manifest
