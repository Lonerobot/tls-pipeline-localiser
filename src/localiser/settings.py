"""Change the local config (config.json in the pipeline root) from a tool such as the tray app.

Only the keys given are changed; anything else in the file, comments included, is kept. The result is
validated with the same parser the pipeline uses before it is written, and written atomically, so a
rejected change leaves the file as it was.
"""
import json
import os
from dataclasses import replace
from pathlib import Path
from typing import Iterable, Mapping

from .config import LocalConfig, parse_local_config, validate_host, validate_series
from .errors import ConfigError
from .fsutil import atomic_write_text
from .provision import Action, provision, unprovision

EDITABLE_KEYS = ("remote_repository", "bundle_repository", "hosts", "check_interval_minutes", "auto_sync")
SCHEMA_VERSION = 1


def _read_document(path: Path) -> dict:
    try:
        text = path.read_text(encoding="utf-8-sig")
    except FileNotFoundError:
        return {"schema_version": SCHEMA_VERSION}
    except OSError as exc:
        raise ConfigError(f"local config not readable ({exc})") from None
    try:
        document = json.loads(text)
    except ValueError as exc:
        raise ConfigError(f"local config is not valid JSON ({exc}); fix it by hand before changing it") from None
    if not isinstance(document, dict):
        raise ConfigError("local config must be a JSON object")
    return document


def _json_value(key: str, value):
    if key in ("remote_repository", "bundle_repository"):
        return os.fspath(value) if isinstance(value, os.PathLike) else value
    if key == "hosts":
        if not isinstance(value, Mapping):
            raise ConfigError("hosts must map each host to its series")
        hosts = {}
        for host, series in value.items():
            validate_host(host)
            if isinstance(series, str):
                raise ConfigError(f"hosts.{host} must be a list of series, not a string")
            unique = list(dict.fromkeys(validate_series(item) for item in series))
            if unique:  # a host with no series is simply not enabled
                hosts[host] = unique
        return hosts
    return value


def save_local_config(path: Path, changes: Mapping) -> LocalConfig:
    """Apply `changes` to the config file at `path` (created if missing) and return the validated result."""
    path = Path(path).absolute()
    unknown = sorted(set(changes) - set(EDITABLE_KEYS))
    if unknown:
        raise ConfigError(f"cannot change {', '.join(unknown)}; editable keys are {', '.join(EDITABLE_KEYS)}")
    document = _read_document(path)
    document.setdefault("schema_version", SCHEMA_VERSION)
    for key, value in changes.items():
        document[key] = _json_value(key, value)
    text = json.dumps(document, indent=4) + "\n"
    config = parse_local_config(text, path.parent)  # raises ConfigError, before anything is written
    atomic_write_text(path, text)
    return config


def _leaving(old: Mapping, new: Mapping) -> dict:
    """What `unprovision` should remove. Maya and Nuke have one entry for all series, so those only go when
    the last series does; Blender has an entry per series."""
    leaving = {}
    for host, old_series in old.items():
        new_series = tuple(new.get(host, ()))
        if host == "blender":
            gone = tuple(series for series in old_series if series not in new_series)
        else:
            gone = tuple(old_series) if not new_series else ()
        if gone:
            leaving[host] = gone
    return leaving


def apply_hosts(
    root: Path,
    enabled: Mapping[str, Iterable[str]],
    environ: Mapping[str, str] | None = None,
    changes: Mapping | None = None,
) -> tuple[LocalConfig, list[Action]]:
    """Enable exactly the hosts and series in `enabled`: save the config, remove the entries of what was
    switched off, and install the entry for what is on. Idempotent.

    `changes` (other local config keys) go into the same validated write, so a bad value changes nothing."""
    root = Path(root)
    config_path = root / "config.json"
    old = _read_current(config_path)
    saved = {**(changes or {}), "hosts": {host: list(series) for host, series in enabled.items()}}
    config = save_local_config(config_path, saved)
    actions = unprovision(replace(config, hosts=_leaving(old.hosts, config.hosts)), environ) if old else []
    actions += provision(root, config, environ)
    return config, actions


def _read_current(config_path: Path) -> LocalConfig | None:
    if not config_path.is_file():
        return None
    try:
        return parse_local_config(config_path.read_text(encoding="utf-8-sig"), config_path.parent)
    except (ConfigError, OSError):
        return None  # can't tell what was enabled before; nothing is removed
