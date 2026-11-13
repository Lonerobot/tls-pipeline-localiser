"""Installing the stubs, pipeline entry and core into the root: only what differs, and nothing else in the root."""
import contextlib
import io
import os
import sys
from pathlib import Path
from unittest.mock import patch

from localiser import install_pipeline_code
from localiser.__main__ import main
from localiser.errors import LocaliserError
from localiser.install_code import pipeline_source
from localiser.provision import CREATED, REMOVED, UPDATED

from .helpers import WorkstationTestCase


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


class InstallPipelineCodeTests(WorkstationTestCase):
    def setUp(self):
        super().setUp()
        self.source = self.tmp / "pipeline_source"
        self.core = self.tmp / "core"
        self.root = self.tmp / "Pipeline Root"  # a space on purpose
        write(self.source / "__init__.py", "ENTRY = 1\n")
        write(self.source / "about.py", "ABOUT = 1\n")
        write(self.source / "bootstrap" / "maya" / "userSetup.py", "MAYA = 1\n")
        write(self.source / "bootstrap" / "blender" / "startup" / "stub.py", "BLENDER = 1\n")
        write(self.core / "__init__.py", "CORE = 1\n")
        write(self.core / "api.py", "API = 1\n")
        write(self.core / "__pycache__" / "api.pyc", "ignored")

    def install(self):
        return install_pipeline_code(self.root, self.source, self.core)

    def test_a_new_root_gets_the_entry_the_stubs_and_the_core(self):
        actions = self.install()
        self.assertEqual({action.change for action in actions}, {CREATED})
        for relative in ("__init__.py", "about.py", "bootstrap/maya/userSetup.py", "bootstrap/blender/startup/stub.py",
                         "localiser/__init__.py", "localiser/api.py"):
            self.assertTrue((self.root / relative).is_file(), relative)
        self.assertFalse((self.root / "localiser" / "__pycache__").exists())

    def test_an_up_to_date_root_is_left_alone(self):
        self.install()
        stamp = (self.root / "about.py").stat().st_mtime_ns
        self.assertEqual(self.install(), [])
        self.assertEqual((self.root / "about.py").stat().st_mtime_ns, stamp)

    def test_only_changed_files_are_replaced_and_dropped_ones_removed(self):
        self.install()
        write(self.core / "__init__.py", "CORE = 2\n")
        (self.core / "api.py").unlink()
        write(self.source / "bootstrap" / "nuke" / "init.py", "NUKE = 1\n")
        changes = {action.path.name: action.change for action in self.install()}
        self.assertEqual(changes, {"__init__.py": UPDATED, "api.py": REMOVED, "init.py": CREATED})
        self.assertEqual((self.root / "localiser" / "__init__.py").read_text(encoding="utf-8"), "CORE = 2\n")
        self.assertFalse((self.root / "localiser" / "api.py").exists())

    def test_config_bundles_and_state_in_the_root_are_never_touched(self):
        write(self.root / "config.json", "{}")
        write(self.root / "hosts" / "maya" / "1.0" / "x.py", "keep")
        write(self.root / "state" / "status.json", "keep")
        write(self.root / "bootstrap" / "mine" / "own.py", "not in the source, so it goes")
        self.install()
        self.assertEqual((self.root / "config.json").read_text(encoding="utf-8"), "{}")
        self.assertTrue((self.root / "hosts" / "maya" / "1.0" / "x.py").is_file())
        self.assertTrue((self.root / "state" / "status.json").is_file())
        self.assertFalse((self.root / "bootstrap" / "mine" / "own.py").exists())  # managed folders mirror the source

    def test_a_root_that_is_the_source_is_not_copied_onto_itself(self):
        self.assertEqual(install_pipeline_code(self.source, self.source, self.core), [])
        self.assertEqual((self.source / "about.py").read_text(encoding="utf-8"), "ABOUT = 1\n")

    def test_a_missing_source_is_reported(self):
        with self.assertRaisesRegex(LocaliserError, "not found"):
            install_pipeline_code(self.root, self.tmp / "nowhere", self.core)

    def test_missing_core_sources_are_reported_before_changing_the_root(self):
        self.install()
        before = {path.relative_to(self.root): path.read_bytes() for path in self.root.rglob("*") if path.is_file()}
        (self.core / "__init__.py").unlink()
        write(self.source / "about.py", "ABOUT = 2\n")
        with self.assertRaisesRegex(LocaliserError, "core Python source"):
            self.install()
        after = {path.relative_to(self.root): path.read_bytes() for path in self.root.rglob("*") if path.is_file()}
        self.assertEqual(before, after)

    def test_this_checkout_installs_a_root_that_can_start_a_host(self):
        actions = install_pipeline_code(self.root)
        self.assertTrue(actions)
        for relative in ("__init__.py", "about.py", "bootstrap/maya/userSetup.py", "bootstrap/nuke/init.py",
                         "bootstrap/blender/startup/tls_pipeline_startup.py", "localiser/api.py", "localiser/launch.py"):
            self.assertTrue((self.root / relative).is_file(), relative)
        self.assertEqual(install_pipeline_code(self.root), [])

    def test_packaged_pipeline_payload_is_used_when_frozen(self):
        packaged = self.tmp / "pipeline"
        write(packaged / "__init__.py", "ENTRY = 1\n")
        write(packaged / "bootstrap" / "maya" / "userSetup.py", "MAYA = 1\n")
        with patch.object(sys, "_MEIPASS", str(self.tmp), create=True):
            self.assertEqual(pipeline_source(), packaged)

    def test_install_command_uses_the_pipeline_root(self):
        out = io.StringIO()
        with patch.dict(os.environ, {"TLS_PIPELINE": str(self.root)}, clear=True), contextlib.redirect_stdout(out):
            self.assertEqual(main(["install"]), 0)
            first = out.getvalue()
            out.truncate(0)
            out.seek(0)
            self.assertEqual(main(["install"]), 0)
        self.assertIn("files changed", first)
        self.assertIn("up to date", out.getvalue())
        self.assertTrue((self.root / "bootstrap" / "maya" / "userSetup.py").is_file())
