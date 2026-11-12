"""Clone a bundle into the dev folder to edit and run in place, and choose which clone a host launches with.

A clone is <local releases>/dev/<host>/<tag>/: a complete bundle laid out as a release would extract, plus a
`.tls-clone.json` marker. It is run where it is (see `sync.dev_release`), is never selected, synced or overwritten,
and is only removed by the user.
"""
import json
import re
import shutil
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from .archive import safe_extract
from .config import LocalConfig, Manifest, parse_manifest, validate_host, validate_id, validate_python_root, validate_series
from .errors import ConfigError, PublishError, ReleaseUnavailableError
from .fsutil import atomic_write_text, rename_with_retry
from .install import _read_marker
from .layout import CLONE_MARKER, HOSTS_DIR, DataLayout
from .publisher import ARTIFACT_NAME, _collect, _host_defaults, _write_release, materialize_plan, plan_bundle, publish_plan
from .repository import as_repository
from .resolve import _load_studio_config
from .sync import pull_release, read_clone_marker


class ZippedSourceError(PublishError):
    """The source folder holds a zipped (published) bundle rather than source code. `archive` is the zip."""

    def __init__(self, message: str, archive: Path):
        super().__init__(message)
        self.archive = Path(archive)


def find_zipped_bundle(source: Path | str) -> Path | None:
    """The zip if `source` is one, or is a published release folder (pipeline.zip beside its manifest.json, or
    a folder holding nothing but one zip); None for an ordinary source folder."""
    source = Path(source)
    if source.is_file():
        return source if source.suffix.lower() == ".zip" else None
    if not source.is_dir():
        return None
    published = source / ARTIFACT_NAME
    if published.is_file():
        return published
    try:
        entries = [p for p in source.iterdir() if not p.name.startswith(".") and p.name != "manifest.json"]
    except OSError:
        return None
    zips = [p for p in entries if p.is_file() and p.suffix.lower() == ".zip"]
    return zips[0] if len(zips) == 1 and len(entries) == 1 else None


def _unzip_python_root(archive: Path, host: str) -> str:
    """The entry point of an unzipped bundle: the manifest beside the zip says; otherwise the host's default."""
    try:
        return parse_manifest((archive.parent / "manifest.json").read_text(encoding="utf-8-sig")).python_root
    except (OSError, ConfigError):
        return _host_defaults(host).get("python_root", ".")


def clone_bundle(
    config: LocalConfig, host: str, tag: str, *, release: str | None = None, source: Path | str | None = None,
    shared: Iterable = (), unzip: bool = False,
) -> Path:
    """Make `dev/<host>/<tag>` from a published `release` (installed first if need be) or from a bundle `source`
    folder with the `shared` packages merged in. Never overwrites: an existing tag is an error. Returns the folder.

    A `source` that is really a zipped bundle raises `ZippedSourceError`; with `unzip` it is extracted and cloned
    as it is (a published bundle already has its shared packages in it)."""
    validate_host(host)
    validate_id(tag, "version tag")
    if bool(release) == bool(source):
        raise PublishError("choose a published release or a source folder to start from, not both and not neither")
    layout = DataLayout(config.bundle_repository)
    destination = layout.dev / host / tag
    if destination.exists():
        raise PublishError(f"{host}/{tag} already exists in the dev folder; choose another version tag")
    archive = find_zipped_bundle(source) if source else None
    if archive and not unzip:
        raise ZippedSourceError(f"{source} holds a zipped bundle ({archive.name}), not source code", archive)
    layout.ensure()
    stage = layout.staging / f"clone__{host}__{tag}__{uuid.uuid4().hex[:8]}"
    try:
        if release:
            installed = pull_release(host, release, config)
            shutil.copytree(installed.release_root, stage, ignore=shutil.ignore_patterns(".complete"))
            python_root = installed.python_root.relative_to(installed.release_root).as_posix()
            origin = f"release {release}"
        elif archive:
            safe_extract(archive, stage)
            python_root = _unzip_python_root(archive, host)
            if not (stage / python_root).is_dir():
                raise PublishError(f"python_root {python_root!r} not found in {archive.name}; is it a bundle for {host}?")
            origin = f"zip {archive.resolve()}"
        else:
            if not Path(source).is_dir():
                raise PublishError(f"source folder not found: {source}")
            if not any(p.is_file() for p in Path(source).rglob("*")):
                raise PublishError(f"there are no files to clone in {source}")
            plan = plan_bundle(Path(source), host, list(shared))
            materialize_plan(plan, stage)
            python_root = plan.python_root
            origin = f"source {Path(source).resolve()}"
        atomic_write_text(stage / CLONE_MARKER, json.dumps({
            "schema_version": 1, "host": host, "tag": tag, "python_root": python_root, "origin": origin,
            "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }, indent=2) + "\n")
        destination.parent.mkdir(parents=True, exist_ok=True)
        try:
            rename_with_retry(stage, destination)
        except OSError as exc:
            raise PublishError(f"could not create {host}/{tag}: {exc}") from None
    finally:
        shutil.rmtree(stage, ignore_errors=True)
    return destination


def publish_to_repository(
    config: LocalConfig, host: str, version: str, *, bundle: str | None = None, source: Path | str | None = None,
    shared: Iterable = (),
) -> tuple[Manifest, Path]:
    """Publish a bundle as the immutable release `host`/`version` of the studio repository, which must be a folder.

    `bundle` is the tag of a bundle made on the Create tab (it already holds its shared packages). `source` is any
    bundle source folder, with the `shared` packages merged in as a publish does; usually they are already inside
    it or aren't needed, as the shared packages (logging) rarely change. Nothing selects the release afterwards:
    the studio config's `bundle_version` does. Returns the manifest and the release's folder."""
    validate_host(host)
    validate_id(version, "release version")
    if bool(bundle) == bool(source):
        raise PublishError("choose a local development bundle or a source folder to publish, not both and not neither")
    remote = config.remote_repository
    if not isinstance(remote, Path):
        raise PublishError(f"the repository is a web address ({remote.location}); publishing needs a repository folder")
    folder = DataLayout(config.bundle_repository).dev / host / validate_id(bundle, "bundle") if bundle else Path(source)
    if not bundle:
        archive = find_zipped_bundle(folder)
        if archive:
            raise ZippedSourceError(f"{folder} holds a zipped bundle ({archive.name}), not source code", archive)
    marker = read_clone_marker(folder)
    if marker is None and bundle:
        raise PublishError(f"{host}/{bundle} is not in the dev folder; create it first")
    if marker is not None:  # a complete bundle, laid out as a release: publish it as it is, without the marker
        python_root = validate_python_root(marker.get("python_root", "."))
        if not (folder / python_root).is_dir():
            raise PublishError(f"python_root {python_root!r} not found in {folder}")
        entries = [(name, path) for name, path in _collect(folder) if name != CLONE_MARKER]
        if not entries:
            raise PublishError(f"there are no files to publish in {folder}")
        manifest = _write_release(entries, remote, host, version, python_root)
    else:
        if not folder.is_dir():
            raise PublishError(f"source folder not found: {folder}")
        if not any(p.is_file() for p in folder.rglob("*")):
            raise PublishError(f"there are no files to publish in {folder}")
        manifest = publish_plan(plan_bundle(folder, host, list(shared)), remote, version)
    return manifest, remote / HOSTS_DIR / host / version


def list_clones(config: LocalConfig, host: str) -> list[str]:
    """The tags cloned for `host`, in sorted order."""
    folder = DataLayout(config.bundle_repository).dev / validate_host(host)
    try:
        return sorted(p.name for p in folder.iterdir() if p.is_dir() and read_clone_marker(p) is not None)
    except OSError:
        return []


@dataclass(frozen=True)
class ReleaseChoice:
    """A published release of one host that can be cloned."""

    release_id: str
    installed: bool  # already on this computer, so cloning needs no download
    studio_series: tuple = ()  # the DCC series the studio config currently selects it for


def _version_key(name: str) -> list:
    return [(0, int(part)) if part.isdigit() else (1, part) for part in re.split(r"[.\-_+]", name)]


def available_releases(config: LocalConfig, host: str) -> list[ReleaseChoice]:
    """The published releases of `host` worth offering: those installed here, those the studio config selects, and
    (when the repository is a folder, which can be listed) those published there. Newest first."""
    validate_host(host)
    installed = set(installed_releases(config, host))
    published = set(as_repository(config.remote_repository).list_folders(f"{HOSTS_DIR}/{host}"))
    studio: dict[str, list] = {}
    try:
        studio_config, _ = _load_studio_config(host, config, DataLayout(config.bundle_repository))
        for series, release in studio_config.hosts.get(host, {}).items():
            studio.setdefault(release, []).append(series)
    except (ConfigError, ReleaseUnavailableError, OSError):
        pass  # offline with no copy: the list is still useful without the marker
    names = {name for name in installed | published | set(studio) if _valid_id(name)}
    return [
        ReleaseChoice(name, name in installed, tuple(sorted(studio.get(name, ()))))
        for name in sorted(names, key=_version_key, reverse=True)
    ]


def _valid_id(name: str) -> bool:
    try:
        validate_id(name, "release")
    except ConfigError:
        return False
    return True


def installed_releases(config: LocalConfig, host: str) -> list[str]:
    """The published releases of `host` already installed on this computer."""
    layout = DataLayout(config.bundle_repository)
    try:
        names = [p.name for p in (layout.releases / validate_host(host)).iterdir() if p.is_dir()]
    except OSError:
        return []
    return sorted(name for name in names if _read_marker(layout.release_dir(host, name), host, name) is not None)


def read_overrides(config: LocalConfig) -> dict[str, str]:
    """{"<host>/<series>": tag}. A missing or unreadable file means no overrides."""
    try:
        data = json.loads(DataLayout(config.bundle_repository).overrides_file.read_text(encoding="utf-8"))
        entries = data["overrides"]
    except (OSError, ValueError, KeyError, TypeError):
        return {}
    return {k: v for k, v in entries.items() if isinstance(k, str) and isinstance(v, str)} if isinstance(entries, dict) else {}


def get_override(config: LocalConfig, host: str, series: str) -> str | None:
    return read_overrides(config).get(f"{validate_host(host)}/{validate_series(series)}")


def set_override(config: LocalConfig, host: str, series: str, tag: str | None) -> None:
    """Launch `host` `series` from the clone `tag`, or with no override when `tag` is None. Remembered until cleared."""
    key = f"{validate_host(host)}/{validate_series(series)}"
    entries = read_overrides(config)
    if tag is None:
        entries.pop(key, None)
    else:
        if tag not in list_clones(config, host):
            raise ReleaseUnavailableError(f"{host}/{tag} is not in the dev folder; create it first", host=host)
        entries[key] = tag
    layout = DataLayout(config.bundle_repository)
    atomic_write_text(layout.overrides_file, json.dumps({"schema_version": 1, "overrides": entries}, indent=2, sort_keys=True) + "\n")


def override_source_folder(config: LocalConfig, host: str, series: str) -> Path | None:
    """The clone this host and series is overridden to launch from, or None. A clone that has gone is an error:
    a launch must never quietly run something other than what the user chose."""
    tag = get_override(config, host, series)
    if tag is None:
        return None
    folder = DataLayout(config.bundle_repository).dev / host / tag
    if read_clone_marker(folder) is None:
        raise ReleaseUnavailableError(
            f"{host} {series} is set to launch from dev/{host}/{tag}, which no longer exists; clear the override", host=host
        )
    return folder
