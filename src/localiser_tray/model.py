"""What the tray app decides, with no Qt in it: when to check, what to sync, how to summarise and what to say."""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping

from localiser.config import LocalConfig
from localiser.hosts import HOSTS, detect_installed_series
from localiser.status import (
    CURRENT,
    ERROR,
    NOT_PREPARED,
    OFFLINE,
    UNSUPPORTED,
    UPDATE_AVAILABLE,
    EntryStatus,
    check_entry,
    enabled_entries,
    sync_entry,
    write_status,
)

LEVEL_IDLE = "idle"  # nothing enabled
LEVEL_OK = "ok"
LEVEL_UPDATE = "update"  # something newer is waiting to be applied
LEVEL_PROBLEM = "problem"

NEEDS_SYNC = (UPDATE_AVAILABLE, NOT_PREPARED)


@dataclass(frozen=True)
class Change:
    host: str
    series: str
    previous: str | None
    current: str


@dataclass(frozen=True)
class CycleResult:
    entries: list
    changes: list = field(default_factory=list)  # selections that moved during this cycle
    synced: bool = False  # whether this cycle applied updates

    @property
    def level(self) -> str:
        return overall(self.entries)[0]


def display_name(host: str) -> str:
    info = HOSTS.get(host)
    return info.display_name if info else host


def describe(entry: EntryStatus) -> str:
    """One line a person can read: what this host and series is running and whether that's right."""
    state = entry.state
    if state == CURRENT:
        return f"Up to date ({entry.selected})"
    if state == UPDATE_AVAILABLE:
        return f"Update available: {entry.selected} -> {entry.target}"
    if state == NOT_PREPARED:
        return f"Not installed yet (studio release {entry.target})" if entry.target else "Not installed yet"
    if state == OFFLINE:
        have = f", using {entry.selected}" if entry.selected else ", nothing installed"
        return f"Can't reach the repository{have}"
    if state == UNSUPPORTED:
        return "Not supported by the studio config"
    return entry.message or "Something went wrong"


def overall(entries: list) -> tuple[str, str]:
    """The single level and sentence for the tray icon, worst state first."""
    if not entries:
        return LEVEL_IDLE, "No applications enabled"
    states = [entry.state for entry in entries]
    errors = states.count(ERROR)
    offline = states.count(OFFLINE)
    if errors:
        return LEVEL_PROBLEM, f"{errors} problem(s) - open the pipeline manager"
    if offline:
        return LEVEL_PROBLEM, "Can't reach the repository" if offline == len(states) else "Some updates can't be checked"
    waiting = sum(state in NEEDS_SYNC for state in states)
    if waiting:
        return LEVEL_UPDATE, f"{waiting} update(s) ready to install"
    return LEVEL_OK, "Pipeline is up to date"


def parse_time(value) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def is_due(status: dict | None, interval_minutes: int, now: datetime | None = None) -> bool:
    """Whether the last recorded check is older than the interval (or there is none, or it can't be read)."""
    checked = parse_time((status or {}).get("checked_at"))
    if checked is None:
        return True
    now = now or datetime.now(timezone.utc)
    return (now - checked).total_seconds() >= interval_minutes * 60


def run_cycle(config: LocalConfig, environ: Mapping[str, str], auto_sync: bool | None = None) -> CycleResult:
    """Check every enabled host and series; when auto-sync is on, install and select what is newer.

    One entry failing never stops the others, and the result is recorded for the hosts and the window.
    """
    auto_sync = config.auto_sync if auto_sync is None else auto_sync
    entries, changes, synced = [], [], False
    for host, series in enabled_entries(config):
        entry = check_entry(host, series, config, environ)
        if auto_sync and entry.state in NEEDS_SYNC:
            after = sync_entry(host, series, config, environ)
            synced = True
            if after.state == CURRENT and after.selected != entry.selected:
                changes.append(Change(host, series, entry.selected, after.selected))
            entry = after
        entries.append(entry)
    write_status(config, entries)
    return CycleResult(entries, changes, synced)


def sync_now(config: LocalConfig, environ: Mapping[str, str]) -> CycleResult:
    """A cycle with auto-sync forced on: what the user gets from "Sync now"."""
    return run_cycle(config, environ, auto_sync=True)


def change_message(changes: list) -> str:
    """The tray notification after updates were applied. Running applications keep their release."""
    lines = [f"{display_name(c.host)} {c.series}: {c.current}" for c in changes]
    return "Pipeline updated - " + ", ".join(lines) + ". Restart open applications to use it."


@dataclass(frozen=True)
class HostChoice:
    host: str
    display_name: str
    icon: Path | None
    series: list  # (series, installed here, enabled) for every installed or enabled series, oldest first


def _series_key(series: str) -> list:
    return [int(part) if part.isdigit() else 0 for part in series.split(".")]


def host_choices(config: LocalConfig | None, roots: list | None = None) -> list:
    """Every supported host with the versions found on this machine plus any already enabled."""
    choices = []
    for name, info in HOSTS.items():
        installed = set(detect_installed_series(name, roots))
        enabled = set(config.hosts.get(name, ())) if config else set()
        series = sorted(installed | enabled, key=_series_key)
        choices.append(
            HostChoice(name, info.display_name, info.icon, [(s, s in installed, s in enabled) for s in series])
        )
    return choices
