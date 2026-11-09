import os
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

from localiser import PublishError, publish_release
from localiser.archive import safe_extract


class PublisherTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)
        self.repo = self.tmp / "share"
        self.src = self.tmp / "src"
        (self.src / "pkg" / "__pycache__").mkdir(parents=True)
        (self.src / "pkg" / "mod.py").write_text("X = 1\n")
        (self.src / "pkg" / "__pycache__" / "mod.cpython-311.pyc").write_bytes(b"\0")
        (self.src / "stray.pyc").write_bytes(b"\0")
        (self.src / "Thumbs.db").write_bytes(b"\0")
        (self.src / ".DS_Store").write_bytes(b"\0")
        (self.src / "pkg" / "scene.nk~").write_bytes(b"\0")
        (self.src / "__MACOSX").mkdir()
        (self.src / "__MACOSX" / "._init.py").write_bytes(b"\0")
        (self.src / "core").mkdir()
        (self.src / "core" / "init.py").write_text("pass\n")

    def test_publishes_zip_and_manifest_without_junk(self):
        manifest = publish_release(self.src, self.repo, "maya-tools", "2.9.0")
        release = self.repo / "hosts" / "maya-tools" / "2.9.0"
        self.assertTrue((release / "manifest.json").is_file())
        with zipfile.ZipFile(release / manifest.artifact) as zf:
            self.assertEqual(sorted(zf.namelist()), ["core/init.py", "pkg/mod.py"])
        self.assertEqual([p.name for p in release.parent.iterdir()], ["2.9.0"])

    def test_transient_access_denied_on_the_final_rename_is_retried(self):
        real_rename = os.rename
        calls = []

        def flaky(source, destination):
            calls.append(source)
            if len(calls) < 3:
                raise PermissionError(13, "Access is denied")
            return real_rename(source, destination)

        with mock.patch("localiser.fsutil.os.rename", side_effect=flaky), mock.patch("localiser.fsutil.time.sleep"):
            publish_release(self.src, self.repo, "p", "1")
        self.assertEqual(len(calls), 3)
        self.assertTrue((self.repo / "hosts" / "p" / "1" / "manifest.json").is_file())

    def test_refuses_to_overwrite_existing_release(self):
        publish_release(self.src, self.repo, "maya-tools", "2.9.0")
        with self.assertRaises(PublishError):
            publish_release(self.src, self.repo, "maya-tools", "2.9.0")

    def test_deterministic_for_identical_content(self):
        first = publish_release(self.src, self.repo, "p", "1")
        second = publish_release(self.src, self.repo, "p", "2")
        self.assertEqual(first.sha256, second.sha256)

    def test_content_change_changes_checksum(self):
        first = publish_release(self.src, self.repo, "p", "1")
        (self.src / "pkg" / "mod.py").write_text("X = 2\n")
        second = publish_release(self.src, self.repo, "p", "2")
        self.assertNotEqual(first.sha256, second.sha256)

    def test_python_root_must_exist(self):
        with self.assertRaises(PublishError):
            publish_release(self.src, self.repo, "p", "1", python_root="missing")
        manifest = publish_release(self.src, self.repo, "p", "2", python_root="core")
        self.assertEqual(manifest.python_root, "core")

    def test_rejects_unsafe_ids_and_missing_source(self):
        from localiser import ConfigError

        with self.assertRaises(ConfigError):
            publish_release(self.src, self.repo, "p", "../x")
        with self.assertRaises(PublishError):
            publish_release(self.tmp / "nope", self.repo, "p", "1")

    def test_rejects_symlinks(self):
        link = self.src / "link.py"
        try:
            os.symlink(str(self.src / "pkg" / "mod.py"), str(link))
        except (OSError, NotImplementedError):
            self.skipTest("symlinks not available")
        with self.assertRaises(PublishError):
            publish_release(self.src, self.repo, "p", "1")

    def test_published_zip_extracts_safely(self):
        manifest = publish_release(self.src, self.repo, "p", "1")
        artifact = self.repo / "hosts" / "p" / "1" / manifest.artifact
        safe_extract(artifact, self.tmp / "out")
        self.assertTrue((self.tmp / "out" / "pkg" / "mod.py").is_file())


if __name__ == "__main__":
    unittest.main()
