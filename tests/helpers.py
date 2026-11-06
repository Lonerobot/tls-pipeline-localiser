"""Shared fixtures: a fake remote repository, a local bundle store and published synthetic releases."""
import json
import tempfile
import unittest
from pathlib import Path

from localiser import LocalConfig, parse_local_config, publish_release

SERIES = "2026"  # the DCC series used by tests that don't care about it


class WorkstationTestCase(unittest.TestCase):
    """Provides self.repo (the remote), self.data (local bundle store) and self.config in a temp dir."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)
        self.repo = self.tmp / "share"
        self.data = self.tmp / "local"
        self.repo.mkdir()
        self.config = self.make_config()

    def make_config(self) -> LocalConfig:
        text = json.dumps(
            {"schema_version": 1, "remote_repository": str(self.repo), "bundle_repository": str(self.data)}
        )
        return parse_local_config(text, self.tmp)

    def publish(self, package_id, release_id, files=None, python_root="."):
        source = self.tmp / "src_{}_{}".format(package_id, release_id)
        files = files if files is not None else {"tool.py": "VALUE = {!r}\n".format(release_id)}
        for relative, content in files.items():
            path = source / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
        source.mkdir(exist_ok=True)
        return publish_release(source, self.repo, package_id, release_id, python_root=python_root)

    def write_studio_config(self, versions):
        """Write the remote config. Values are a version (used for SERIES) or a {series: version} dict."""
        hosts = {}
        for host, value in versions.items():
            by_series = value if isinstance(value, dict) else {SERIES: value}
            hosts[host] = {series: {"bundle_version": version} for series, version in by_series.items()}
        path = self.repo / "config.json"
        path.write_text(json.dumps({"schema_version": 1, "hosts": hosts}), encoding="utf-8")
        return path
