"""Select which bundle a host should use: override, studio config, or last-known-good config."""
import logging
from dataclasses import dataclass
from typing import Mapping

from .config import LocalConfig, parse_studio_config, validate_host, validate_id, validate_series
from .errors import ReleaseUnavailableError
from .fsutil import atomic_write_text
from .layout import DataLayout
from .logs import log_event
from .repository import as_repository

ROOT_VARIABLE = "TLS_PIPELINE"  # the local pipeline root; also the prefix of the per-host variables
SOURCE_OVERRIDE = "override"
SOURCE_STUDIO = "studio"
SOURCE_LAST_KNOWN = "last_known_config"


@dataclass(frozen=True)
class Resolution:
    host: str
    series: str
    release_id: str
    source: str


def override_variable(host: str) -> str:
    """TLS_PIPELINE_<HOST>_BUNDLE: the release to use instead of the studio default.

    `sync` selects it machine-wide (pulling it if needed); at DCC startup it is a pin for that session only.
    """
    return f"{ROOT_VARIABLE}_{validate_host(host).upper()}_BUNDLE"


def resolve_release(
    host: str, series: str, config: LocalConfig, layout: DataLayout, environ: Mapping[str, str]
) -> Resolution:
    """Pick the bundle version for `host` running DCC version `series`."""
    validate_host(host)
    validate_series(series)

    variable = override_variable(host)
    override = environ.get(variable, "").strip()
    if override:
        release_id = validate_id(override, variable)
        log_event(logging.WARNING, "override_in_use", host=host, release=release_id, variable=variable)
        return Resolution(host, series, release_id, SOURCE_OVERRIDE)

    studio, source = _load_studio_config(host, config, layout)
    return Resolution(host, series, studio.bundle_version(host, series), source)


def _load_studio_config(host, config, layout):
    """Read the studio config from the remote repository; if it is unreachable, use the last-known-good copy."""
    try:
        text = as_repository(config.remote_repository).read_text("config.json")
    except OSError as share_error:
        try:
            text = layout.last_known_config.read_text(encoding="utf-8-sig")
        except OSError:
            raise ReleaseUnavailableError(
                f"studio config unreachable ({share_error}) and no last-known-good copy", host=host
            ) from None
        log_event(logging.WARNING, "stale_studio_config", host=host, reason=share_error)
        return parse_studio_config(text), SOURCE_LAST_KNOWN

    config = parse_studio_config(text)
    _remember_config(layout, text)
    return config, SOURCE_STUDIO


def _remember_config(layout: DataLayout, text: str) -> None:
    """Keep a validated copy for offline launches; skip the write when nothing changed."""
    try:
        if layout.last_known_config.read_text(encoding="utf-8") == text:
            return
    except OSError:
        pass  # no copy yet
    try:
        atomic_write_text(layout.last_known_config, text)
    except OSError as exc:
        # The copy is only a convenience; a failure to refresh it must not block the launch.
        log_event(logging.WARNING, "last_known_config_write_failed", error=exc)
