"""Pulling, pinning and dev mode: running something other than the selected release, without changing it."""
import contextlib
import importlib.util
import io
import json
import os
import sys
import time
from pathlib import Path
from unittest.mock import patch

from localiser import (
    ConfigError,
    LocaliserError,
    PublishError,
    ReleaseUnavailableError,
    prepared_release,
    pull_release,
    startup_release,
    sync_release,
)
from localiser.__main__ import main
from localiser.layout import DataLayout
from localiser.resolve import override_variable
from localiser.sync import SHARED_VARIABLE, source_variable

from .helpers import SERIES, WorkstationTestCase

STRUCTURE = Path(__file__).resolve().parents[1] / "structure"


class StartupModeTests(WorkstationTestCase):
    def setUp(self):
        super().setUp()
        self.pipeline = self.tmp / "pipeline"
        self.pipeline.mkdir()
        (self.pipeline / "config.json").write_text(json.dumps({
            "schema_version": 1,
            "remote_repository": str(self.repo),
            "bundle_repository": str(self.data),
        }), encoding="utf-8")
        self.write_studio_config({"maya": "1.0"})
        self.publish("maya", "1.0", {"__init__.py": "VALUE = 'default'\n"})
        self.publish("maya", "1.1", {"__init__.py": "VALUE = 'pinned'\n"})
        self.selected = sync_release("maya", SERIES, self.config, {})

    def startup(self, env=None):
        return startup_release("maya", SERIES, self.config, env or {})

    def source_folder(self, files=None, name="2.0"):
        folder = self.tmp / "work" / name
        for relative, text in (files or {"__init__.py": "VALUE = 'dev'\n"}).items():
            path = folder / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        return folder

    def cli(self, *args):
        with patch.dict(os.environ, {}, clear=True), contextlib.redirect_stdout(io.StringIO()) as output:
            with contextlib.redirect_stderr(io.StringIO()) as errors:
                status = main(["--pipeline", str(self.pipeline), *args])
        return status, output.getvalue(), errors.getvalue()

    # pull

    def test_pull_installs_without_selecting(self):
        release = pull_release("maya", "1.1", self.config)
        self.assertTrue(release.python_root.is_dir())
        self.assertEqual(prepared_release("maya", SERIES, self.config).release_id, "1.0")

    def test_pull_of_an_unpublished_release_fails_clearly(self):
        with self.assertRaises(ReleaseUnavailableError):
            pull_release("maya", "9.9", self.config)

    def test_pull_command(self):
        status, output, _ = self.cli("pull", "maya", "1.1")
        self.assertEqual(status, 0)
        self.assertIn("Not selected", output)
        self.assertIn(override_variable("maya") + "=1.1", output)
        self.assertEqual(prepared_release("maya", SERIES, self.config).release_id, "1.0")

    # pin

    def test_no_pin_starts_with_the_selected_release(self):
        self.assertEqual(self.startup().release_id, "1.0")
        self.assertEqual(self.startup().source, "prepared")

    def test_pin_uses_the_installed_release_for_this_session_only(self):
        pull_release("maya", "1.1", self.config)
        pinned = self.startup({override_variable("maya"): "1.1"})
        self.assertEqual((pinned.release_id, pinned.source), ("1.1", "pinned"))
        self.assertEqual(prepared_release("maya", SERIES, self.config).release_id, "1.0")

    def test_pin_never_downloads(self):
        with self.assertRaisesRegex(ReleaseUnavailableError, "localiser pull maya 1.1"):
            self.startup({override_variable("maya"): "1.1"})
        self.assertFalse(DataLayout(self.data).release_dir("maya", "1.1").exists())

    def test_invalid_pin_is_an_error_and_blank_is_ignored(self):
        with self.assertRaises(ConfigError):
            self.startup({override_variable("maya"): "../escape"})
        self.assertEqual(self.startup({override_variable("maya"): "  "}).release_id, "1.0")

    def test_pin_applies_to_its_host_only(self):
        pull_release("maya", "1.1", self.config)
        self.assertEqual(self.startup({override_variable("nuke"): "1.1"}).release_id, "1.0")

    # dev

    def test_dev_lays_the_source_out_like_a_release_with_shared_packages(self):
        source = self.source_folder({"__init__.py": "VALUE = 'dev'\n", "tool/a.py": "X = 1\n"})
        shared = self.tmp / "shared"
        (shared / "tls_common").mkdir(parents=True)
        (shared / "tls_common" / "__init__.py").write_text("", encoding="utf-8")
        release = self.startup({source_variable("maya"): str(source), SHARED_VARIABLE: str(shared)})
        self.assertEqual((release.source, release.release_id), ("dev", "dev-2.0"))
        self.assertEqual(release.release_root.name, "2.0")  # whatever shows the folder name shows the version
        self.assertEqual((release.python_root / "__init__.py").read_text(), "VALUE = 'dev'\n")
        self.assertTrue((release.release_root / "tool" / "a.py").is_file())
        self.assertTrue((release.release_root / "tls_common" / "__init__.py").is_file())
        self.assertIn(str(DataLayout(self.data).dev), str(release.release_root))

    def test_dev_changes_no_selection_and_needs_no_remote(self):
        self.repo.rename(self.tmp / "offline")
        before = {p: p.read_bytes() for p in (self.data / "state").rglob("*") if p.is_file()}
        release = self.startup({source_variable("maya"): str(self.source_folder())})
        self.assertEqual(release.source, "dev")
        self.assertEqual(before, {p: p.read_bytes() for p in (self.data / "state").rglob("*") if p.is_file()})
        self.assertEqual(prepared_release("maya", SERIES, self.config).release_id, "1.0")

    def test_dev_takes_precedence_over_a_pin(self):
        pull_release("maya", "1.1", self.config)
        env = {override_variable("maya"): "1.1", source_variable("maya"): str(self.source_folder())}
        self.assertEqual(self.startup(env).source, "dev")

    def test_dev_source_that_cannot_be_used_is_an_error_not_a_fallback(self):
        with self.assertRaises(PublishError):
            self.startup({source_variable("maya"): str(self.tmp / "nowhere")})

    def test_blender_dev_uses_the_host_layout(self):
        source = self.source_folder({"startup/__init__.py": "", "addons/a/__init__.py": ""}, name="1.5")
        shared = self.tmp / "shared"
        (shared / "tls_common").mkdir(parents=True)
        (shared / "tls_common" / "__init__.py").write_text("", encoding="utf-8")
        env = {source_variable("blender"): str(source), SHARED_VARIABLE: str(shared)}
        release = startup_release("blender", "5.2", self.config, env)
        self.assertEqual(release.python_root, release.release_root / "startup")
        self.assertTrue((release.release_root / "modules" / "tls_common" / "__init__.py").is_file())

    def test_old_unused_dev_copies_are_removed_and_recent_ones_kept(self):
        host_dir = DataLayout(self.data).dev / "maya"
        old, recent = host_dir / "old00000", host_dir / "recent00"
        for folder in (old, recent):
            (folder / "x").mkdir(parents=True)
        long_ago = time.time() - 10 * 24 * 3600
        os.utime(old, (long_ago, long_ago))
        self.startup({source_variable("maya"): str(self.source_folder())})
        self.assertFalse(old.exists())
        self.assertTrue(recent.exists())

    # launch

    def launch_check(self, *options, code):
        # Options go before the host: everything after the series belongs to the DCC command.
        return self.cli("launch", *options, "maya", SERIES, sys.executable, "-c", code)

    def test_launch_bundle_pins_the_child_and_leaves_the_selection(self):
        pull_release("maya", "1.1", self.config)
        code = (
            "import os, sys; "
            "sys.exit(0 if os.environ['TLS_PIPELINE_MAYA'].endswith('1.1') "
            "and os.environ['TLS_PIPELINE_MAYA_BUNDLE'] == '1.1' else 3)"
        )
        status, _, error = self.launch_check("--bundle", "1.1", code=code)
        self.assertEqual((status, error), (0, ""))
        self.assertEqual(prepared_release("maya", SERIES, self.config).release_id, "1.0")

    def test_launch_bundle_that_is_not_installed_fails_before_starting(self):
        status, _, error = self.launch_check("--bundle", "1.1", code="raise SystemExit(0)")
        self.assertEqual(status, 2)
        self.assertIn("localiser pull maya 1.1", error)

    def test_launch_source_hands_the_child_the_source_and_shared_folders(self):
        source = self.source_folder()
        shared = self.tmp / "shared"
        shared.mkdir()
        code = (
            "import os, sys; "
            f"sys.exit(0 if os.environ['TLS_PIPELINE_MAYA_SOURCE'] == {str(source)!r} "
            f"and os.environ['TLS_PIPELINE_SHARED_SOURCES'] == {str(shared)!r} "
            "and 'TLS_PIPELINE_MAYA' not in os.environ else 3)"
        )
        status, _, error = self.launch_check("--source", str(source), "--shared", str(shared), code=code)
        self.assertEqual((status, error), (0, ""))

    def test_launch_source_that_cannot_be_used_fails_before_starting(self):
        status, _, error = self.launch_check("--source", str(self.tmp / "nowhere"), code="raise SystemExit(0)")
        self.assertEqual(status, 2)
        self.assertIn("source folder not found", error)

    def test_sync_bundle_selects_that_release_machine_wide(self):
        status, output, _ = self.cli("sync", "maya", SERIES, "--bundle", "1.1")
        self.assertEqual(status, 0)
        self.assertIn("1.1", output)
        self.assertEqual(prepared_release("maya", SERIES, self.config).release_id, "1.1")

    # the host entry

    def test_the_host_entry_runs_a_dev_source_and_says_so(self):
        entry = STRUCTURE / "THE-LINE" / "pipeline" / "__init__.py"
        if not entry.is_file():
            self.skipTest("pipeline entry not present")
        spec = importlib.util.spec_from_file_location("test_pipeline_dev", entry)
        pipeline = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(pipeline)
        source = self.source_folder({"__init__.py": "VALUE = 'from dev source'\n"})
        env = {"TLS_PIPELINE": str(self.pipeline), source_variable("maya"): str(source)}
        shown = io.StringIO()
        with patch.dict(sys.modules, {"test_pipeline_dev.localiser": sys.modules["localiser"]}), \
                patch.dict(os.environ, env), contextlib.redirect_stdout(shown):
            release = pipeline.start("maya", SERIES)
            self.assertEqual(sys.modules["tls_bundle_maya"].VALUE, "from dev source")
        self.assertEqual(release.source, "dev")
        self.assertIn("UNPUBLISHED", shown.getvalue())
        self.assertIn(str(source), shown.getvalue())
