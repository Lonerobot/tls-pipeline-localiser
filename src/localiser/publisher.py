"""Publish a source folder as an immutable release on the share."""
import os
import shutil
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path

from .config import Manifest, _check_schema, _load_object, validate_host, validate_id, validate_python_root
from .errors import ConfigError, PublishError
from .fsutil import atomic_write_text, rename_with_retry, sha256_file
from .hosts import HOSTS
from .layout import HOSTS_DIR

ARTIFACT_NAME = "pipeline.zip"
BUNDLE_FILE = "bundle.json"


def _host_defaults(host: str) -> dict:
    """Where a host's bundle keeps its entry point and shared packages when bundle.json doesn't say (hosts.py)."""
    info = HOSTS.get(host)
    return {"python_root": info.python_root, "shared_destination": info.shared_destination} if info else {}
EXCLUDED_DIRS = frozenset({"__pycache__", "__MACOSX"})
EXCLUDED_FILES = frozenset({"Thumbs.db", ".DS_Store"})
EXCLUDED_SUFFIXES = (".pyc", "~")  # compiled bytecode and editor/Nuke autosave backups (scene.nk~)
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
    validate_id(package_id, "package_id")
    validate_id(release_id, "release_id")
    python_root = validate_python_root(python_root)
    if not source.is_dir():
        raise PublishError(f"source folder not found: {source}")
    if not (source / python_root).is_dir():
        raise PublishError(f"python_root {python_root!r} not found in source folder")
    return _write_release(_collect(source), repository_root, package_id, release_id, python_root)


def _write_release(
    entries: list[tuple[str, Path]], repository_root: Path, package_id: str, release_id: str, python_root: str
) -> Manifest:
    """Zip `entries` (archive name, file path), write the manifest, and place both on the share."""
    package_id = validate_id(package_id, "package_id")
    release_id = validate_id(release_id, "release_id")
    python_root = validate_python_root(python_root)

    package_dir = Path(repository_root) / HOSTS_DIR / package_id
    destination = package_dir / release_id
    if destination.exists():
        raise PublishError(f"release already exists and is immutable: {package_id}/{release_id}")

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
            rename_with_retry(staging, destination)
        except OSError as exc:
            raise PublishError(f"could not publish {package_id}/{release_id}: {exc}") from None
        return manifest
    finally:
        shutil.rmtree(staging, ignore_errors=True)


@dataclass(frozen=True)
class BundlePlan:
    """What a bundle source will publish: every archive entry, the entry point and the shared packages merged in."""

    host: str
    python_root: str
    entries: list  # (archive name, file path), sorted
    shared: tuple  # names of the shared packages merged in


def read_descriptor(source: Path, host: str) -> tuple[str, str]:
    """Return (python_root, shared_destination) for a bundle source.

    Host defaults apply first, then an optional bundle.json at the root of the source overrides them.
    """
    settings = {"python_root": ".", "shared_destination": ".", **_host_defaults(host)}
    path = Path(source) / BUNDLE_FILE
    if path.is_file():
        try:
            data = _load_object(path.read_text(encoding="utf-8-sig"), BUNDLE_FILE)
            _check_schema(data, BUNDLE_FILE)
        except ConfigError as exc:
            raise PublishError(str(exc)) from None
        unknown = sorted(set(data) - {"schema_version", *settings})
        if unknown:
            raise PublishError(f"{BUNDLE_FILE} has unknown keys: {', '.join(unknown)}")
        settings.update({key: data[key] for key in settings if key in data})
    try:
        return validate_python_root(settings["python_root"]), validate_python_root(settings["shared_destination"])
    except ConfigError as exc:
        raise PublishError(f"{BUNDLE_FILE}: {exc}") from None


def _shared_packages(shared_roots) -> list[Path]:
    packages = []
    for root in shared_roots:
        root = Path(root)
        if not root.is_dir():
            raise PublishError(f"shared sources folder not found: {root}")
        packages += [p for p in sorted(root.iterdir()) if p.is_dir() and not p.name.startswith((".", "_"))]
    return packages


def plan_bundle(source: Path, host: str, shared=()) -> BundlePlan:
    """Work out what `source` publishes for `host`, merging in each package from the `shared` folders.

    Shared packages go to the bundle root, or to the host's shared destination (Blender: modules/). A bundle
    can't ship a package with the same name as a shared one. bundle.json is publishing metadata and is not shipped.
    """
    source = Path(source)
    validate_host(host)
    if not source.is_dir():
        raise PublishError(f"source folder not found: {source}")
    python_root, destination = read_descriptor(source, host)

    entries = [(name, path) for name, path in _collect(source) if name != BUNDLE_FILE]
    taken = {name.lower() for name, _ in entries}
    names = []
    for package in _shared_packages(shared):
        prefix = package.name if destination == "." else f"{destination}/{package.name}"
        if any(name == prefix.lower() or name.startswith(prefix.lower() + "/") for name in taken):
            raise PublishError(f"{prefix} already exists in the bundle; a shared package can't be overridden or repeated")
        added = [(f"{prefix}/{name}", path) for name, path in _collect(package)]
        entries += added
        taken.update(name.lower() for name, _ in added)
        names.append(package.name)
    entries.sort()

    if python_root != "." and not any(name.lower().startswith(python_root.lower() + "/") for name, _ in entries):
        raise PublishError(f"python_root {python_root!r} not found in the bundle")
    return BundlePlan(host, python_root, entries, tuple(names))


def publish_plan(plan: BundlePlan, repository_root: Path, release_id: str) -> Manifest:
    """Publish a planned bundle as an immutable release of its host."""
    return _write_release(plan.entries, repository_root, plan.host, release_id, plan.python_root)


def materialize_plan(plan: BundlePlan, destination: Path) -> Path:
    """Copy a planned bundle to `destination` exactly as a published release would extract: the same files in
    the same places, without the zip or the checksum. Returns the entry-point folder (python_root)."""
    destination = Path(destination)
    for name, path in plan.entries:
        target = destination / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
    return destination if plan.python_root == "." else destination / plan.python_root


def publish_bundle(source: Path, repository_root: Path, host: str, release_id: str, *, shared=()) -> Manifest:
    """Plan and publish a bundle source in one step."""
    return publish_plan(plan_bundle(source, host, shared), repository_root, release_id)
