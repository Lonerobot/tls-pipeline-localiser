"""Public entry point used by host stubs. Imports no DCC modules and no pipeline code."""
import json
import logging
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, MutableMapping

from .config import LocalConfig, load_local_config, validate_host
from .errors import ConfigError
from .fsutil import atomic_write_text
from .install import ensure_release
from .layout import DataLayout
from .logs import log_event
from .resolve import resolve_release

ROOT_VARIABLE = "TLS_PIPELINE"  # the local pipeline root, which holds config.json


def host_variable(host: str) -> str:
    """TLS_PIPELINE_<HOST>: set to the resolved bundle path for that host."""
    return f"{ROOT_VARIABLE}_{validate_host(host).upper()}"


@dataclass(frozen=True)
class LocalisedRelease:
    host: str
    series: str
    release_id: str
    source: str
    release_root: Path
    python_root: Path


def localise(
    host: str,
    series: str,
    config: LocalConfig,
    environ: Mapping[str, str] | None = None,
    *,
    lock_timeout: float = 60.0,
) -> LocalisedRelease:
    """Select, localise and verify the bundle for `host` running DCC version `series`.

    Returns where it lives locally. The caller (a host stub) exposes it; see `expose_environment`.
    """
    started = time.monotonic()
    environ = os.environ if environ is None else environ
    layout = DataLayout(config.bundle_repository)

    resolution = resolve_release(host, series, config, layout, environ)
    local = ensure_release(
        layout,
        config.remote_repository,
        host,
        resolution.release_id,
        host=host,
        lock_timeout=lock_timeout,
    )
    result = LocalisedRelease(
        host=host,
        series=series,
        release_id=local.release_id,
        source=resolution.source,
        release_root=local.release_root,
        python_root=local.python_root,
    )
    _remember(layout, result)
    log_event(
        logging.INFO,
        "localised",
        host=host,
        series=series,
        release=result.release_id,
        source=result.source,
        root=result.release_root,
        elapsed_ms=int((time.monotonic() - started) * 1000),
    )
    return result


def ensure_local_release(
    host: str, series: str, environ: Mapping[str, str] | None = None, *, lock_timeout: float = 60.0
) -> LocalisedRelease:
    """Like `localise`, finding config.json in the folder named by TLS_PIPELINE."""
    environ = os.environ if environ is None else environ
    root = environ.get(ROOT_VARIABLE, "").strip()
    if not root:
        raise ConfigError(f"{ROOT_VARIABLE} is not set; installation or repair is required")
    config = load_local_config(Path(root) / "config.json")
    return localise(host, series, config, environ, lock_timeout=lock_timeout)


def expose_environment(release: LocalisedRelease, environ: MutableMapping[str, str] | None = None) -> None:
    """Set TLS_PIPELINE_<HOST> to the resolved bundle path, for the pipeline inside the bundle to read."""
    environ = os.environ if environ is None else environ
    environ[host_variable(release.host)] = str(release.release_root)


def _remember(layout: DataLayout, release: LocalisedRelease) -> None:
    """Per-host convenience cache; the completion marker stays the source of truth."""
    state = {
        "schema_version": 1,
        "host": release.host,
        "series": release.series,
        "release_id": release.release_id,
        "source": release.source,
        "root": str(release.release_root),
    }
    path = layout.host_state_file(release.host)
    try:
        if json.loads(path.read_text(encoding="utf-8")) == state:
            return
    except (OSError, ValueError):
        pass  # missing or unreadable state is simply rewritten
    try:
        atomic_write_text(path, json.dumps(state, indent=2, sort_keys=True) + "\n")
    except OSError as exc:
        log_event(logging.WARNING, "host_state_write_failed", host=release.host, error=exc)
