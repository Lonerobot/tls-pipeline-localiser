"""Publishing a bundle source: descriptor, host defaults, shared packages and the publish command."""
import contextlib
import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from localiser import PublishError, plan_bundle, publish_bundle
from localiser.__main__ import main
from localiser.config import parse_manifest


class BundlePublishTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)
        self.repo = self.tmp / "share"
        self.src = self.tmp / "src"
        self.shared = self.tmp / "shared"

    def write(self, root, relative, text="x = 1\n"):
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def names(self, manifest):
        with zipfile.ZipFile(self.repo / "hosts" / manifest.package_id / manifest.release_id / manifest.artifact) as zf:
            return sorted(zf.namelist())

    def test_shared_packages_go_to_the_bundle_root_by_default(self):
        self.write(self.src, "__init__.py")
        self.write(self.src, "tool/a.py")
        self.write(self.shared, "tls_common/__init__.py")
        self.write(self.shared, "tls_common/log.py")
        manifest = publish_bundle(self.src, self.repo, "maya", "1.0.0", shared=[self.shared])
        self.assertEqual(manifest.python_root, ".")
        self.assertEqual(
            self.names(manifest), ["__init__.py", "tls_common/__init__.py", "tls_common/log.py", "tool/a.py"]
        )

    def test_blender_defaults_put_the_entry_in_startup_and_shared_code_in_modules(self):
        self.write(self.src, "startup/__init__.py")
        self.write(self.shared, "tls_common/__init__.py")
        manifest = publish_bundle(self.src, self.repo, "blender", "1.0.0", shared=[self.shared])
        self.assertEqual(manifest.python_root, "startup")
        self.assertEqual(self.names(manifest), ["modules/tls_common/__init__.py", "startup/__init__.py"])

    def test_bundle_json_overrides_the_defaults_and_is_not_shipped(self):
        self.write(self.src, "entry/__init__.py")
        self.write(self.src, "bundle.json", json.dumps(
            {"schema_version": 1, "python_root": "entry", "shared_destination": "lib"}
        ))
        self.write(self.shared, "common/__init__.py")
        manifest = publish_bundle(self.src, self.repo, "maya", "1.0.0", shared=[self.shared])
        self.assertEqual(manifest.python_root, "entry")
        self.assertEqual(self.names(manifest), ["entry/__init__.py", "lib/common/__init__.py"])

    def test_a_bundle_cannot_override_a_shared_package(self):
        self.write(self.src, "tls_common/own.py")
        self.write(self.shared, "tls_common/__init__.py")
        with self.assertRaises(PublishError):
            plan_bundle(self.src, "maya", [self.shared])

    def test_the_same_package_in_two_shared_folders_is_refused(self):
        self.write(self.src, "a.py")
        other = self.tmp / "other"
        self.write(self.shared, "pkg/__init__.py")
        self.write(other, "pkg/__init__.py")
        with self.assertRaises(PublishError):
            plan_bundle(self.src, "maya", [self.shared, other])

    def test_shared_junk_and_private_folders_are_skipped(self):
        self.write(self.src, "a.py")
        self.write(self.shared, "pkg/mod.py")
        self.write(self.shared, "pkg/__pycache__/mod.cpython-311.pyc")
        self.write(self.shared, "_notes/readme.txt")
        self.write(self.shared, ".git/config")
        plan = plan_bundle(self.src, "maya", [self.shared])
        self.assertEqual([name for name, _ in plan.entries], ["a.py", "pkg/mod.py"])
        self.assertEqual(plan.shared, ("pkg",))

    def test_missing_entry_point_folder_is_refused(self):
        self.write(self.src, "other/a.py")
        with self.assertRaises(PublishError):
            plan_bundle(self.src, "blender", [])

    def test_bad_descriptors_are_refused(self):
        self.write(self.src, "a.py")
        for text in (
            "not json",
            json.dumps({"python_root": "."}),
            json.dumps({"schema_version": 1, "surprise": 1}),
            json.dumps({"schema_version": 1, "python_root": "../outside"}),
        ):
            with self.subTest(text=text):
                self.write(self.src, "bundle.json", text)
                with self.assertRaises(PublishError):
                    plan_bundle(self.src, "maya", [])

    def test_missing_shared_folder_is_refused(self):
        self.write(self.src, "a.py")
        with self.assertRaises(PublishError):
            plan_bundle(self.src, "maya", [self.tmp / "nope"])

    def test_identical_plans_publish_identical_zips(self):
        self.write(self.src, "a.py")
        self.write(self.shared, "pkg/__init__.py")
        first = publish_bundle(self.src, self.repo, "maya", "1", shared=[self.shared])
        second = publish_bundle(self.src, self.repo, "maya", "2", shared=[self.shared])
        self.assertEqual(first.sha256, second.sha256)

    def test_publish_command_writes_a_release_and_refuses_to_overwrite(self):
        self.write(self.src, "a.py")
        self.write(self.shared, "pkg/__init__.py")
        argv = ["publish", str(self.src), "maya", "1.0.0", "--shared", str(self.shared), "--remote", str(self.repo)]
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(main(argv), 0)
        manifest = parse_manifest((self.repo / "hosts" / "maya" / "1.0.0" / "manifest.json").read_text())
        self.assertIn(manifest.sha256, out.getvalue())
        self.assertIn("shared=pkg", out.getvalue())
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            self.assertEqual(main(argv), 2)
        self.assertIn("already exists", err.getvalue())


if __name__ == "__main__":
    unittest.main()
