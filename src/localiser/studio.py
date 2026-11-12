"""Edit the studio config (`config.json` in the remote repository): which bundle each application version uses.

This is the one place that writes it. It is for the admin mode of the tray app and the `studio` command; it works
only when the repository is a folder. A write re-reads the file first, changes the one entry asked for, keeps
everything else (comments, other entries, their order) and is validated with the parser every reader uses before it
replaces the file atomically. Edits are rare, so there is no locking beyond that replace.
"""
import json
import os
from pathlib import Path

from .config import LocalConfig, parse_studio_config, validate_host, validate_id, validate_series
from .errors import ConfigError
from .fsutil import atomic_write_text

STUDIO_FILE = "config.json"
SCHEMA_VERSION = 1


def studio_file(config: LocalConfig) -> Path:
    """The studio config's path, or an error saying it can't be edited (a web repository is read-only)."""
    remote = config.remote_repository
    if not isinstance(remote, Path):
        raise ConfigError(f"the repository is a web address ({remote.location}); the studio config can't be edited here")
    return remote / STUDIO_FILE


def can_edit_studio(config: LocalConfig) -> tuple[bool, str]:
    """Whether the studio config can be edited from this computer, and if not, why."""
    try:
        path = studio_file(config)
    except ConfigError as exc:
        return False, str(exc)
    folder = path.parent
    if not folder.is_dir():
        return False, f"the repository folder can't be reached ({folder})"
    try:
        if path.exists() and not os.access(path, os.W_OK):
            return False, f"{path} is read-only for you"
        if not os.access(folder, os.W_OK):
            return False, f"you can't write to the repository folder ({folder})"
    except OSError as exc:
        return False, str(exc)
    return True, ""


def _read_document(path: Path) -> dict:
    try:
        text = path.read_text(encoding="utf-8-sig")
    except FileNotFoundError:
        return {"schema_version": SCHEMA_VERSION, "hosts": {}}
    except OSError as exc:
        raise ConfigError(f"studio config not readable ({exc})") from None
    try:
        document = json.loads(text)
    except ValueError as exc:
        raise ConfigError(f"studio config is not valid JSON ({exc}); fix it by hand before changing it") from None
    if not isinstance(document, dict):
        raise ConfigError("studio config must be a JSON object")
    return document


def studio_entries(config: LocalConfig) -> dict[tuple[str, str], str | None]:
    """{(host, series): bundle version or None} as the repository's studio config has it now."""
    path = studio_file(config)
    try:
        studio = parse_studio_config(path.read_text(encoding="utf-8-sig"))
    except OSError as exc:
        raise ConfigError(f"studio config not readable ({exc})") from None
    return {(host, series): version for host, series_map in studio.hosts.items() for series, version in series_map.items()}


def set_studio_bundle(config: LocalConfig, host: str, series: str, release: str | None) -> None:
    """Make `host` `series` use `release` (an id) or no bundle (None) in the studio config."""
    validate_host(host)
    validate_series(series)
    if release is not None:
        validate_id(release, "bundle_version")
    path = studio_file(config)
    document = _read_document(path)
    document.setdefault("schema_version", SCHEMA_VERSION)
    hosts = document.setdefault("hosts", {})
    if not isinstance(hosts, dict):
        raise ConfigError("studio config 'hosts' must be an object")
    series_map = hosts.setdefault(host, {})
    if not isinstance(series_map, dict):
        raise ConfigError(f"studio config 'hosts.{host}' must be an object")
    entry = series_map.get(series)
    series_map[series] = {**entry, "bundle_version": release} if isinstance(entry, dict) else {"bundle_version": release}
    text = json.dumps(document, indent=4) + "\n"
    parse_studio_config(text)  # raises ConfigError, before anything is written
    atomic_write_text(path, text)
