"""Changing the local config safely, and applying host changes to the entries the DCCs read."""
import json
from pathlib import Path
from unittest.mock import patch

from localiser import apply_hosts, load_local_config, save_local_config
from localiser.errors import ConfigError

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

    def test_the_organisations_repository_is_never_written_and_cannot_be_changed(self):
        env = {"TLS_PIPELINE_REPOSITORY": str(self.repo)}
        config = save_local_config(self.path, {"hosts": {"maya": ["2026"]}}, env)
        self.assertTrue(config.remote_locked)
        self.assertNotIn("remote_repository", self.stored())
        before = self.path.read_text(encoding="utf-8")
        with self.assertRaisesRegex(ConfigError, "organisation"):
            save_local_config(self.path, {"remote_repository": "D:/mine"}, env)
        self.assertEqual(self.path.read_text(encoding="utf-8"), before)


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
        self.env = {  # where Maya and Blender would look for per-user entries
            "MAYA_APP_DIR": str(self.tmp / "maya"),
            "APPDATA": str(self.tmp / "appdata"),
        }
        patcher = patch("pathlib.Path.home", return_value=self.home)
        patcher.start()
        self.addCleanup(patcher.stop)

    def apply(self, enabled):
        return apply_hosts(self.root, enabled)

    def assert_no_entries_written(self):
        self.assertFalse((self.tmp / "maya").exists())
        self.assertFalse((self.tmp / "appdata").exists())
        self.assertFalse((self.home / ".nuke").exists())

    def test_enabling_saves_the_config(self):
        config = self.apply({"maya": ["2026"], "blender": ["5.1", "5.2"]})
        self.assertEqual(config.hosts, {"maya": ("2026",), "blender": ("5.1", "5.2")})
        self.assertEqual(load_local_config(self.root / "config.json").hosts, config.hosts)

    def test_saving_writes_no_per_user_entries(self):
        self.apply({"maya": ["2026"], "nuke": ["17.0"], "blender": ["5.2"]})
        self.assert_no_entries_written()

    def test_applying_the_same_thing_twice_changes_nothing(self):
        self.apply({"maya": ["2026"]})
        before = (self.root / "config.json").read_text(encoding="utf-8")
        self.apply({"maya": ["2026"]})
        self.assertEqual((self.root / "config.json").read_text(encoding="utf-8"), before)

    def test_switching_a_host_off_removes_it_from_the_config(self):
        self.apply({"maya": ["2026"], "blender": ["5.2"]})
        self.assertEqual(self.apply({"blender": ["5.2"]}).hosts, {"blender": ("5.2",)})

    def test_other_settings_are_saved_in_the_same_write(self):
        config = apply_hosts(self.root, {"maya": ["2026"]}, {"check_interval_minutes": 15, "auto_sync": False})
        self.assertEqual((config.check_interval_minutes, config.auto_sync), (15, False))
        self.assertEqual(load_local_config(self.root / "config.json").check_interval_minutes, 15)

    def test_a_bad_setting_stops_the_hosts_changing_too(self):
        self.apply({"maya": ["2026"]})
        with self.assertRaises(ConfigError):
            apply_hosts(self.root, {"blender": ["5.2"]}, {"check_interval_minutes": 1})
        self.assertEqual(load_local_config(self.root / "config.json").hosts, {"maya": ("2026",)})

    def test_an_invalid_request_changes_nothing(self):
        self.apply({"maya": ["2026"]})
        with self.assertRaises(ConfigError):
            self.apply({"maya": ["../x"]})
        self.assertEqual(load_local_config(self.root / "config.json").hosts, {"maya": ("2026",)})
