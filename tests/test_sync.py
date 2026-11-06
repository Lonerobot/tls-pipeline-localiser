import contextlib
import importlib.util
import io
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

from localiser import (
    ReleaseUnavailableError,
    VerificationError,
    load_prepared_release,
    localise,
    prepared_release,
    sync_release,
)
from localiser.__main__ import main
from localiser.archive import safe_extract
from localiser.layout import DataLayout

from .helpers import SERIES, WorkstationTestCase


class SyncTests(WorkstationTestCase):
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
        self.publish("maya", "1.0", {"__init__.py": "VALUE = 'old'\n"})

    def sync(self, series=SERIES):
        return sync_release("maya", series, self.config, {})

    def cli(self, *args):
        with patch.dict(os.environ, {}, clear=True), contextlib.redirect_stdout(io.StringIO()) as output:
            with contextlib.redirect_stderr(io.StringIO()) as errors:
                status = main(["--pipeline", str(self.pipeline), *args])
        return status, output.getvalue(), errors.getvalue()

    def test_startup_requires_explicit_sync_even_when_remote_is_available(self):
        with self.assertRaisesRegex(ReleaseUnavailableError, "run sync"):
            prepared_release("maya", SERIES, self.config)
        self.assertFalse(self.data.exists())

    def test_startup_is_local_only_and_read_only(self):
        synced = self.sync()
        self.write_studio_config({"maya": "missing-update"})
        before = {p: p.read_bytes() for p in self.data.rglob("*") if p.is_file()}
        with patch("localiser.resolve.resolve_release", side_effect=AssertionError("remote resolution")), \
                patch("localiser.api.ensure_release", side_effect=AssertionError("installation")):
            loaded = load_prepared_release("maya", SERIES, {"TLS_PIPELINE": str(self.pipeline)})
        self.assertEqual(loaded.release_root, synced.release_root)
        self.assertEqual(before, {p: p.read_bytes() for p in self.data.rglob("*") if p.is_file()})
        self.repo.rename(self.tmp / "offline")
        self.assertEqual(prepared_release("maya", SERIES, self.config), loaded)

    def test_failed_update_keeps_previous_selection(self):
        old = self.sync()
        self.publish("maya", "2.0")
        self.write_studio_config({"maya": "2.0"})
        (self.repo / "hosts" / "maya" / "2.0" / "pipeline.zip").write_bytes(b"broken")
        with self.assertRaises(VerificationError):
            self.sync()
        self.assertEqual(prepared_release("maya", SERIES, self.config).release_root, old.release_root)
        self.assertFalse((self.data / "hosts" / "maya" / "2.0" / ".complete").exists())

    def test_update_retains_old_bundle_and_selects_new_bundle_on_next_start(self):
        old = self.sync()
        self.publish("maya", "2.0")
        self.write_studio_config({"maya": "2.0"})
        new = self.sync()
        self.assertEqual(prepared_release("maya", SERIES, self.config).release_id, "2.0")
        self.assertNotEqual(old.release_root, new.release_root)
        self.assertEqual((old.python_root / "__init__.py").read_text(), "VALUE = 'old'\n")

    def test_incomplete_cached_target_does_not_replace_usable_selection(self):
        old = self.sync()
        self.publish("maya", "2.0", {"python/tool.py": "VALUE = 2\n"}, python_root="python")
        self.write_studio_config({"maya": "2.0"})
        cached = localise("maya", SERIES, self.config, {})
        shutil.rmtree(cached.python_root)
        with self.assertRaisesRegex(ReleaseUnavailableError, "repair required"):
            self.sync()
        self.assertEqual(prepared_release("maya", SERIES, self.config).release_root, old.release_root)

    def test_startup_during_extraction_keeps_complete_previous_selection(self):
        old = self.sync()
        self.publish("maya", "2.0")
        self.write_studio_config({"maya": "2.0"})

        def extract(archive, destination):
            self.assertEqual(prepared_release("maya", SERIES, self.config).release_root, old.release_root)
            self.assertFalse((self.data / "hosts" / "maya" / "2.0").exists())
            safe_extract(archive, destination)

        with patch("localiser.install.safe_extract", side_effect=extract):
            self.sync()
        self.assertEqual(prepared_release("maya", SERIES, self.config).release_id, "2.0")

    def test_selections_are_per_host_and_series(self):
        self.sync()
        self.publish("maya", "2.0")
        self.publish("nuke", "3.0")
        self.write_studio_config({"maya": {"2025": "2.0", SERIES: "1.0"}, "nuke": {"17.0": "3.0"}})
        self.sync("2025")
        sync_release("nuke", "17.0", self.config, {})
        self.assertEqual(prepared_release("maya", SERIES, self.config).release_id, "1.0")
        self.assertEqual(prepared_release("maya", "2025", self.config).release_id, "2.0")
        self.assertEqual(prepared_release("nuke", "17.0", self.config).release_id, "3.0")

    def test_invalid_selection_or_incomplete_marker_is_never_loaded(self):
        self.sync()
        selection = DataLayout(self.data).prepared_file("maya", SERIES)
        for state in ("[]", "{", '{"schema_version":true,"release_id":"1.0"}',
                      '{"schema_version":1,"release_id":"../../escape"}'):
            with self.subTest(state=state):
                selection.write_text(state, encoding="utf-8")
                with self.assertRaises(ReleaseUnavailableError):
                    prepared_release("maya", SERIES, self.config)
        self.sync()
        (self.data / "hosts" / "maya" / "1.0" / ".complete").unlink()
        with self.assertRaisesRegex(ReleaseUnavailableError, "incomplete"):
            prepared_release("maya", SERIES, self.config)

    def test_check_does_not_install_or_activate_and_reports_offline(self):
        self.assertEqual(self.cli("check", "maya", SERIES)[0], 1)
        self.assertFalse((self.data / "hosts").exists())
        self.assertFalse(DataLayout(self.data).prepared_file("maya", SERIES).exists())
        self.assertEqual(self.cli("sync", "maya", SERIES)[0], 0)
        self.assertEqual(self.cli("check", "maya", SERIES)[0], 0)
        self.write_studio_config({"maya": "2.0"})
        self.assertEqual(self.cli("check", "maya", SERIES)[0], 1)
        self.assertEqual(prepared_release("maya", SERIES, self.config).release_id, "1.0")
        (self.repo / "config.json").unlink()
        status, _, error = self.cli("check", "maya", SERIES)
        self.assertEqual(status, 2)
        self.assertIn("offline", error)

    def test_launch_sets_child_environment_without_sync(self):
        release = self.sync()
        self.repo.rename(self.tmp / "offline")
        output = self.tmp / "child.json"
        code = (
            "import json, os, pathlib; "
            f"pathlib.Path({str(output)!r}).write_text(json.dumps(dict(os.environ)))"
        )
        status, _, error = self.cli("launch", "maya", SERIES, sys.executable, "-c", code)
        self.assertEqual((status, error), (0, ""))
        env = json.loads(output.read_text())
        self.assertEqual(env["TLS_PIPELINE"], str(self.pipeline))
        self.assertEqual(env["TLS_PIPELINE_MAYA"], str(release.release_root))
        self.assertEqual(env["PYTHONPATH"], str(self.pipeline / "bootstrap" / "maya"))
        status, _, _ = self.cli("launch", "maya", SERIES, sys.executable, "-c", "raise SystemExit(7)")
        self.assertEqual(status, 7)

    def test_host_entry_loads_prepared_bundle_without_sync(self):
        self.sync()
        self.repo.rename(self.tmp / "offline")
        entry = Path(__file__).resolve().parents[1] / "structure" / "THE-LINE" / "pipeline" / "__init__.py"
        spec = importlib.util.spec_from_file_location("test_pipeline", entry)
        pipeline = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(pipeline)
        with patch.dict(sys.modules, {"test_pipeline.localiser": sys.modules["localiser"]}), \
                patch.dict(os.environ, {"TLS_PIPELINE": str(self.pipeline)}):
            release = pipeline.start("maya", SERIES)
            self.assertEqual(os.environ["TLS_PIPELINE_MAYA"], str(release.release_root))
            self.assertEqual(sys.modules["tls_bundle_maya"].VALUE, "old")

    def test_module_entry_point_and_missing_preparation_error(self):
        result = subprocess.run(
            [sys.executable, "-m", "localiser", "--pipeline", str(self.pipeline), "check", "maya", SERIES],
            capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 1, result.stderr)
        status, _, error = self.cli("launch", "maya", SERIES, sys.executable)
        self.assertEqual(status, 2)
        self.assertIn("run sync", error)
