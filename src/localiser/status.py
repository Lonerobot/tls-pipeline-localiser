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

from .config import LocalConfig
from .errors import ConfigError, LocaliserError, ReleaseUnavailableError, UnsupportedSeriesError
from .fsutil import atomic_write_text
from .layout import DataLayout
from .logs import log_event
from .resolve import SOURCE_LAST_KNOWN, resolve_release
from .sync import prepared_release, sync_release

STATUS_VERSION = 1

CURRENT = "current"  # the selected release is what the studio config asks for
UPDATE_AVAILABLE = "update_available"  # the studio config asks for a different release
NOT_PREPARED = "not_prepared"  # nothing is selected yet; run sync
OFFLINE = "offline"  # the repository can't be reached, so it can't be checked or fetched
UNSUPPORTED = "unsupported"  # the studio config has no release for this host or series
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


def enabled_entries(config: LocalConfig) -> list[tuple[str, str]]:
    return [(host, series) for host, series_list in sorted(config.hosts.items()) for series in series_list]


def _selected(host: str, series: str, config: LocalConfig) -> str | None:
    try:
        return prepared_release(host, series, config).release_id
    except ReleaseUnavailableError:
        return None


def check_entry(host: str, series: str, config: LocalConfig, environ: Mapping[str, str]) -> EntryStatus:
    """Compare what a DCC would start with against what the studio config asks for. Installs nothing."""
    selected = _selected(host, series, config)
    try:
        target = resolve_release(host, series, config, DataLayout(config.bundle_repository), environ)
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
