"""Nuke exposes self-contained plugins without changing existing toolchains."""
import io
import os
import runpy
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, call, patch

from tests.test_stub_root import STUBS


class NukePluginTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.paths = [str(self.root / "user-plugins")]
        self.nuke = SimpleNamespace(
            NUKE_VERSION_MAJOR=17,
            NUKE_VERSION_MINOR=0,
            pluginPath=Mock(side_effect=lambda: list(self.paths)),
            pluginAddPath=Mock(side_effect=self.add_path),
        )
        self.start = Mock(return_value=SimpleNamespace(release_root=self.root))

    def add_path(self, folder):
        self.paths.insert(0, folder)

    def folder(self, name):
        path = self.root / "plugins" / name
        path.mkdir(parents=True)
        return str(path)

    def load(self):
        with patch.dict(sys.modules, {
            "nuke": self.nuke,
            "tls_pipeline": SimpleNamespace(start=self.start),
        }):
            return runpy.run_path(str(STUBS["nuke"]))

    def test_startup_adds_only_immediate_plugin_directories_without_importing_files(self):
        zulu = self.folder("Zulu")
        alpha = self.folder("Alpha")
        self.folder(".hidden")
        self.folder("__pycache__")
        self.folder("__internal")
        self.folder(os.path.join("Alpha", "nested"))
        (self.root / "plugins" / "loose.py").write_text("raise RuntimeError('not a plugin')", encoding="utf-8")
        (Path(alpha) / "module.py").write_text("raise RuntimeError('do not auto-import')", encoding="utf-8")
        (self.root / "toolchains" / "disabled").mkdir(parents=True)

        self.load()

        self.start.assert_called_once_with("nuke", "17.0")
        self.assertEqual(self.nuke.pluginAddPath.call_args_list, [call(alpha), call(zulu)])
        self.assertTrue(all(os.path.isabs(path) for path in self.paths))
        self.assertIn(str(self.root / "user-plugins"), self.paths)

    def test_existing_paths_are_preserved_and_normalized_and_repeated_exposure_is_a_no_op(self):
        alpha = self.folder("Alpha")
        zulu = self.folder("Zulu")
        existing = os.path.join(alpha, ".") + os.sep
        if sys.platform.startswith("win"):
            existing = existing.upper()
        self.paths.append(existing)

        stub = self.load()
        stub["_expose_plugins"](self.root)

        self.nuke.pluginAddPath.assert_called_once_with(zulu)
        self.assertIn(existing, self.paths)
        self.assertIn(str(self.root / "user-plugins"), self.paths)

    def test_an_optional_plugins_directory_is_not_required(self):
        self.load()
        self.nuke.pluginAddPath.assert_not_called()

    def test_no_selected_release_does_not_expose_plugins(self):
        self.folder("Alpha")
        self.start.return_value = None

        self.load()

        self.nuke.pluginPath.assert_not_called()
        self.nuke.pluginAddPath.assert_not_called()

    def test_a_failed_bundle_entry_does_not_expose_plugins_and_is_reported(self):
        self.folder("Alpha")
        self.start.side_effect = RuntimeError("bundle entry failed")
        with patch("sys.stderr", new_callable=io.StringIO) as errors, \
                patch("sys.stdout", new_callable=io.StringIO) as output:
            self.load()

        self.assertIn("bundle entry failed", errors.getvalue())
        self.assertIn("TLS pipeline: failed", output.getvalue())
        self.nuke.pluginAddPath.assert_not_called()

    def test_discovery_and_registration_failures_are_reported_without_stopping_nuke(self):
        self.folder("Alpha")
        for operation, error in (
            ("scan", PermissionError("plugin directory denied")),
            ("register", RuntimeError("plugin registration failed")),
        ):
            with self.subTest(operation=operation):
                if operation == "scan":
                    failure = patch("os.scandir", side_effect=error)
                else:
                    failure = patch.object(self.nuke, "pluginAddPath", side_effect=error)
                with failure, patch("sys.stderr", new_callable=io.StringIO) as errors, \
                        patch("sys.stdout", new_callable=io.StringIO) as output:
                    self.load()
                self.assertIn(str(error), errors.getvalue())
                self.assertIn("TLS pipeline: failed", output.getvalue())


if __name__ == "__main__":
    unittest.main()
