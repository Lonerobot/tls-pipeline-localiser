import json
import os
import subprocess
import sys
import time
import unittest
import zipfile
from pathlib import Path
from unittest import mock

from localiser import (
    LocaliserError,
    Manifest,
    ReleaseUnavailableError,
    UnsafeArchiveError,
    VerificationError,
)
from localiser.fsutil import sha256_file
from localiser.install import ensure_release
from localiser.layout import COMPLETE_MARKER, DataLayout

from .helpers import WorkstationTestCase

WORKERS = str(Path(__file__).with_name("_workers.py"))


class InstallTests(WorkstationTestCase):
    def setUp(self):
        super().setUp()
        self.layout = DataLayout(self.data)

    def ensure(self, package="maya-tools", release="2.9.0"):
        return ensure_release(self.layout, self.repo, package, release, host="maya", lock_timeout=10)

    def share_dir(self, package="maya-tools", release="2.9.0"):
        return self.repo / "hosts" / package / release

    def assert_nothing_published(self, package="maya-tools", release="2.9.0"):
        self.assertFalse(self.layout.release_dir(package, release).exists())
        self.assertEqual(list(self.layout.staging.iterdir()), [])

    def test_installs_and_returns_python_root(self):
        self.publish("maya-tools", "2.9.0", {"core/tool.py": "X = 1\n"}, python_root="core")
        release = self.ensure()
        self.assertEqual(release.python_root, release.release_root / "core")
        self.assertEqual((release.python_root / "tool.py").read_text(), "X = 1\n")
        self.assertTrue((release.release_root / COMPLETE_MARKER).is_file())

    def test_manifest_copy_kept_outside_the_payload(self):
        manifest = self.publish("maya-tools", "2.9.0")
        self.ensure()
        cached = self.layout.manifest_cache("maya-tools", "2.9.0")
        self.assertEqual(json.loads(cached.read_text())["sha256"], manifest.sha256)
        self.assertFalse((self.layout.release_dir("maya-tools", "2.9.0") / "manifest.json").exists())

    def test_fast_path_needs_no_share_and_no_hashing(self):
        self.publish("maya-tools", "2.9.0")
        first = self.ensure()
        for path in sorted(self.repo.rglob("*"), reverse=True):
            path.unlink() if path.is_file() else path.rmdir()
        self.repo.rmdir()
        with mock.patch("localiser.install.sha256_file", side_effect=AssertionError("hashed")):
            second = self.ensure()
        self.assertEqual(first, second)

    def test_directory_deleted_triggers_reinstall(self):
        self.publish("maya-tools", "2.9.0")
        release = self.ensure()
        import shutil

        shutil.rmtree(release.release_root)
        self.assertEqual(self.ensure().release_root, release.release_root)
        self.assertTrue((release.release_root / COMPLETE_MARKER).is_file())

    def test_missing_marker_is_not_installed_and_is_replaced(self):
        self.publish("maya-tools", "2.9.0")
        release = self.ensure()
        (release.release_root / COMPLETE_MARKER).unlink()
        (release.release_root / "stale.txt").write_text("left over")
        again = self.ensure()
        self.assertTrue((again.release_root / COMPLETE_MARKER).is_file())
        self.assertFalse((again.release_root / "stale.txt").exists())

    def test_corrupt_or_foreign_marker_is_not_trusted(self):
        self.publish("maya-tools", "2.9.0")
        release = self.ensure()
        marker = release.release_root / COMPLETE_MARKER
        for content in ["{broken", json.dumps({"package_id": "other", "release_id": "2.9.0", "python_root": "."})]:
            with self.subTest(content=content):
                marker.write_text(content)
                self.ensure()
                self.assertEqual(json.loads(marker.read_text())["package_id"], "maya-tools")

    def test_checksum_mismatch_publishes_nothing(self):
        self.publish("maya-tools", "2.9.0")
        artifact = self.share_dir() / "pipeline.zip"
        artifact.write_bytes(artifact.read_bytes() + b"tampered")
        with self.assertRaises(VerificationError):
            self.ensure()
        self.assert_nothing_published()

    def test_manifest_identity_mismatch(self):
        manifest = self.publish("maya-tools", "2.9.0")
        wrong = Manifest("maya-tools", "9.9.9", manifest.artifact, manifest.sha256)
        (self.share_dir() / "manifest.json").write_text(wrong.to_json())
        with self.assertRaises(VerificationError):
            self.ensure()
        self.assert_nothing_published()

    def test_missing_python_root_in_archive(self):
        manifest = self.publish("maya-tools", "2.9.0")
        broken = Manifest("maya-tools", "2.9.0", manifest.artifact, manifest.sha256, "core")
        (self.share_dir() / "manifest.json").write_text(broken.to_json())
        with self.assertRaises(VerificationError):
            self.ensure()
        self.assert_nothing_published()

    def test_unsafe_archive_publishes_nothing(self):
        share = self.share_dir("maya-tools", "1.0")
        share.mkdir(parents=True)
        artifact = share / "pipeline.zip"
        with zipfile.ZipFile(artifact, "w") as zf:
            zf.writestr("ok.py", "x")
            zf.writestr("../evil.py", "x")
        (share / "manifest.json").write_text(
            Manifest("maya-tools", "1.0", "pipeline.zip", sha256_file(artifact)).to_json()
        )
        with self.assertRaises(UnsafeArchiveError):
            self.ensure(release="1.0")
        self.assert_nothing_published(release="1.0")
        self.assertFalse((self.layout.releases.parent / "evil.py").exists())

    def test_unavailable_release_names_host_and_id(self):
        with self.assertRaises(ReleaseUnavailableError) as raised:
            self.ensure(release="7.7.7")
        self.assertIn("host=maya", str(raised.exception))
        self.assertIn("release=7.7.7", str(raised.exception))
        self.assert_nothing_published(release="7.7.7")

    def test_interrupted_extraction_leaves_no_valid_release_and_retry_works(self):
        self.publish("maya-tools", "2.9.0")
        with mock.patch("localiser.install.safe_extract", side_effect=RuntimeError("killed")):
            with self.assertRaises(RuntimeError):
                self.ensure()
        self.assert_nothing_published()
        self.assertTrue((self.ensure().release_root / COMPLETE_MARKER).is_file())

    def test_concurrent_installers_install_once(self):
        self.publish("maya-tools", "2.9.0", {"big.py": "x = 1\n" * 200000})
        descriptor_path = self.tmp / "config.json"
        descriptor_path.write_text(
            json.dumps(
                {"schema_version": 1, "remote_repository": str(self.repo), "bundle_repository": str(self.data)}
            )
        )
        go = self.tmp / "go"
        workers = [
            subprocess.Popen(
                [sys.executable, WORKERS, "install", str(descriptor_path), "maya-tools", "2.9.0", str(go)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            for _ in range(4)
        ]
        time.sleep(1.0)
        go.write_text("go")
        results = [worker.communicate(timeout=60) + (worker.returncode,) for worker in workers]
        for out, err, code in results:
            self.assertEqual(code, 0, err)
            self.assertTrue(out.startswith("OK"), out)
        installed = sorted(int(out.split("installed=")[1].split()[0]) for out, _, _ in results)
        self.assertEqual(installed, [0, 0, 0, 1])
        release_dir = self.layout.release_dir("maya-tools", "2.9.0")
        self.assertTrue((release_dir / COMPLETE_MARKER).is_file())
        self.assertEqual(list(self.layout.staging.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
