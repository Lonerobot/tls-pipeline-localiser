"""The tray app's decisions: scheduling, auto-sync, summaries and wording. No Qt involved."""
import json
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from localiser import read_status
from localiser.status import EntryStatus, enabled_entries
from localiser_tray import model

from .helpers import SERIES, WorkstationTestCase


class RunCycleTests(WorkstationTestCase):
    def setUp(self):
        super().setUp()
        self.publish("maya", "1.0")
        self.publish("maya", "1.1")
        self.write_studio_config({"maya": "1.0"})
        self.config = replace(self.config, hosts={"maya": (SERIES,)})

    def select(self, release):
        self.write_studio_config({"maya": release})

    def test_progress_is_reported_before_each_entry_and_at_the_end(self):
        seen = []
        model.run_cycle(self.config, {}, progress=lambda done, total, label: seen.append((done, total)))
        self.assertEqual(seen, [(0, 1), (1, 1)])

    def test_the_first_cycle_installs_what_is_missing(self):
        result = model.run_cycle(self.config, {})
        self.assertEqual([(e.state, e.selected) for e in result.entries], [("current", "1.0")])
        self.assertEqual(result.changes, [model.Change("maya", SERIES, None, "1.0")])
        self.assertTrue(result.synced)

    def test_an_update_is_applied_when_auto_sync_is_on(self):
        model.run_cycle(self.config, {})
        self.select("1.1")
        result = model.run_cycle(self.config, {})
        self.assertEqual(result.changes, [model.Change("maya", SERIES, "1.0", "1.1")])
        self.assertEqual(read_status(self.config)["entries"][0]["selected"], "1.1")

    def test_an_update_is_only_reported_when_auto_sync_is_off(self):
        model.run_cycle(self.config, {})
        self.select("1.1")
        result = model.run_cycle(replace(self.config, auto_sync=False), {})
        self.assertEqual([e.state for e in result.entries], ["update_available"])
        self.assertEqual((result.changes, result.synced, result.level), ([], False, model.LEVEL_UPDATE))
        self.assertEqual(read_status(self.config)["entries"][0]["selected"], "1.0")  # nothing was selected

    def test_sync_now_applies_updates_even_with_auto_sync_off(self):
        config = replace(self.config, auto_sync=False)
        model.run_cycle(config, {})
        result = model.sync_now(config, {})
        self.assertEqual(result.changes, [model.Change("maya", SERIES, None, "1.0")])

    def test_nothing_to_do_when_current(self):
        model.run_cycle(self.config, {})
        result = model.run_cycle(self.config, {})
        self.assertEqual((result.changes, result.synced, result.level), ([], False, model.LEVEL_OK))

    def test_an_unreachable_repository_keeps_what_is_installed_and_reports_a_problem(self):
        model.run_cycle(self.config, {})
        offline = replace(self.config, remote_repository=self.tmp / "gone")
        result = model.run_cycle(offline, {})
        self.assertEqual((result.entries[0].state, result.entries[0].selected), ("offline", "1.0"))
        self.assertEqual((result.changes, result.level), ([], model.LEVEL_PROBLEM))

    def test_one_failing_entry_does_not_stop_the_others(self):
        self.publish("nuke", "2.0")
        self.write_studio_config({"maya": "1.0", "nuke": {"17.0": "2.0"}})
        config = replace(self.config, hosts={"maya": (SERIES,), "nuke": ("17.0", "99.9")})  # 99.9 isn't in the studio config
        result = model.run_cycle(config, {})
        states = {(e.host, e.series): e.state for e in result.entries}
        self.assertEqual(states[("maya", SERIES)], "current")
        self.assertEqual(states[("nuke", "17.0")], "current")
        self.assertEqual(states[("nuke", "99.9")], "unsupported")

    def test_nothing_enabled_and_nothing_of_the_studio_installed_here_is_idle_and_still_writes_a_status(self):
        with patch("localiser.status.detect_installed_series", return_value=[]):
            result = model.run_cycle(replace(self.config, hosts={}), {})
        self.assertEqual((result.entries, result.level), ([], model.LEVEL_IDLE))
        self.assertIsNotNone(read_status(self.config))

    def test_with_nothing_enabled_a_fresh_machine_follows_the_studio_config_for_what_is_installed(self):
        self.write_studio_config({"maya": {SERIES: "1.0", "2025": "1.0"}, "nuke": {"17.0": "1.0"}})
        installed = {"maya": [SERIES], "nuke": []}  # 2025 and Nuke aren't installed here
        with patch("localiser.status.detect_installed_series", lambda host, roots=None: installed.get(host, [])):
            result = model.run_cycle(replace(self.config, hosts={}), {})
            self.assertEqual([(e.host, e.series, e.state) for e in result.entries], [("maya", SERIES, "current")])
            self.assertEqual(enabled_entries(replace(self.config, hosts={})), [("maya", SERIES)])
            offline = replace(self.config, hosts={}, remote_repository=self.tmp / "gone")
            self.assertEqual(enabled_entries(offline), [("maya", SERIES)])  # from the last copy of the studio config
            self.assertEqual(enabled_entries(offline, cached_only=True), [("maya", SERIES)])
            # an explicit choice wins: nothing from the studio config is added to it
            self.assertEqual(enabled_entries(replace(self.config, hosts={"maya": ("2025",)})), [("maya", "2025")])

    def test_the_launcher_offers_what_the_studio_lists_when_nothing_is_enabled(self):
        self.write_studio_config({"maya": {SERIES: "1.0"}})
        config = replace(self.config, hosts={})
        with patch("localiser.status.detect_installed_series", return_value=[SERIES]), \
                patch.object(model, "detect_installed_series", lambda host, roots=None: [SERIES] if host == "maya" else []):
            self.assertEqual(model.launcher_choices(config), [])  # no copy of the studio config on this machine yet
            model.run_cycle(config, {})  # the first check keeps one
            self.assertEqual(model.launcher_choices(config), [("maya", SERIES)])


class SummaryTests(WorkstationTestCase):
    def entry(self, state, selected="1.0", target="1.1", message=""):
        return EntryStatus("maya", SERIES, state, selected, target, message)

    def test_overall_reports_the_worst_state(self):
        self.assertEqual(model.overall([])[0], model.LEVEL_IDLE)
        self.assertEqual(model.overall([self.entry("current")])[0], model.LEVEL_OK)
        self.assertEqual(model.overall([self.entry("current"), self.entry("update_available")])[0], model.LEVEL_UPDATE)
        self.assertEqual(model.overall([self.entry("not_prepared", None)])[0], model.LEVEL_UPDATE)
        self.assertEqual(model.overall([self.entry("update_available"), self.entry("offline")])[0], model.LEVEL_PROBLEM)
        self.assertEqual(model.overall([self.entry("current"), self.entry("error", message="x")])[0], model.LEVEL_PROBLEM)

    def test_unsupported_is_not_a_problem_for_the_user(self):
        self.assertEqual(model.overall([self.entry("unsupported", None, None)])[0], model.LEVEL_OK)

    def test_every_state_has_a_sentence(self):
        for state in ("current", "update_available", "not_prepared", "offline", "unsupported", "error"):
            with self.subTest(state=state):
                self.assertTrue(model.describe(self.entry(state, message="boom")))
        self.assertIn("1.0 -> 1.1", model.describe(self.entry("update_available")))
        self.assertEqual(model.describe(self.entry("error", message="boom")), "boom")

    def test_the_change_message_names_each_host_and_says_to_restart(self):
        text = model.change_message([model.Change("maya", "2026", "1.0", "1.1"), model.Change("nuke", "17.0", None, "2.0")])
        self.assertIn("Maya 2026: 1.1", text)
        self.assertIn("Nuke 17.0: 2.0", text)
        self.assertIn("Restart", text)


class DueTests(WorkstationTestCase):
    NOW = datetime(2026, 11, 9, 12, 0, tzinfo=timezone.utc)

    def status(self, minutes_ago):
        return {"checked_at": (self.NOW - timedelta(minutes=minutes_ago)).isoformat()}

    def test_due_only_once_the_interval_has_passed(self):
        self.assertFalse(model.is_due(self.status(10), 60, self.NOW))
        self.assertTrue(model.is_due(self.status(60), 60, self.NOW))
        self.assertTrue(model.is_due(self.status(500), 60, self.NOW))

    def test_due_when_there_is_no_usable_record(self):
        for status in (None, {}, {"checked_at": "yesterday"}, {"checked_at": 5}):
            with self.subTest(status=status):
                self.assertTrue(model.is_due(status, 60, self.NOW))

    def test_a_time_without_a_zone_is_taken_as_utc(self):
        naive = {"checked_at": (self.NOW - timedelta(minutes=1)).replace(tzinfo=None).isoformat()}
        self.assertFalse(model.is_due(naive, 60, self.NOW))


class HostChoiceTests(WorkstationTestCase):

    def test_the_launcher_offers_the_newest_installed_enabled_series_of_each_host_by_name(self):
        config = replace(self.config, hosts={"nuke": ("16.0", "17.0"), "maya": ("2025", "2026"), "blender": ("5.2",)})
        installed = {"nuke": ["16.0", "17.0"], "maya": ["2025"], "blender": []}  # 2026 isn't installed, 5.2 isn't either
        with patch.object(model, "detect_installed_series", lambda host, roots=None: installed.get(host, [])):
            self.assertEqual(model.launcher_choices(config), [("maya", "2025"), ("nuke", "17.0")])
        self.assertEqual(model.launcher_choices(None), [])

    def test_lists_installed_and_enabled_series_for_every_host(self):
        roots = [self.tmp / "pf"]
        (roots[0] / "Autodesk" / "Maya2025").mkdir(parents=True)
        (roots[0] / "Autodesk" / "Maya2026").mkdir(parents=True)
        (roots[0] / "Nuke17.0v3").mkdir(parents=True)
        config = replace(self.config, hosts={"maya": ("2026",), "blender": ("4.0",)})
        choices = {choice.host: choice for choice in model.host_choices(config, roots)}
        self.assertEqual(set(choices), {"maya", "nuke", "blender"})
        self.assertEqual(choices["maya"].series, [("2025", True, False), ("2026", True, True)])
        self.assertEqual(choices["nuke"].series, [("17.0", True, False)])
        self.assertEqual(choices["blender"].series, [("4.0", False, True)])  # enabled but not installed here
        self.assertEqual(choices["maya"].display_name, "Maya")

    def test_series_sort_numerically(self):
        roots = [self.tmp / "pf"]
        for series in ("Blender 4.10", "Blender 4.2", "Blender 5.0"):
            (roots[0] / "Blender Foundation" / series).mkdir(parents=True)
        blender = {c.host: c for c in model.host_choices(self.config, roots)}["blender"]
        self.assertEqual([s[0] for s in blender.series], ["4.2", "4.10", "5.0"])
