"""Parsing and validation of the local config, studio (remote) config and release manifest.

Anything malformed or of an unknown schema version is an error; nothing is guessed.
Top-level keys starting with "_" (such as "_comment_hosts") are comments and are ignored.
"""
import json
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Mapping
from urllib.parse import urlsplit
from urllib.request import url2pathname

from .errors import ConfigError, NoBundleSelectedError, UnsupportedSeriesError
from .repository import WebRepository, parse_web_url

SCHEMA_VERSION = 1
DEFAULT_CHECK_INTERVAL_MINUTES = 240
MIN_CHECK_INTERVAL_MINUTES = 5
MAX_CHECK_INTERVAL_MINUTES = 7 * 24 * 60

_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._+-]{0,127}$")
_HOST_RE = re.compile(r"^[a-z][a-z0-9_]{0,31}$")
_SERIES_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,31}$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def validate_id(value, what: str) -> str:
    """IDs become path components, so they must be a single safe component."""
    if not isinstance(value, str) or not _ID_RE.match(value):
        raise ConfigError(f"invalid {what}: {value!r}")
    return value


def validate_host(value) -> str:
    if not isinstance(value, str) or not _HOST_RE.match(value):
        raise ConfigError(f"invalid host name: {value!r}")
    return value


def validate_series(value) -> str:
    """The DCC version an entry applies to, such as '2026' (Maya), '5.2' (Blender) or '17.0' (Nuke)."""
    if not isinstance(value, str) or not _SERIES_RE.match(value):
        raise ConfigError(f"invalid DCC series: {value!r}")
    return value


def validate_python_root(value) -> str:
    """Return a normalised relative POSIX path inside the release, '.' meaning the release root."""
    if not isinstance(value, str) or not value or "\\" in value or ":" in value or "\x00" in value:
        raise ConfigError(f"invalid python_root: {value!r}")
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts:
        raise ConfigError(f"python_root must stay inside the release: {value!r}")
    return path.as_posix()


def _load_object(text: str, what: str) -> dict:
    try:
        data = json.loads(text)
    except ValueError as exc:
        raise ConfigError(f"{what} is not valid JSON: {exc}") from None
    if not isinstance(data, dict):
        raise ConfigError(f"{what} must be a JSON object")
    return data


def _check_schema(data: dict, what: str) -> None:
    version = data.get("schema_version")
    # bool is an int subclass, so True would otherwise pass as version 1.
    if type(version) is not int or version != SCHEMA_VERSION:
        raise ConfigError(f"{what} has unsupported schema_version: {version!r}")


@dataclass(frozen=True)
class StudioConfig:
    """The studio default: hosts[<host>][<dcc series>] -> bundle version, or None when the studio lists the
    version but has selected no bundle for it."""

    hosts: dict[str, dict[str, str | None]]

    def entry(self, host: str, series: str) -> str | None:
        """The bundle version for `host` `series`, or None for "no bundle". Raises if there is no entry at all."""
        versions = self.hosts.get(host)
        if versions is None:
            raise UnsupportedSeriesError(f"studio config has no entry for host {host!r}")
        if series not in versions:
            raise UnsupportedSeriesError(
                f"studio config has no entry for {host} {series!r}; available: {', '.join(sorted(versions))}"
            )
        return versions[series]

    def bundle_version(self, host: str, series: str) -> str:
        version = self.entry(host, series)
        if version is None:
            raise NoBundleSelectedError(host, series)
        return version


def parse_studio_config(text: str) -> StudioConfig:
    data = _load_object(text, "studio config")
    _check_schema(data, "studio config")
    raw_hosts = data.get("hosts")
    if not isinstance(raw_hosts, dict):
        raise ConfigError("studio config 'hosts' must be an object")
    hosts = {}
    for host, raw_series in raw_hosts.items():
        validate_host(host)
        if not isinstance(raw_series, dict):
            raise ConfigError(f"studio config 'hosts.{host}' must be an object")
        hosts[host] = {}
        for series, entry in raw_series.items():
            validate_series(series)
            if not isinstance(entry, dict):
                raise ConfigError(f"studio config 'hosts.{host}.{series}' must be an object")
            version = entry.get("bundle_version")
            # null is "no bundle selected"; a missing key is still a mistake.
            hosts[host][series] = (
                None if "bundle_version" in entry and version is None
                else validate_id(version, f"bundle_version for {host} {series}")
            )
    return StudioConfig(hosts=hosts)


@dataclass(frozen=True)
class Manifest:
    package_id: str
    release_id: str
    artifact: str
    sha256: str
    python_root: str = "."

    def to_json(self) -> str:
        data = {
            "schema_version": SCHEMA_VERSION,
            "package_id": self.package_id,
            "release_id": self.release_id,
            "artifact": self.artifact,
            "sha256": self.sha256,
            "python_root": self.python_root,
        }
        return json.dumps(data, indent=2, sort_keys=True) + "\n"


def parse_manifest(text: str) -> Manifest:
    data = _load_object(text, "manifest")
    _check_schema(data, "manifest")
    artifact = data.get("artifact")
    if not isinstance(artifact, str) or artifact in ("", ".", "..") or re.search(r"[/\\:\x00]", artifact):
        raise ConfigError(f"manifest artifact must be a plain file name: {artifact!r}")
    sha256 = data.get("sha256")
    if not isinstance(sha256, str) or not _SHA256_RE.match(sha256.lower()):
        raise ConfigError("manifest sha256 must be 64 hex characters")
    return Manifest(
        package_id=validate_id(data.get("package_id"), "package_id"),
        release_id=validate_id(data.get("release_id"), "release_id"),
        artifact=artifact,
        sha256=sha256.lower(),
        python_root=validate_python_root(data.get("python_root", ".")),
    )


@dataclass(frozen=True)
class LocalConfig:
    """Machine configuration in the pipeline root's config.json: where bundles come from and go to."""

    remote_repository: Path | WebRepository  # a folder (a share) or an https address
    bundle_repository: Path
    hosts: dict = field(default_factory=dict)  # host -> series the user has enabled, for sync-all and the tray app
    check_interval_minutes: int = DEFAULT_CHECK_INTERVAL_MINUTES
    auto_sync: bool = True  # whether the tray app applies updates itself
    remote_locked: bool = False  # the repository comes from TLS_PIPELINE_REPOSITORY, so it can't be changed here
    python_homes: dict[str, Path] = field(default_factory=dict)  # optional external runtime folders, keyed by host


REPOSITORY_VARIABLE = "TLS_PIPELINE_REPOSITORY"  # an organisation's (or user's) repository; wins over config.json


def managed_repository(environ: Mapping[str, str] | None = None) -> str | None:
    """The repository supplied by the environment (user or system variable), or None if there isn't one."""
    environ = os.environ if environ is None else environ
    return environ.get(REPOSITORY_VARIABLE, "").strip() or None


def default_pipeline_root(environ: Mapping[str, str] | None = None, platform: str | None = None) -> Path | None:
    """Where a per-user installation puts the pipeline root when TLS_PIPELINE isn't set, or None if unknown."""
    environ = os.environ if environ is None else environ
    platform = sys.platform if platform is None else platform
    if platform.startswith("win"):
        base = environ.get("LOCALAPPDATA", "").strip()
        return Path(base) / "TheLine" / "pipeline" if base else None
    home = environ.get("HOME", "").strip()
    if platform == "darwin":
        return Path(home) / "Library" / "Application Support" / "TheLine" / "Pipeline" if home else None
    data = environ.get("XDG_DATA_HOME", "").strip() or (str(Path(home) / ".local" / "share") if home else "")
    return Path(data) / "theline" / "pipeline" if data else None


def _hosts(value) -> dict:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ConfigError("local config 'hosts' must be an object of host -> list of series")
    hosts = {}
    for host, series in value.items():
        validate_host(host)
        if not isinstance(series, list):
            raise ConfigError(f"local config 'hosts.{host}' must be a list of series")
        hosts[host] = tuple(dict.fromkeys(validate_series(item) for item in series))
    return hosts


def _interval(value) -> int:
    if value is None:
        return DEFAULT_CHECK_INTERVAL_MINUTES
    if type(value) is not int or not MIN_CHECK_INTERVAL_MINUTES <= value <= MAX_CHECK_INTERVAL_MINUTES:
        raise ConfigError(
            f"check_interval_minutes must be a whole number from {MIN_CHECK_INTERVAL_MINUTES} "
            f"to {MAX_CHECK_INTERVAL_MINUTES}: {value!r}"
        )
    return value


def _folder(value, base: Path, what: str) -> Path:
    """A folder path, relative to `base` (the config file's folder) unless absolute."""
    if not isinstance(value, str) or not value.strip():
        raise ConfigError(f"{what} must be a folder path")
    parts = urlsplit(value)
    if parts.scheme.lower() == "file":
        path = Path(url2pathname(parts.path))
    elif len(parts.scheme) > 1:  # a one-letter scheme is a drive letter, not a URL
        raise ConfigError(f"{what} {value!r} is not a folder path")
    else:
        path = Path(value)
    return Path(os.path.normpath(base / path))


def _remote(value, base: Path, what: str):
    """The remote repository: an https address, or a folder as for _folder."""
    if isinstance(value, str):
        scheme = urlsplit(value.strip()).scheme.lower()
        if scheme in ("http", "https"):
            return WebRepository(parse_web_url(value, what))
        if len(scheme) > 1 and scheme != "file":  # a one-letter scheme is a drive letter
            raise ConfigError(f"{what} {value!r} must be a folder path or an https address")
    return _folder(value, base, what)


def _python_homes(value, base: Path) -> dict[str, Path]:
    if not isinstance(value, dict):
        raise ConfigError("local config 'python_homes' must be an object of host -> Python installation folder")
    return {
        validate_host(host): _folder(home, base, f"python_homes.{host}")
        for host, home in value.items()
    }


def parse_local_config(text: str, base: Path, environ: Mapping[str, str] | None = None) -> LocalConfig:
    """Parse config.json text; relative paths resolve against `base`, the folder containing the file.

    TLS_PIPELINE_REPOSITORY in `environ` (the process environment by default) takes precedence over the file."""
    data = _load_object(text, "local config")
    _check_schema(data, "local config")
    auto_sync = data.get("auto_sync", True)
    if type(auto_sync) is not bool:
        raise ConfigError(f"auto_sync must be true or false: {auto_sync!r}")
    managed = managed_repository(environ)
    if managed:
        remote = _remote(managed, base, REPOSITORY_VARIABLE)
    else:
        remote = _remote(data.get("remote_repository"), base, "remote_repository")
    return LocalConfig(
        remote_repository=remote,
        bundle_repository=_folder(data.get("bundle_repository", "./bundles"), base, "bundle_repository"),
        hosts=_hosts(data.get("hosts")),
        check_interval_minutes=_interval(data.get("check_interval_minutes")),
        auto_sync=auto_sync,
        remote_locked=bool(managed),
        python_homes=_python_homes(data.get("python_homes", {}), base),
    )


def load_local_config(path: Path, environ: Mapping[str, str] | None = None) -> LocalConfig:
    path = Path(path).absolute()
    try:
        text = path.read_text(encoding="utf-8-sig")
    except OSError as exc:
        raise ConfigError(f"local config not readable ({exc}); installation or repair is required") from None
    return parse_local_config(text, path.parent, environ)
