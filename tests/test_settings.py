"""Changing the local config safely, and applying host changes to the entries the DCCs read."""
import json
from pathlib import Path
from unittest.mock import patch

from localiser import apply_hosts, load_local_config, save_local_config
from localiser.errors import ConfigError
from localiser.provision import blender_scripts_dir, maya_app_dir

from .helpers import WorkstationTestCase


class SaveLocalConfigTests(WorkstationTestCase):
    def setUp(self):
        super().setUp()
        self.path = self.tmp / "root" / "config.json"

    def write(self, document):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(document), encoding="utf-8")

    def stored(self):
        return json.loads(self.path.read_text(encoding="utf-8"))

    def test_creates_the_file_when_there_is_none(self):
        config = save_local_config(self.path, {"remote_repository": str(self.repo), "hosts": {"maya": ["2026"]}})
        self.assertEqual(config.remote_repository, self.repo)
        self.assertEqual(self.stored()["schema_version"], 1)
        self.assertEqual(load_local_config(self.path).hosts, {"maya": ("2026",)})

    def test_changes_only_what_was_given_and_keeps_the_rest(self):
        self.write({"schema_version": 1, "_comment_x": "kept", "remote_repository": str(self.repo), "custom": 7})
        save_local_config(self.path, {"check_interval_minutes": 30, "auto_sync": False})
        document = self.stored()
        self.assertEqual((document["_comment_x"], document["custom"]), ("kept", 7))
        self.assertEqual((document["check_interval_minutes"], document["auto_sync"]), (30, False))
        self.assertEqual(document["remote_repository"], str(self.repo))

    def test_paths_are_stored_as_text(self):
        self.write({"schema_version": 1, "remote_repository": "x"})
        save_local_config(self.path, {"remote_repository": self.repo, "bundle_repository": self.data})
        self.assertEqual(self.stored()["remote_repository"], str(self.repo))
        self.assertEqual(load_local_config(self.path).bundle_repository, self.data)

    def test_an_https_address_is_accepted_as_the_remote(self):
        self.write({"schema_version": 1, "remote_repository": str(self.repo)})
        config = save_local_config(self.path, {"remote_repository": "https://example.org/pipeline"})
        self.assertNotIsInstance(config.remote_repository, Path)

    def test_hosts_are_deduplicated_and_empty_hosts_dropped(self):
        self.write({"schema_version": 1, "remote_repository": str(self.repo)})
        config = save_local_config(self.path, {"hosts": {"nuke": ["17.0", "17.0"], "maya": [], "blender": ("5.2",)}})
        self.assertEqual(config.hosts, {"nuke": ("17.0",), "blender": ("5.2",)})

    def test_a_rejected_change_leaves_the_file_untouched(self):
        self.write({"schema_version": 1, "remote_repository": str(self.repo), "auto_sync": True})
        before = self.path.read_text(encoding="utf-8")
        for bad in (
            {"auto_sync": "yes"},
            {"check_interval_minutes": 1},
            {"hosts": {"maya": "2026"}},
            {"hosts": {"../evil": ["1"]}},
            {"remote_repository": "ftp://nope"},
            {"unknown": 1},
        ):
            with self.subTest(bad=bad), self.assertRaises(ConfigError):
                save_local_config(self.path, bad)
            self.assertEqual(self.path.read_text(encoding="utf-8"), before)
        self.assertEqual([p.name for p in self.path.parent.iterdir()], ["config.json"])  # no temp files left

    def test_a_missing_remote_is_rejected_when_creating(self):
        with self.assertRaises(ConfigError):
            save_local_config(self.path, {"hosts": {"maya": ["2026"]}})
        self.assertFalse(self.path.exists())

    def test_a_file_that_is_not_json_is_not_overwritten(self):
        self.path.parent.mkdir(parents=True)
        self.path.write_text("{ not json", encoding="utf-8")
        with self.assertRaises(ConfigError):
            save_local_config(self.path, {"auto_sync": False})
        self.assertEqual(self.path.read_text(encoding="utf-8"), "{ not json")


class ApplyHostsTests(WorkstationTestCase):
    def setUp(self):
        super().setUp()
        self.home = self.tmp / "home"
        self.home.mkdir()
        self.root = self.tmp / "root"
        self.root.mkdir()
        (self.root / "config.json").write_text(
            json.dumps({"schema_version": 1, "remote_repository": str(self.repo)}), encoding="utf-8"
        )
        self.env = {  # no BLENDER_USER_SCRIPTS: it would make every Blender series share one folder
            "MAYA_APP_DIR": str(self.tmp / "maya"),
            "APPDATA": str(self.tmp / "appdata"),
        }
        patcher = patch("pathlib.Path.home", return_value=self.home)
        patcher.start()
        self.addCleanup(patcher.stop)

    def apply(self, enabled):
        return apply_hosts(self.root, enabled, self.env)

    def maya_module(self):
        return maya_app_dir(self.env) / "modules" / "TheLinePipeline.mod"

    def blender_stub(self, series):
        return blender_scripts_dir(series, self.env) / "startup" / "tls_pipeline_startup.py"

    def test_enabling_saves_the_config_and_installs_each_entry(self):
        config, actions = self.apply({"maya": ["2026"], "blender": ["5.1", "5.2"]})
        self.assertEqual(config.hosts, {"maya": ("2026",), "blender": ("5.1", "5.2")})
        self.assertEqual(load_local_config(self.root / "config.json").hosts, config.hosts)
        self.assertTrue(self.maya_module().is_file())
        self.assertTrue(self.blender_stub("5.1").is_file() and self.blender_stub("5.2").is_file())
        self.assertEqual(len(actions), 3)

    def test_applying_the_same_thing_twice_changes_nothing(self):
        self.apply({"maya": ["2026"]})
        _, actions = self.apply({"maya": ["2026"]})
        self.assertEqual({action.change for action in actions}, {"unchanged"})

    def test_switching_off_one_blender_series_removes_only_its_entry(self):
        self.apply({"blender": ["5.1", "5.2"]})
        self.apply({"blender": ["5.2"]})
        self.assertFalse(self.blender_stub("5.1").exists())
        self.assertTrue(self.blender_stub("5.2").is_file())

    def test_maya_keeps_its_module_while_any_series_stays_enabled(self):
        self.apply({"maya": ["2025", "2026"]})
        self.apply({"maya": ["2026"]})
        self.assertTrue(self.maya_module().is_file())
        self.apply({})
        self.assertFalse(self.maya_module().exists())

    def test_switching_off_a_whole_host_removes_its_entries_and_leaves_others(self):
        self.apply({"maya": ["2026"], "blender": ["5.2"]})
        self.apply({"blender": ["5.2"]})
        self.assertFalse(self.maya_module().exists())
        self.assertTrue(self.blender_stub("5.2").is_file())

    def test_other_settings_are_saved_in_the_same_write(self):
        config, _ = apply_hosts(self.root, {"maya": ["2026"]}, self.env, {"check_interval_minutes": 15, "auto_sync": False})
        self.assertEqual((config.check_interval_minutes, config.auto_sync), (15, False))
        self.assertEqual(load_local_config(self.root / "config.json").check_interval_minutes, 15)

    def test_a_bad_setting_stops_the_hosts_changing_too(self):
        self.apply({"maya": ["2026"]})
        with self.assertRaises(ConfigError):
            apply_hosts(self.root, {"blender": ["5.2"]}, self.env, {"check_interval_minutes": 1})
        self.assertEqual(load_local_config(self.root / "config.json").hosts, {"maya": ("2026",)})
        self.assertTrue(self.maya_module().is_file())
        self.assertFalse(self.blender_stub("5.2").exists())

    def test_an_invalid_request_changes_neither_the_config_nor_the_entries(self):
        self.apply({"maya": ["2026"]})
        with self.assertRaises(ConfigError):
            self.apply({"maya": ["../x"]})
        self.assertEqual(load_local_config(self.root / "config.json").hosts, {"maya": ("2026",)})
        self.assertTrue(self.maya_module().is_file())
