"""Explicit synchronization and local-only selection for DCC startup."""
import json
import logging
import os
import re
import shutil
from pathlib import Path
from typing import Mapping

from .api import ROOT_VARIABLE, LocalisedRelease, host_variable, localise
from .config import (
    LocalConfig,
    default_pipeline_root,
    load_local_config,
    validate_host,
    validate_id,
    validate_python_root,
    validate_series,
)
from .errors import ConfigError, PublishError, ReleaseUnavailableError
from .fsutil import atomic_write_text
from .install import LocalRelease, _read_marker, ensure_release
from .layout import CLONE_MARKER, DataLayout
from .logs import log_event
from .publisher import plan_bundle
from .resolve import override_variable

SHARED_VARIABLE = "TLS_PIPELINE_SHARED_SOURCES"  # folders of shared packages a dev source gets on sys.path (os.pathsep list)
_LEGACY_COPY = re.compile(r"^[0-9a-f]{8}$")  # what dev copies were named before dev sources ran in place


def source_variable(host: str) -> str:
    """TLS_PIPELINE_<HOST>_SOURCE: an unpublished bundle source folder to run instead of any release."""
    return f"{host_variable(host)}_SOURCE"


def pipeline_root(environ: Mapping[str, str]) -> Path:
    """The pipeline root: TLS_PIPELINE if set, otherwise the per-user default location when it has been installed."""
    root = environ.get(ROOT_VARIABLE, "").strip()
    if root:
        return Path(root)
    default = default_pipeline_root(environ)
    if default is not None and (default / "config.json").is_file():
        return default
    raise ConfigError(
        f"{ROOT_VARIABLE} is not set and there is no installation at {default or 'the default location'}; "
        "installation or repair is required"
    )


def pipeline_config(environ: Mapping[str, str]) -> LocalConfig:
    return load_local_config(pipeline_root(environ) / "config.json", environ)


def sync_release(
    host: str, series: str, config: LocalConfig, environ: Mapping[str, str] | None = None
) -> LocalisedRelease:
    """Prepare a complete bundle, then atomically select it for future DCC sessions."""
    release = localise(host, series, config, environ)
    if not release.python_root.is_dir():
        raise ReleaseUnavailableError(
            "cached bundle is incomplete; repair required before sync", host=host, release_id=release.release_id
        )
    state = {"schema_version": 1, "release_id": release.release_id}
    atomic_write_text(
        DataLayout(config.bundle_repository).prepared_file(host, series),
        json.dumps(state, sort_keys=True) + "\n",
    )
    return release


def prepared_release(host: str, series: str, config: LocalConfig) -> LocalisedRelease:
    """Read only local state and a completion marker; never resolve, download or repair."""
    validate_host(host)
    validate_series(series)
    layout = DataLayout(config.bundle_repository)
    try:
        state = json.loads(layout.prepared_file(host, series).read_text(encoding="utf-8"))
        if not isinstance(state, dict) or type(state.get("schema_version")) is not int or state["schema_version"] != 1:
            raise ValueError("invalid prepared selection")
        release_id = validate_id(state.get("release_id"), "prepared release_id")
    except (OSError, ValueError, ConfigError) as exc:
        raise ReleaseUnavailableError(
            f"no valid prepared bundle for {host} {series}; run sync before starting the DCC ({exc})",
            host=host,
        ) from None
    local = _read_marker(layout.release_dir(host, release_id), host, release_id)
    if local is None or not local.python_root.is_dir():
        raise ReleaseUnavailableError(
            "prepared bundle is incomplete; run sync before starting the DCC", host=host, release_id=release_id
        )
    return LocalisedRelease(host, series, release_id, "prepared", local.release_root, local.python_root)


def pull_release(host: str, release_id: str, config: LocalConfig, *, lock_timeout: float = 60.0) -> LocalRelease:
    """Install a release into the local store without selecting it, so a pin or a project launch can use it.

    Pulling never changes what any host or series starts with by default.
    """
    validate_host(host)
    validate_id(release_id, "release_id")
    layout = DataLayout(config.bundle_repository)
    release = ensure_release(
        layout, config.remote_repository, host, release_id, host=host, lock_timeout=lock_timeout
    )
    if not release.python_root.is_dir():
        raise ReleaseUnavailableError(
            "cached bundle is incomplete; repair required", host=host, release_id=release_id
        )
    return release


def pinned_release(host: str, series: str, config: LocalConfig, release_id: str) -> LocalisedRelease:
    """A specific installed release for this session. Never downloads; the release must have been pulled."""
    layout = DataLayout(config.bundle_repository)
    release_id = validate_id(release_id, override_variable(host))
    local = _read_marker(layout.release_dir(host, release_id), host, release_id)
    if local is None or not local.python_root.is_dir():
        raise ReleaseUnavailableError(
            f"pinned bundle {release_id} is not installed for {host}; "
            f"run: python -m localiser pull {host} {release_id}",
            host=host,
            release_id=release_id,
        )
    log_event(logging.WARNING, "pinned_release_in_use", host=host, release=release_id)
    return LocalisedRelease(host, series, release_id, "pinned", local.release_root, local.python_root)


def _shared_folders(environ: Mapping[str, str]) -> list:
    return [part for part in environ.get(SHARED_VARIABLE, "").split(os.pathsep) if part.strip()]


def read_clone_marker(folder: Path) -> dict | None:
    """The marker `clone_bundle` leaves in a folder it made, or None if `folder` is an ordinary bundle source."""
    try:
        data = json.loads((Path(folder) / CLONE_MARKER).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def clean_legacy_dev_copies(config: LocalConfig) -> int:
    """Best effort: remove the throwaway <host>/<8 hex>/<version> copies older versions made at every start.

    Folders with a clone marker are the user's and are never touched. Returns how many were removed."""
    removed = 0
    dev = DataLayout(config.bundle_repository).dev
    try:
        folders = [path for host_dir in dev.iterdir() if host_dir.is_dir() for path in host_dir.iterdir()]
    except OSError:
        return 0
    for folder in folders:
        if folder.is_dir() and _LEGACY_COPY.match(folder.name) and read_clone_marker(folder) is None:
            shutil.rmtree(folder, ignore_errors=True)
            removed += not folder.exists()
    return removed


def dev_release(
    host: str, series: str, config: LocalConfig, source: str, environ: Mapping[str, str]
) -> LocalisedRelease:
    """Run an unpublished bundle source where it is. Nothing is copied: the copy was made at every DCC start, and
    a DCC can start several processes. The shared packages are put on sys.path from their own folders instead
    of being merged in. A folder made by `clone_bundle` is already a complete bundle. No change to any selection."""
    validate_host(host)
    validate_series(series)
    source_path = Path(source).resolve()
    marker = read_clone_marker(source_path)
    if marker is not None:
        python_root = validate_python_root(marker.get("python_root", "."))
        shared = []
        if not (source_path / python_root).is_dir():
            raise PublishError(f"python_root {python_root!r} not found in the clone {source_path}")
    else:
        shared = _shared_folders(environ)
        python_root = plan_bundle(source_path, host, shared).python_root  # checks it can be published as it runs
    log_event(logging.WARNING, "dev_source_in_use", host=host, source=source_path, shared=",".join(shared))
    return LocalisedRelease(
        host, series, f"dev-{source_path.name}", "dev", source_path,
        source_path if python_root == "." else source_path / python_root,
        tuple(str(Path(folder).resolve()) for folder in shared),
    )


def startup_release(
    host: str, series: str, config: LocalConfig, environ: Mapping[str, str]
) -> LocalisedRelease:
    """What a DCC session starts with, using only local files. In order of precedence:

    1. TLS_PIPELINE_<HOST>_SOURCE: an unpublished bundle source folder (dev mode).
    2. TLS_PIPELINE_<HOST>_BUNDLE: a pinned, already installed release.
    3. The release `sync` selected for this host and series.

    A source or pin that can't be used is an error, never a quiet fallback to the default.
    """
    source = environ.get(source_variable(host), "").strip()
    if source:
        return dev_release(host, series, config, source, environ)
    pin = environ.get(override_variable(host), "").strip()
    if pin:
        return pinned_release(host, series, config, pin)
    return prepared_release(host, series, config)


def load_prepared_release(
    host: str, series: str, environ: Mapping[str, str] | None = None
) -> LocalisedRelease:
    """Find machine configuration through TLS_PIPELINE and load what this session should start with."""
    environ = os.environ if environ is None else environ
    return startup_release(host, series, pipeline_config(environ), environ)


def host_enabled(host: str, series: str, environ: Mapping[str, str] | None = None) -> bool:
    """Whether the pipeline should load in this DCC.

    An empty `hosts` in the local config enables everything. Once hosts are listed, only those series load, so
    a Maya or Blender version the user doesn't use is left alone. A source or pin asked for explicitly
    always loads.
    """
    environ = os.environ if environ is None else environ
    config = pipeline_config(environ)
    if environ.get(source_variable(host), "").strip() or environ.get(override_variable(host), "").strip():
        return True
    return not config.hosts or series in config.hosts.get(host, ())
