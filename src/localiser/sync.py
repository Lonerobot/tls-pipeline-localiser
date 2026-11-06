"""Explicit synchronization and local-only selection for DCC startup."""
import json
import os
from pathlib import Path
from typing import Mapping

from .api import ROOT_VARIABLE, LocalisedRelease, localise
from .config import LocalConfig, load_local_config, validate_host, validate_id, validate_series
from .errors import ConfigError, ReleaseUnavailableError
from .fsutil import atomic_write_text
from .install import _read_marker
from .layout import DataLayout


def pipeline_config(environ: Mapping[str, str]) -> LocalConfig:
    root = environ.get(ROOT_VARIABLE, "").strip()
    if not root:
        raise ConfigError(f"{ROOT_VARIABLE} is not set; installation or repair is required")
    return load_local_config(Path(root) / "config.json")


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


def load_prepared_release(
    host: str, series: str, environ: Mapping[str, str] | None = None
) -> LocalisedRelease:
    """Find machine configuration through TLS_PIPELINE and load a prepared bundle."""
    environ = os.environ if environ is None else environ
    return prepared_release(host, series, pipeline_config(environ))
