"""Update status for every host and series a user has enabled.

`check_enabled` asks the repository what each should be running; `sync_enabled` brings each up to date.
Both record the result in the local state folder, where the tray app and the hosts read it without any
network access. One entry failing never stops the others.
"""
import json
import logging
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Mapping

from .config import LocalConfig, parse_studio_config
from .errors import (
    ConfigError,
    LocaliserError,
    NoBundleSelectedError,
    ReleaseUnavailableError,
    UnsupportedSeriesError,
)
from .fsutil import atomic_write_text
from .hosts import detect_installed_series
from .layout import DataLayout
from .logs import log_event
from .resolve import SOURCE_LAST_KNOWN, _load_studio_config, resolve_release
from .sync import clear_prepared, prepared_release, sync_release

STATUS_VERSION = 1

CURRENT = "current"  # the selected release is what the studio config asks for
UPDATE_AVAILABLE = "update_available"  # the studio config asks for a different release
NOT_PREPARED = "not_prepared"  # nothing is selected yet; run sync
OFFLINE = "offline"  # the repository can't be reached, so it can't be checked or fetched
UNSUPPORTED = "unsupported"  # the studio config has no release for this host or series
NO_BUNDLE = "no_bundle"  # the studio config lists it but selects no bundle: no pipeline loads once synced
ERROR = "error"  # anything else; the message says what
PROBLEMS = (OFFLINE, ERROR)  # states that make a command exit non-zero


@dataclass(frozen=True)
class EntryStatus:
    host: str
    series: str
    state: str
    selected: str | None  # the release a DCC would start with now
    target: str | None  # the release the studio config asks for
    message: str = ""


def needs_sync(entry: EntryStatus) -> bool:
    """Whether syncing would change what a DCC starts with."""
    return entry.state in (UPDATE_AVAILABLE, NOT_PREPARED) or (entry.state == NO_BUNDLE and entry.selected is not None)


def studio_pairs(config: LocalConfig, cached_only: bool = False) -> list[tuple[str, str]]:
    """Every (host, series) the studio config lists. `cached_only` reads only the last copy kept locally, for
    callers that mustn't touch the repository (the launcher is built on the UI thread)."""
    layout = DataLayout(config.bundle_repository)
    try:
        if cached_only:
            studio = parse_studio_config(layout.last_known_config.read_text(encoding="utf-8-sig"))
        else:
            studio, _ = _load_studio_config(None, config, layout)
    except (ConfigError, ReleaseUnavailableError, OSError):
        return []
    return [(host, series) for host, versions in sorted(studio.hosts.items()) for series in versions]


def enabled_entries(config: LocalConfig, cached_only: bool = False) -> list[tuple[str, str]]:
    """What this computer keeps up to date: the hosts and series listed in the local config. While it lists none,
    whatever the studio config lists that is installed here, so a fresh machine follows the studio with no setup
    (the same rule that has a DCC load the pipeline when no hosts are listed)."""
    if config.hosts:
        return [(host, series) for host, series_list in sorted(config.hosts.items()) for series in series_list]
    pairs = studio_pairs(config, cached_only)
    installed = {host: set(detect_installed_series(host)) for host in {host for host, _ in pairs}}
    return [(host, series) for host, series in pairs if series in installed[host]]


def _selected(host: str, series: str, config: LocalConfig) -> str | None:
    try:
        return prepared_release(host, series, config).release_id
    except (ReleaseUnavailableError, NoBundleSelectedError):
        return None


def check_entry(host: str, series: str, config: LocalConfig, environ: Mapping[str, str]) -> EntryStatus:
    """Compare what a DCC would start with against what the studio config asks for. Installs nothing."""
    selected = _selected(host, series, config)
    try:
        target = resolve_release(host, series, config, DataLayout(config.bundle_repository), environ)
    except NoBundleSelectedError as exc:
        return EntryStatus(host, series, NO_BUNDLE, selected, None, str(exc))
    except UnsupportedSeriesError as exc:
        return EntryStatus(host, series, UNSUPPORTED, selected, None, str(exc))
    except ReleaseUnavailableError as exc:
        return EntryStatus(host, series, OFFLINE, selected, None, str(exc))
    except ConfigError as exc:
        return EntryStatus(host, series, ERROR, selected, None, str(exc))
    if target.source == SOURCE_LAST_KNOWN:
        return EntryStatus(host, series, OFFLINE, selected, target.release_id, "the repository is unreachable")
    if selected is None:
        return EntryStatus(host, series, NOT_PREPARED, None, target.release_id, "run sync")
    if selected != target.release_id:
        return EntryStatus(host, series, UPDATE_AVAILABLE, selected, target.release_id)
    return EntryStatus(host, series, CURRENT, selected, target.release_id)


def sync_entry(host: str, series: str, config: LocalConfig, environ: Mapping[str, str]) -> EntryStatus:
    """Bring one host and series up to date, then report where it ended up."""
    before = check_entry(host, series, config, environ)
    if before.state == UNSUPPORTED:
        return before
    try:
        release = sync_release(host, series, config, environ)
    except NoBundleSelectedError as exc:
        try:
            clear_prepared(host, series, config)
        except OSError as write_error:
            return EntryStatus(host, series, ERROR, before.selected, None, str(write_error))
        log_event(logging.WARNING, "no_studio_bundle", host=host, series=series)
        return EntryStatus(host, series, NO_BUNDLE, None, None, str(exc))
    except ReleaseUnavailableError as exc:
        return EntryStatus(host, series, OFFLINE, before.selected, before.target, str(exc))
    except LocaliserError as exc:
        return EntryStatus(host, series, ERROR, before.selected, before.target, str(exc))
    return EntryStatus(host, series, CURRENT, release.release_id, release.release_id)


def check_enabled(config: LocalConfig, environ: Mapping[str, str]) -> list[EntryStatus]:
    entries = [check_entry(host, series, config, environ) for host, series in enabled_entries(config)]
    write_status(config, entries)
    return entries


def sync_enabled(config: LocalConfig, environ: Mapping[str, str]) -> list[EntryStatus]:
    entries = [sync_entry(host, series, config, environ) for host, series in enabled_entries(config)]
    write_status(config, entries)
    return entries


def write_status(config: LocalConfig, entries: list[EntryStatus]) -> None:
    """Record the result atomically. Failing to write it is logged, never raised: it's only a convenience."""
    layout = DataLayout(config.bundle_repository)
    document = {
        "schema_version": STATUS_VERSION,
        "checked_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "entries": [asdict(entry) for entry in entries],
    }
    try:
        atomic_write_text(layout.status_file, json.dumps(document, indent=2, sort_keys=True) + "\n")
    except OSError as exc:
        log_event(logging.WARNING, "status_write_failed", error=exc)


def read_status(config: LocalConfig) -> dict | None:
    """The last recorded result, or None if there is none or it can't be read."""
    try:
        document = json.loads(DataLayout(config.bundle_repository).status_file.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(document, dict) or document.get("schema_version") != STATUS_VERSION:
        return None
    return document


def selection_changed(host: str, series: str, loaded_release_id: str, config: LocalConfig) -> str | None:
    """For a running DCC: the release now selected, if it differs from the one this session loaded.

    Reads only local state, so a host can call it on a timer.
    """
    selected = _selected(host, series, config)
    return selected if selected and selected != loaded_release_id else None
