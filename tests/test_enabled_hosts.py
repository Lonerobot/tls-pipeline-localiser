"""Enabled hosts: local config keys, default location, detection, per-host status, check-all and sync-all."""
import contextlib
import io
import json
import os
from pathlib import Path
from unittest.mock import patch

from localiser import ConfigError, ReleaseUnavailableError, parse_local_config, prepared_release, sync_release
from localiser.__main__ import main
from localiser.config import default_pipeline_root
from localiser.hosts import HOSTS, detect_installed_series
from localiser.status import (
    CURRENT,
    ERROR,
    NOT_PREPARED,
    OFFLINE,
    UNSUPPORTED,
    UPDATE_AVAILABLE,
    check_enabled,
    check_entry,
    read_status,
    selection_changed,
    sync_enabled,
    sync_entry,
)
from localiser.sync import pipeline_root

from .helpers import SERIES, WorkstationTestCase


class LocalConfigKeyTests(WorkstationTestCase):
    def parse(self, **extra):
        text = json.dumps({
            "schema_version": 1, "remote_repository": str(self.repo), "bundle_repository": str(self.data), **extra
        })
        return parse_local_config(text, self.tmp)

    def test_new_keys_default_when_absent(self):
        config = self.parse()
        self.assertEqual((config.hosts, config.check_interval_minutes, config.auto_sync), ({}, 240, True))

    def test_hosts_are_read_and_deduplicated(self):
        config = self.parse(hosts={"nuke": ["17.0", "17.0"], "maya": []}, check_interval_minutes=30, auto_sync=False)
        self.assertEqual(config.hosts, {"nuke": ("17.0",), "maya": ()})
        self.assertEqual((config.check_interval_minutes, config.auto_sync), (30, False))

    def test_bad_values_are_errors(self):
        for extra in (
            {"hosts": []}, {"hosts": {"Nuke": ["17.0"]}}, {"hosts": {"nuke": "17.0"}}, {"hosts": {"nuke": ["../x"]}},
            {"check_interval_minutes": 1}, {"check_interval_minutes": "60"}, {"check_interval_minutes": True},
            {"auto_sync": "yes"},
        ):
            with self.subTest(extra=extra), self.assertRaises(ConfigError):
                self.parse(**extra)


class DefaultRootTests(WorkstationTestCase):
    def test_default_location_per_platform(self):
        self.assertEqual(
            default_pipeline_root({"LOCALAPPDATA": r"C:\Users\a\AppData\Local"}, "win32"),
            Path(r"C:\Users\a\AppData\Local") / "TheLine" / "Pipeline",
        )
        self.assertEqual(
            default_pipeline_root({"HOME": "/Users/a"}, "darwin"),
            Path("/Users/a/Library/Application Support/TheLine/Pipeline"),
        )
        self.assertEqual(default_pipeline_root({"HOME": "/home/a"}, "linux"), Path("/home/a/.local/share/theline/pipeline"))
        self.assertEqual(
            default_pipeline_root({"XDG_DATA_HOME": "/data", "HOME": "/home/a"}, "linux"), Path("/data/theline/pipeline")
        )
        self.assertIsNone(default_pipeline_root({}, "win32"))

    def test_the_variable_wins_and_the_default_is_used_only_when_installed(self):
        installed = self.tmp / "Local" / "TheLine" / "Pipeline"
        env = {"LOCALAPPDATA": str(self.tmp / "Local")}
        with patch("sys.platform", "win32"):
            with self.assertRaisesRegex(ConfigError, "no installation"):
                pipeline_root(env)
            installed.mkdir(parents=True)
            (installed / "config.json").write_text("{}", encoding="utf-8")
            self.assertEqual(pipeline_root(env), installed)
            self.assertEqual(pipeline_root({**env, "TLS_PIPELINE": str(self.tmp / "other")}), self.tmp / "other")


class DetectionTests(WorkstationTestCase):
    def test_installed_series_come_from_program_files_folder_names(self):
        pf = self.tmp / "Program Files"
        for folder in (
            "Autodesk/Maya2022", "Autodesk/Maya2026", "Autodesk/MayaUSD", "Autodesk/Maya2025",
            "Nuke15.1v2", "Nuke15.1v10", "Nuke17.0v3", "NukeStudio", "Blender Foundation/Blender 4.2",
            "Blender Foundation/Blender 5.2", "Blender Foundation/Blender 10.1", "Blender Foundation/Blender Launcher",
        ):
            (pf / folder).mkdir(parents=True)
        self.assertEqual(detect_installed_series("maya", [pf]), ["2022", "2025", "2026"])
        self.assertEqual(detect_installed_series("nuke", [pf]), ["15.1", "17.0"])
        self.assertEqual(detect_installed_series("blender", [pf]), ["4.2", "5.2", "10.1"])  # numeric, not text, order

    def test_missing_roots_and_unknown_hosts_find_nothing(self):
        self.assertEqual(detect_installed_series("maya", [self.tmp / "nowhere"]), [])
        self.assertEqual(detect_installed_series("houdini", [self.tmp]), [])

    def test_the_registry_covers_the_three_hosts_with_their_publish_defaults(self):
        self.assertEqual(set(HOSTS), {"maya", "nuke", "blender"})
        self.assertEqual((HOSTS["blender"].python_root, HOSTS["blender"].shared_destination), ("startup", "modules"))
        self.assertEqual((HOSTS["maya"].python_root, HOSTS["maya"].shared_destination), (".", "."))


class StatusTests(WorkstationTestCase):
    def setUp(self):
        super().setUp()
        self.write_studio_config({"maya": "1.0", "nuke": {"17.0": "2.0"}})
        self.publish("maya", "1.0")
        self.publish("maya", "1.1")
        self.publish("nuke", "2.0")
        self.env = {}

    def config_with(self, hosts):
        return parse_local_config(json.dumps({
            "schema_version": 1, "remote_repository": str(self.repo), "bundle_repository": str(self.data),
            "hosts": hosts,
        }), self.tmp)

    def test_states_for_one_entry(self):
        config = self.config_with({})
        self.assertEqual(check_entry("maya", SERIES, config, self.env).state, NOT_PREPARED)
        sync_release("maya", SERIES, config, self.env)
        self.assertEqual(check_entry("maya", SERIES, config, self.env).state, CURRENT)
        self.write_studio_config({"maya": "1.1"})
        update = check_entry("maya", SERIES, config, self.env)
        self.assertEqual((update.state, update.selected, update.target), (UPDATE_AVAILABLE, "1.0", "1.1"))
        self.assertEqual(check_entry("maya", "2099", config, self.env).state, UNSUPPORTED)
        self.assertEqual(check_entry("blender", "5.2", config, self.env).state, UNSUPPORTED)

    def test_offline_is_reported_not_raised(self):
        config = self.config_with({})
        sync_release("maya", SERIES, config, self.env)
        self.repo.rename(self.tmp / "offline")
        status = check_entry("maya", SERIES, config, self.env)
        self.assertEqual((status.state, status.selected, status.target), (OFFLINE, "1.0", "1.0"))
        self.assertEqual(check_entry("nuke", "17.0", config, self.env).state, OFFLINE)  # nothing cached for it

    def test_sync_entry_updates_and_reports_where_it_ended_up(self):
        config = self.config_with({})
        sync_release("maya", SERIES, config, self.env)
        self.write_studio_config({"maya": "1.1"})
        status = sync_entry("maya", SERIES, config, self.env)
        self.assertEqual((status.state, status.selected), (CURRENT, "1.1"))
        self.assertEqual(prepared_release("maya", SERIES, config).release_id, "1.1")

    def test_unsupported_entries_are_not_synced(self):
        config = self.config_with({})
        status = sync_entry("maya", "2099", config, self.env)
        self.assertEqual(status.state, UNSUPPORTED)
        self.assertFalse((self.data / "hosts").exists())  # nothing installed, though the config cache may exist

    def test_one_failing_entry_never_stops_the_others(self):
        self.write_studio_config({"maya": "9.9", "nuke": {"17.0": "2.0"}})  # maya's release was never published
        config = self.config_with({"maya": [SERIES], "nuke": ["17.0"]})
        by_host = {entry.host: entry for entry in sync_enabled(config, self.env)}
        self.assertEqual(by_host["maya"].state, OFFLINE)  # unavailable releases read as not fetchable
        self.assertEqual((by_host["nuke"].state, by_host["nuke"].selected), (CURRENT, "2.0"))

    def test_results_are_recorded_for_the_tray_app_and_hosts(self):
        config = self.config_with({"maya": [SERIES]})
        self.assertIsNone(read_status(config))
        check_enabled(config, self.env)
        status = read_status(config)
        self.assertEqual([(e["host"], e["state"]) for e in status["entries"]], [("maya", NOT_PREPARED)])
        self.assertIn("checked_at", status)
        sync_enabled(config, self.env)
        self.assertEqual(read_status(config)["entries"][0]["state"], CURRENT)

    def test_a_running_session_learns_the_selection_changed_from_local_state_only(self):
        config = self.config_with({})
        sync_release("maya", SERIES, config, self.env)
        self.assertIsNone(selection_changed("maya", SERIES, "1.0", config))
        self.write_studio_config({"maya": "1.1"})
        sync_release("maya", SERIES, config, self.env)
        self.repo.rename(self.tmp / "offline")  # no network needed
        self.assertEqual(selection_changed("maya", SERIES, "1.0", config), "1.1")
        self.assertIsNone(selection_changed("maya", SERIES, "1.1", config))
        self.assertIsNone(selection_changed("nuke", "17.0", "x", config))


class EnabledCommandTests(StatusTests):
    def setUp(self):
        super().setUp()
        self.pipeline = self.tmp / "pipeline"
        self.pipeline.mkdir()
        self.write_local({"maya": [SERIES], "nuke": ["17.0"]})

    def write_local(self, hosts):
        (self.pipeline / "config.json").write_text(json.dumps({
            "schema_version": 1, "remote_repository": str(self.repo), "bundle_repository": str(self.data), "hosts": hosts,
        }), encoding="utf-8")

    def cli(self, *args):
        with patch.dict(os.environ, {}, clear=True), contextlib.redirect_stdout(io.StringIO()) as out:
            with contextlib.redirect_stderr(io.StringIO()) as err:
                status = main(["--pipeline", str(self.pipeline), *args])
        return status, out.getvalue(), err.getvalue()

    def test_check_all_reports_updates_with_exit_one_and_installs_nothing(self):
        status, out, _ = self.cli("check-all")
        self.assertEqual(status, 1)
        self.assertIn("maya 2026: not prepared; target 1.0", out)
        self.assertIn("nuke 17.0: not prepared; target 2.0", out)
        self.assertFalse((self.data / "hosts").exists())

    def test_sync_all_then_check_all_is_up_to_date(self):
        status, out, _ = self.cli("sync-all")
        self.assertEqual((status, out.count("up to date")), (0, 2))
        status, out, _ = self.cli("check-all")
        self.assertEqual(status, 0)

    def test_a_problem_gives_exit_two_but_the_other_hosts_are_still_synced(self):
        self.write_studio_config({"maya": "9.9", "nuke": {"17.0": "2.0"}})
        status, out, _ = self.cli("sync-all")
        self.assertEqual(status, 2)
        self.assertIn("nuke 17.0: up to date: 2.0", out)
        self.assertIn("maya 2026: offline", out)

    def test_unsupported_series_are_informational_not_failures(self):
        self.write_local({"maya": [SERIES, "2099"]})
        status, out, _ = self.cli("sync-all")
        self.assertEqual(status, 0)
        self.assertIn("maya 2099: unsupported", out)

    def test_nothing_enabled_says_how_to_enable(self):
        self.write_local({})
        status, out, _ = self.cli("sync-all")
        self.assertEqual(status, 0)
        self.assertIn('"hosts"', out)

    def test_hosts_lists_the_registry_with_what_is_enabled(self):
        with patch("localiser.__main__.detect_installed_series", side_effect=lambda host: {"maya": ["2026"]}.get(host, [])):
            status, out, _ = self.cli("hosts")
        self.assertEqual(status, 0)
        self.assertIn("Maya     installed: 2026   enabled: 2026", out)
        self.assertIn("Blender  installed: none found   enabled: none", out)
