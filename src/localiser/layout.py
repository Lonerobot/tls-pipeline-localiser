"""Paths inside the local data root."""
from pathlib import Path

from .config import validate_host, validate_id, validate_series

COMPLETE_MARKER = ".complete"
HOSTS_DIR = "hosts"  # bundles live at <root>/hosts/<host>/<bundle_version>, on the remote and locally


class DataLayout:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.releases = self.root / HOSTS_DIR
        self.state = self.root / "state"
        self.staging = self.root / "staging"
        self.locks = self.root / "locks"
        self.logs = self.root / "logs"
        self.dev = self.root / "dev"  # throwaway copies of unpublished bundle sources, see sync.dev_release
        self.last_known_config = self.state / "studio-config.json"

    def release_dir(self, package_id: str, release_id: str) -> Path:
        return self.releases / validate_id(package_id, "package_id") / validate_id(release_id, "release_id")

    def release_lock(self, package_id: str, release_id: str) -> Path:
        package_id = validate_id(package_id, "package_id")
        release_id = validate_id(release_id, "release_id")
        return self.locks / f"{package_id}__{release_id}.lock"

    def host_state_file(self, host: str) -> Path:
        return self.state / f"{validate_host(host)}.json"

    def prepared_file(self, host: str, series: str) -> Path:
        return self.state / "prepared" / validate_host(host) / f"{validate_series(series)}.json"

    def manifest_cache(self, package_id: str, release_id: str) -> Path:
        package_id = validate_id(package_id, "package_id")
        release_id = validate_id(release_id, "release_id")
        return self.state / "manifests" / package_id / f"{release_id}.json"

    @property
    def status_file(self) -> Path:
        """The last check or sync result per enabled host and series, for the tray app and the hosts."""
        return self.state / "status.json"

    def ensure(self) -> None:
        for directory in (self.releases, self.state, self.staging, self.locks, self.logs):
            directory.mkdir(parents=True, exist_ok=True)
