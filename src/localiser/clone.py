"""Clone a bundle into the dev folder to edit and run in place, and choose which clone a host launches with.

A clone is <local releases>/dev/<host>/<tag>/: a complete bundle laid out as a release would extract, plus a
`.tls-clone.json` marker. It is run where it is (see `sync.dev_release`), is never selected, synced or overwritten,
and is only removed by the user.
"""
import json
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from .config import LocalConfig, validate_host, validate_id, validate_series
from .errors import PublishError, ReleaseUnavailableError
from .fsutil import atomic_write_text, rename_with_retry
from .install import _read_marker
from .layout import CLONE_MARKER, DataLayout
from .publisher import materialize_plan, plan_bundle
from .sync import pull_release, read_clone_marker


def clone_bundle(
    config: LocalConfig, host: str, tag: str, *, release: str | None = None, source: Path | str | None = None,
    shared: Iterable = (),
) -> Path:
    """Make `dev/<host>/<tag>` from a published `release` (installed first if need be) or from a bundle `source`
    folder with the `shared` packages merged in. Never overwrites: an existing tag is an error. Returns the folder."""
    validate_host(host)
    validate_id(tag, "version tag")
    if bool(release) == bool(source):
        raise PublishError("choose a published release or a source folder to clone, not both and not neither")
    layout = DataLayout(config.bundle_repository)
    destination = layout.dev / host / tag
    if destination.exists():
        raise PublishError(f"{host}/{tag} already exists in the dev folder; choose another version tag")
    layout.ensure()
    stage = layout.staging / f"clone__{host}__{tag}__{uuid.uuid4().hex[:8]}"
    try:
        if release:
            installed = pull_release(host, release, config)
            shutil.copytree(installed.release_root, stage, ignore=shutil.ignore_patterns(".complete"))
            python_root = installed.python_root.relative_to(installed.release_root).as_posix()
            origin = f"release {release}"
        else:
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


def list_clones(config: LocalConfig, host: str) -> list[str]:
    """The tags cloned for `host`, in sorted order."""
    folder = DataLayout(config.bundle_repository).dev / validate_host(host)
    try:
        return sorted(p.name for p in folder.iterdir() if p.is_dir() and read_clone_marker(p) is not None)
    except OSError:
        return []


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
            raise ReleaseUnavailableError(f"{host}/{tag} is not in the dev folder; clone it first", host=host)
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
