"""Explicit synchronization and local-only selection for DCC startup."""
import json
import logging
import os
import shutil
import time
import uuid
from pathlib import Path
from typing import Mapping

from .api import ROOT_VARIABLE, LocalisedRelease, host_variable, localise
from .config import LocalConfig, default_pipeline_root, load_local_config, validate_host, validate_id, validate_series
from .errors import ConfigError, ReleaseUnavailableError
from .fsutil import atomic_write_text
from .install import LocalRelease, _read_marker, ensure_release
from .layout import DataLayout
from .logs import log_event
from .publisher import materialize_plan, plan_bundle
from .resolve import override_variable

SHARED_VARIABLE = "TLS_PIPELINE_SHARED_SOURCES"  # folders of shared packages merged into a dev source (os.pathsep list)
DEV_KEEP_SECONDS = 3 * 24 * 3600  # unused dev copies older than this are removed the next time one is made


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
    return load_local_config(pipeline_root(environ) / "config.json")


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


def _clean_dev_copies(host_dir: Path) -> None:
    """Best effort: remove old throwaway copies. One still in use, or locked, is left alone."""
    if not host_dir.is_dir():
        return
    cutoff = time.time() - DEV_KEEP_SECONDS
    for entry in host_dir.iterdir():
        try:
            if entry.is_dir() and entry.stat().st_mtime < cutoff:
                shutil.rmtree(entry, ignore_errors=True)
        except OSError:
            pass


def dev_release(
    host: str, series: str, config: LocalConfig, source: str, environ: Mapping[str, str]
) -> LocalisedRelease:
    """Run an unpublished bundle source folder: lay it out exactly as a release would extract, with the shared
    packages merged in, in a throwaway folder. No zip, no checksum and no change to any selection."""
    validate_host(host)
    validate_series(series)
    source_path = Path(source).resolve()
    plan = plan_bundle(source_path, host, _shared_folders(environ))
    host_dir = DataLayout(config.bundle_repository).dev / host
    _clean_dev_copies(host_dir)
    # The folder is named after the source (1.0.1, say), so anything that shows the release folder name shows that.
    stage = host_dir / uuid.uuid4().hex[:8] / source_path.name
    python_root = materialize_plan(plan, stage)
    log_event(logging.WARNING, "dev_source_in_use", host=host, source=source_path, shared=",".join(plan.shared))
    return LocalisedRelease(host, series, f"dev-{source_path.name}", "dev", stage, python_root)


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
