"""Editing the studio config, and a version the studio lists with no bundle selected (bundle_version null)."""
import contextlib
import importlib.util
import io
import json
import os
import sys
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from localiser import (
    ConfigError,
    NoBundleSelectedError,
    check_entry,
    parse_studio_config,
    prepared_release,
    set_studio_bundle,
    startup_release,
    studio_entries,
    sync_entry,
    sync_release,
)
from localiser.__main__ import main
from localiser.repository import WebRepository
from localiser.status import NO_BUNDLE, UNSUPPORTED, needs_sync
from localiser.studio import can_edit_studio

from .helpers import SERIES, WorkstationTestCase

STRUCTURE = Path(__file__).resolve().parents[1] / "structure"


class StudioConfigTests(WorkstationTestCase):
    def setUp(self):
        super().setUp()
        self.publish("maya", "1.0")
        self.publish("maya", "1.1")
        (self.repo / "config.json").write_text(json.dumps({
            "schema_version": 1,
            "_comment_hosts": "kept",
            "hosts": {
                "nuke": {"17.0": {"bundle_version": "5.0", "note": "kept too"}},
                "maya": {SERIES: {"bundle_version": "1.0"}},
            },
        }, indent=2), encoding="utf-8")

    def stored(self):
        return json.loads((self.repo / "config.json").read_text(encoding="utf-8"))

    # parsing

    def test_null_means_no_bundle_but_a_missing_or_bad_value_is_still_an_error(self):
        studio = parse_studio_config('{"schema_version": 1, "hosts": {"maya": {"2026": {"bundle_version": null}}}}')
        self.assertIsNone(studio.entry("maya", "2026"))
        with self.assertRaises(NoBundleSelectedError):
            studio.bundle_version("maya", "2026")
        for bad in ('{"maya": {"2026": {}}}', '{"maya": {"2026": {"bundle_version": 5}}}', '{"maya": {"2026": {"bundle_version": ""}}}'):
            with self.subTest(bad=bad), self.assertRaises(ConfigError):
                parse_studio_config('{"schema_version": 1, "hosts": %s}' % bad)

    # editing

    def test_setting_one_entry_keeps_everything_else(self):
        set_studio_bundle(self.config, "maya", SERIES, "1.1")
        document = self.stored()
        self.assertEqual(document["hosts"]["maya"][SERIES], {"bundle_version": "1.1"})
        self.assertEqual(document["hosts"]["nuke"], {"17.0": {"bundle_version": "5.0", "note": "kept too"}})
        self.assertEqual(document["_comment_hosts"], "kept")
        self.assertEqual(list(document["hosts"]), ["nuke", "maya"])  # the order is the file's

    def test_a_new_version_is_added_and_none_is_written_as_null(self):
        set_studio_bundle(self.config, "maya", "2027", "1.1")
        set_studio_bundle(self.config, "nuke", "17.0", None)
        document = self.stored()
        self.assertEqual(document["hosts"]["maya"]["2027"], {"bundle_version": "1.1"})
        self.assertEqual(document["hosts"]["nuke"]["17.0"], {"bundle_version": None, "note": "kept too"})
        self.assertEqual(studio_entries(self.config)[("nuke", "17.0")], None)
        self.assertEqual(studio_entries(self.config)[("maya", SERIES)], "1.0")

    def test_a_bad_request_or_file_changes_nothing(self):
        before = (self.repo / "config.json").read_text(encoding="utf-8")
        for args in (("maya", SERIES, "../x"), ("../x", SERIES, "1.0"), ("maya", "bad series!", "1.0")):
            with self.subTest(args=args), self.assertRaises(ConfigError):
                set_studio_bundle(self.config, *args)
        (self.repo / "config.json").write_text("{ not json", encoding="utf-8")
        with self.assertRaises(ConfigError):
            set_studio_bundle(self.config, "maya", SERIES, "1.0")
        self.assertEqual((self.repo / "config.json").read_text(encoding="utf-8"), "{ not json")
        self.assertEqual([p.name for p in self.repo.iterdir() if p.is_file()], ["config.json"])
        self.assertNotEqual(before, "{ not json")

    def test_a_web_repository_cannot_be_edited(self):
        web = replace(self.config, remote_repository=WebRepository("https://example.com/p"))
        with self.assertRaisesRegex(ConfigError, "web address"):
            set_studio_bundle(web, "maya", SERIES, "1.0")
        self.assertFalse(can_edit_studio(web)[0])
        self.assertTrue(can_edit_studio(self.config)[0])
        gone = replace(self.config, remote_repository=self.tmp / "nowhere")
        self.assertFalse(can_edit_studio(gone)[0])

    def test_the_studio_command_shows_and_sets(self):
        pipeline = self.tmp / "pipeline"
        pipeline.mkdir()
        (pipeline / "config.json").write_text(json.dumps({
            "schema_version": 1, "remote_repository": str(self.repo), "bundle_repository": str(self.data),
        }), encoding="utf-8")

        def cli(*args):
            with patch.dict(os.environ, {}, clear=True), contextlib.redirect_stdout(io.StringIO()) as out, \
                    contextlib.redirect_stderr(io.StringIO()) as err:
                return main(["--pipeline", str(pipeline), *args]), out.getvalue(), err.getvalue()

        self.assertEqual(cli("studio", "set", "maya", SERIES, "none")[0], 0)
        status, output, _ = cli("studio", "show")
        self.assertEqual(status, 0)
        self.assertIn("(no bundle)", output)
        self.assertEqual(cli("studio", "set", "maya", SERIES, "1.1")[0], 0)
        self.assertIn("1.1", cli("studio", "show")[1])

    # no bundle

    def test_no_bundle_is_reported_and_syncing_clears_what_a_dcc_would_start_with(self):
        config = replace(self.config, hosts={"maya": (SERIES,)})
        sync_release("maya", SERIES, config, {})
        self.assertEqual(prepared_release("maya", SERIES, config).release_id, "1.0")
        set_studio_bundle(config, "maya", SERIES, None)
        before = check_entry("maya", SERIES, config, {})
        self.assertEqual((before.state, before.selected, before.target), (NO_BUNDLE, "1.0", None))
        self.assertTrue(needs_sync(before))  # a DCC would still start the old bundle
        after = sync_entry("maya", SERIES, config, {})
        self.assertEqual((after.state, after.selected), (NO_BUNDLE, None))
        self.assertFalse(needs_sync(after))
        with self.assertRaises(NoBundleSelectedError):
            prepared_release("maya", SERIES, config)
        self.assertTrue((self.data / "hosts" / "maya" / "1.0" / ".complete").is_file())  # still installed

    def test_a_version_missing_from_the_studio_config_is_still_unsupported(self):
        self.assertEqual(check_entry("maya", "2099", self.config, {}).state, UNSUPPORTED)

    def test_a_pin_or_source_still_wins_over_no_bundle(self):
        set_studio_bundle(self.config, "maya", SERIES, None)
        source = self.tmp / "work"
        source.mkdir()
        (source / "__init__.py").write_text("", encoding="utf-8")
        release = startup_release("maya", SERIES, self.config, {"TLS_PIPELINE_MAYA_SOURCE": str(source)})
        self.assertEqual(release.source, "dev")

    def test_the_host_entry_warns_and_loads_nothing(self):
        entry = STRUCTURE / "THE-LINE" / "pipeline" / "__init__.py"
        if not entry.is_file():
            self.skipTest("pipeline entry not present")
        pipeline_root = self.tmp / "pipeline"
        pipeline_root.mkdir()
        (pipeline_root / "config.json").write_text(json.dumps({
            "schema_version": 1, "remote_repository": str(self.repo), "bundle_repository": str(self.data),
        }), encoding="utf-8")
        config = replace(self.config, hosts={"maya": (SERIES,)})
        sync_release("maya", SERIES, config, {})
        set_studio_bundle(config, "maya", SERIES, None)
        sync_entry("maya", SERIES, config, {})
        spec = importlib.util.spec_from_file_location("test_pipeline_none", entry)
        pipeline = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(pipeline)
        shown = io.StringIO()
        with patch.dict(sys.modules, {"test_pipeline_none.localiser": sys.modules["localiser"]}), \
                patch.dict(os.environ, {"TLS_PIPELINE": str(pipeline_root)}), contextlib.redirect_stdout(shown):
            self.assertIsNone(pipeline.start("maya", SERIES))
        self.assertIn("no bundle selected", shown.getvalue())
        self.assertNotIn("tls_bundle_maya", sys.modules)
