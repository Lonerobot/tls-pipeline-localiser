"""Where releases and the studio config come from: a folder (a share) or an https address.

Both give the same two operations, so the rest of the core doesn't care which it has:

    read_text("config.json")                         a small text file (config, manifest)
    fetch("hosts/maya/1.0.0/pipeline.zip", target)   a larger file, copied to a local path

Every failure is an OSError, so callers treat an unreachable share and an unreachable web address alike.
"""
import shutil
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from .errors import ConfigError

MAX_TEXT_BYTES = 1024 * 1024  # config and manifest files are a few hundred bytes; anything bigger is wrong
TIMEOUT_SECONDS = 15
LOOPBACK_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})  # plain http is only accepted here, for testing
USER_AGENT = "localiser"


def parse_web_url(value: str, what: str) -> str:
    """Return a normalised https base URL, or raise ConfigError. Plain http is accepted for loopback only."""
    parts = urllib.parse.urlsplit(value.strip())
    scheme = parts.scheme.lower()
    secure = scheme == "https" or (scheme == "http" and parts.hostname in LOOPBACK_HOSTS)
    if not secure:
        raise ConfigError(f"{what} {value!r} must be an https address")
    if not parts.hostname or parts.username or parts.password or parts.query or parts.fragment:
        raise ConfigError(f"{what} {value!r} must be a plain address: no credentials, query or fragment")
    return urllib.parse.urlunsplit((scheme, parts.netloc, parts.path.rstrip("/"), "", ""))


class _SecureRedirects(urllib.request.HTTPRedirectHandler):
    """Follow redirects, but never to an address that parse_web_url wouldn't accept."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        try:
            parse_web_url(urllib.parse.urljoin(req.full_url, newurl), "redirect")
        except ConfigError:
            raise urllib.error.URLError(f"refusing to follow a redirect to {newurl}") from None
        return super().redirect_request(req, fp, code, msg, headers, newurl)


@dataclass(frozen=True)
class FolderRepository:
    root: Path

    @property
    def location(self) -> str:
        return str(self.root)

    def read_text(self, relative: str) -> str:
        return (self.root / relative).read_text(encoding="utf-8-sig")

    def fetch(self, relative: str, destination: Path) -> None:
        shutil.copyfile(self.root / relative, destination)

    def list_folders(self, relative: str) -> list[str]:
        """Names of the folders under `relative`; empty if there are none or it can't be read."""
        try:
            return sorted(p.name for p in (self.root / relative).iterdir() if p.is_dir() and not p.name.startswith("."))
        except OSError:
            return []

@dataclass(frozen=True)
class WebRepository:
    base_url: str

    @property
    def location(self) -> str:
        return self.base_url

    def url(self, relative: str) -> str:
        parts = relative.split("/")
        if not relative or ".." in parts or "" in parts or "\\" in relative:
            raise OSError(f"invalid repository path: {relative!r}")
        return f"{self.base_url}/" + "/".join(urllib.parse.quote(part) for part in parts)

    def _open(self, relative: str):
        request = urllib.request.Request(self.url(relative), headers={"User-Agent": USER_AGENT})
        return urllib.request.build_opener(_SecureRedirects()).open(request, timeout=TIMEOUT_SECONDS)

    def read_text(self, relative: str) -> str:
        with self._open(relative) as response:
            data = response.read(MAX_TEXT_BYTES + 1)
        if len(data) > MAX_TEXT_BYTES:
            raise OSError(f"{relative} is larger than {MAX_TEXT_BYTES} bytes")
        return data.decode("utf-8-sig")

    def fetch(self, relative: str, destination: Path) -> None:
        with self._open(relative) as response, open(destination, "wb") as sink:
            shutil.copyfileobj(response, sink, 1024 * 1024)

    def list_folders(self, relative: str) -> list[str]:
        return []  # static web hosting has no directory listing; the studio config names the releases in use

Repository = FolderRepository | WebRepository


def as_repository(value) -> Repository:
    """Accept a folder path or an already opened repository."""
    if isinstance(value, (FolderRepository, WebRepository)):
        return value
    return FolderRepository(Path(value))
