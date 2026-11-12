"""The tray app end to end, with the real window and manager running offscreen against a temp pipeline root."""
import json
import os
import time
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtWidgets import QApplication
except ImportError:  # the core stays stdlib-only; the tray tests need PySide6
    QApplication = None

from .helpers import SERIES, WorkstationTestCase


@unittest.skipIf(QApplication is None, "PySide6 is not installed")
class TrayAppTests(WorkstationTestCase):
    @classmethod
    def setUpClass(cls):
        cls.qt = QApplication.instance() or QApplication([])

    def setUp(self):
        super().setUp()
        from localiser_tray import app, model

        self.app, self.model = app, model
        self.home = self.tmp / "home"
        self.home.mkdir()
        self.root = self.tmp / "Pipeline"
        self.environ = {
            "TLS_PIPELINE": str(self.root),
            "MAYA_APP_DIR": str(self.tmp / "maya"),
            "APPDATA": str(self.tmp / "appdata"),
        }
        for patcher in (
            patch("pathlib.Path.home", return_value=self.home),
            patch.object(model, "detect_installed_series", lambda host, roots=None: [SERIES] if host == "maya" else []),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)
        self.publish("maya", "1.0")
        self.write_studio_config({"maya": "1.0"})
        self.manager = None

    def tearDown(self):
        if self.manager:
            self.manager.timer.stop()
            self.manager.tray.hide()
            self.manager.window.deleteLater()

    def make_manager(self):
        self.manager = self.app.Manager(self.environ)
        self.manager.tray.show = lambda: None  # no tray on a test machine
        self.manager.start()
        return self.manager

    def wait_for(self, condition, seconds=20):
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            self.qt.processEvents()
            if condition():
                return
            time.sleep(0.01)
        self.fail("timed out waiting")

    def write_local(self, **extra):
        self.root.mkdir(parents=True, exist_ok=True)
        document = {"schema_version": 1, "remote_repository": str(self.repo), "bundle_repository": str(self.root / "bundles")}
        (self.root / "config.json").write_text(json.dumps({**document, **extra}), encoding="utf-8")

    def test_the_first_run_installs_the_pipeline_code_into_the_root(self):
        manager = self.make_manager()
        self.assertIsNone(manager.config)
        for relative in ("__init__.py", "about.py", "bootstrap/nuke/init.py", "localiser/launch.py"):
            self.assertTrue((self.root / relative).is_file(), relative)
        self.assertNotIn("could not be installed", manager.window.settings.warning.text())

    def test_a_stale_stub_is_refreshed_when_the_app_starts(self):
        self.write_local(hosts={"maya": [SERIES]})
        stub = self.root / "bootstrap" / "maya" / "userSetup.py"
        stub.parent.mkdir(parents=True)
        stub.write_text("# stale\n", encoding="utf-8")
        manager = self.make_manager()
        self.wait_for(lambda: not manager.busy)  # the start-up check writes into the root; let it finish
        self.assertNotEqual(stub.read_text(encoding="utf-8"), "# stale\n")

    def test_the_first_run_has_no_config_and_asks_for_the_repository(self):
        manager = self.make_manager()
        self.assertIsNone(manager.config)
        self.assertIn("repository", manager.window.settings.warning.text())
        self.assertEqual(manager.level, self.model.LEVEL_IDLE)
        self.assertEqual(list(manager.window.settings.series_boxes), [("maya", SERIES)])  # installed here, not yet enabled

    def test_the_organisations_repository_locks_the_field_and_needs_no_first_run_setup(self):
        self.environ["TLS_PIPELINE_REPOSITORY"] = str(self.repo)
        manager = self.make_manager()
        self.wait_for(lambda: not manager.busy)
        settings = manager.window.settings
        self.assertIsNotNone(manager.config)
        self.assertTrue(manager.config.remote_locked)
        self.assertTrue(settings.remote.isReadOnly())
        self.assertFalse(settings.remote_browse.isEnabled())
        self.assertFalse(settings.remote_note.isHidden())
        self.assertEqual(settings.remote.text(), str(self.repo))
        self.assertNotIn("remote_repository", settings.values()[1])
        self.assertNotIn("remote_repository", json.loads((self.root / "config.json").read_text(encoding="utf-8")))

    def test_saving_the_first_run_settings_writes_the_config_enables_the_host_and_updates(self):
        manager = self.make_manager()
        settings = manager.window.settings
        settings.remote.setText(str(self.repo))
        settings.series_boxes[("maya", SERIES)].setChecked(True)
        settings.save.click()
        self.wait_for(lambda: manager.config is not None and not manager.busy and manager.level == self.model.LEVEL_OK)
        self.assertEqual(manager.config.hosts, {"maya": (SERIES,)})
        self.assertFalse((self.tmp / "maya" / "modules" / "TheLinePipeline.mod").exists())  # no per-user entries
        self.assertTrue((self.root / "bootstrap" / "maya" / "userSetup.py").is_file())  # but the code a launch needs
        table = manager.window.status.table
        self.assertEqual([table.item(0, c).text() for c in (0, 1, 2, 3)], ["Maya", SERIES, "1.0", "1.0"])
        self.assertIn("Up to date", table.item(0, 4).text())

    def test_the_rocket_button_starts_the_host_with_the_pipeline_environment(self):
        self.write_local(hosts={"maya": [SERIES]})
        manager = self.make_manager()
        self.wait_for(lambda: not manager.busy and manager.level == self.model.LEVEL_OK)
        rocket = manager.window.status.launch_buttons[("maya", SERIES)]
        self.assertFalse(rocket.icon().isNull())
        with patch.object(self.app, "launch_host") as launch:
            rocket.click()
        launch.assert_called_once()
        self.assertEqual(launch.call_args.args[:2], ("maya", SERIES))
        self.assertEqual(launch.call_args.args[3]["TLS_PIPELINE"], str(self.root))

    def test_the_launcher_offers_the_enabled_installed_hosts_and_launches_them(self):
        self.write_local(hosts={"maya": [SERIES], "nuke": ["17.0"]})  # nuke is enabled but not installed here
        manager = self.make_manager()
        self.wait_for(lambda: not manager.busy)
        launcher = manager.launcher
        self.assertEqual(list(launcher.buttons), [("maya", SERIES)])
        self.assertEqual(launcher.buttons[("maya", SERIES)].toolTip(), f"Launch Maya {SERIES}")
        with patch.object(self.app, "launch_host") as launch:
            launcher.buttons[("maya", SERIES)].click()
        self.assertEqual(launch.call_args.args[:2], ("maya", SERIES))

    def test_the_launcher_has_nothing_to_change(self):
        from PySide6.QtWidgets import QCheckBox, QLineEdit

        manager = self.make_manager()
        self.assertEqual(manager.launcher.findChildren(QLineEdit) + manager.launcher.findChildren(QCheckBox), [])

    def test_the_tray_menu_leads_with_the_launcher_and_settings_opens_the_manager(self):
        manager = self.make_manager()
        actions = [a for a in manager.menu.actions() if not a.isSeparator()]
        self.assertEqual(actions[0].text(), "Launcher")
        self.assertNotIn("Open pipeline manager", [a.text() for a in actions])
        next(a for a in actions if a.text() == "Settings...").trigger()
        self.assertTrue(manager.window.isVisible())
        next(a for a in actions if a.text() == "Launcher").trigger()
        self.assertTrue(manager.launcher.isVisible())
        manager.window.hide()
        manager.launcher.hide()

    def test_a_cycle_reports_progress_for_each_entry(self):
        self.write_local(hosts={"maya": [SERIES]})
        manager = self.make_manager()
        self.wait_for(lambda: not manager.busy and manager.level == self.model.LEVEL_OK)
        seen = []
        manager.progressChanged.connect(lambda done, total, label: seen.append((done, total, label)))
        manager.start_cycle(manual=True, sync=True)
        self.assertTrue(manager.window.progress.isVisibleTo(manager.window))
        self.wait_for(lambda: not manager.busy)
        self.assertIn((0, 1, f"Maya {SERIES}"), seen)
        self.assertFalse(manager.window.progress.isVisibleTo(manager.window))

    def test_cloning_then_overriding_launches_from_the_clone_and_shows_the_row_in_orange(self):
        self.write_local(hosts={"maya": [SERIES]})
        manager = self.make_manager()
        self.wait_for(lambda: not manager.busy and manager.level == self.model.LEVEL_OK)
        status = manager.window.status
        self.assertFalse(status.override_buttons[("maya", SERIES)].isEnabled())  # nothing cloned yet
        page = manager.window.release
        page.tag.setText("mine")
        page.release.setEditText("1.0")
        page.clone.click()
        self.wait_for(lambda: not manager.cloning)
        self.assertIn("Cloned to", page.result.text())
        self.assertTrue((self.root / "bundles" / "dev" / "maya" / "mine" / ".tls-clone.json").is_file())
        toggle = status.override_buttons[("maya", SERIES)]
        self.assertTrue(toggle.isEnabled())
        toggle.click()
        self.assertEqual(status.override_boxes[("maya", SERIES)].currentText(), "mine")
        self.assertEqual(status.table.item(0, 0).background().color().name(), "#f0a030")
        with patch.object(self.app, "launch_host") as launch:
            status.launch_buttons[("maya", SERIES)].click()
        launch.assert_called_once()
        manager2_overrides = self.app.read_overrides(manager.config)
        self.assertEqual(manager2_overrides, {f"maya/{SERIES}": "mine"})
        status.override_buttons[("maya", SERIES)].click()  # off again
        self.assertEqual(self.app.read_overrides(manager.config), {})
        self.assertNotEqual(status.table.item(0, 0).background().color().name(), "#f0a030")
        self.assertIsNone(status.table.cellWidget(0, 4))  # the drop-down goes, leaving the status text
        self.assertNotIn(("maya", SERIES), status.override_boxes)

    def test_launching_shows_a_popup_with_the_application_icon(self):
        self.write_local(hosts={"maya": [SERIES]})
        manager = self.make_manager()
        self.wait_for(lambda: not manager.busy and manager.level == self.model.LEVEL_OK)
        with patch.object(self.app, "launch_host"):
            manager.launch("maya", SERIES)
        popup = manager.notifications.popups[-1]
        self.assertEqual(popup.title_label.text(), f"Launching Maya {SERIES}")
        self.assertEqual(popup.message_label.text(), "Pipeline 1.0")
        self.assertFalse(popup.icon_label.pixmap().isNull())
        popup.close()

    def test_popups_stack_dismiss_and_leave_nothing_behind(self):
        from localiser_tray.notification import NotificationManager

        shown = NotificationManager()
        first, second = shown.show("One", duration=0), shown.show("Two", "text", duration=0)
        self.assertLessEqual(first.y() + first.height(), second.y())  # the older one sits above the newest
        self.assertTrue(first.icon_label.isHidden() and second.message_label.isHidden() is False)
        first.dismiss()
        first.dismiss()  # twice is harmless
        self.wait_for(lambda: first not in shown.popups)
        self.assertEqual(shown.popups, [second])
        second.close()
        self.assertEqual(shown.popups, [])

    def test_a_clone_with_no_tag_says_what_is_missing(self):
        self.write_local(hosts={"maya": [SERIES]})
        manager = self.make_manager()
        self.wait_for(lambda: not manager.busy)
        page = manager.window.release
        page.clone.click()
        self.wait_for(lambda: not manager.cloning)
        self.assertIn("version tag", page.result.text())

    def test_a_launch_that_cannot_start_shows_why(self):
        self.write_local(hosts={"maya": [SERIES]})
        manager = self.make_manager()
        self.wait_for(lambda: not manager.busy and manager.level == self.model.LEVEL_OK)
        shown = []
        manager.window.show_error = lambda title, text: shown.append((title, text))
        with patch.object(self.app, "launch_host", side_effect=self.app.LocaliserError("Maya 2026 was not found")):
            manager.launch("maya", SERIES)
        self.assertEqual(shown, [("Can't launch Maya 2026", "Maya 2026 was not found")])

    def test_a_rejected_setting_shows_an_error_and_changes_nothing(self):
        self.write_local(hosts={"maya": [SERIES]})
        manager = self.make_manager()
        self.wait_for(lambda: not manager.busy and manager.level == self.model.LEVEL_OK)
        before = (self.root / "config.json").read_text(encoding="utf-8")
        shown = []
        manager.window.show_error = lambda title, text: shown.append((title, text))
        manager.window.settings.remote.setText("ftp://nope")
        manager.window.settings.save.click()
        self.assertEqual(len(shown), 1)
        self.assertEqual((self.root / "config.json").read_text(encoding="utf-8"), before)

    def test_start_checks_when_due_and_installs_automatically(self):
        self.write_local(hosts={"maya": [SERIES]})
        manager = self.make_manager()
        self.wait_for(lambda: not manager.busy and manager.level == self.model.LEVEL_OK)
        self.publish("maya", "1.1")
        self.write_studio_config({"maya": "1.1"})
        manager.start_cycle(manual=True)
        self.wait_for(lambda: not manager.busy)
        self.assertEqual(manager.window.status.table.item(0, 2).text(), "1.1")  # auto_sync defaults on

    def test_with_auto_sync_off_the_update_is_reported_not_installed(self):
        self.write_local(hosts={"maya": [SERIES]}, auto_sync=False)
        manager = self.make_manager()
        self.wait_for(lambda: not manager.busy and manager.window.status.table.rowCount() == 1)
        self.publish("maya", "1.1")
        self.write_studio_config({"maya": "1.1"})
        manager.start_cycle(manual=True)
        self.wait_for(lambda: not manager.busy)
        self.assertEqual(manager.level, self.model.LEVEL_UPDATE)
        self.assertEqual(manager.window.status.table.item(0, 2).text(), "-")  # nothing was ever installed
        manager.start_cycle(manual=True, sync=True)  # the "Update now" button
        self.wait_for(lambda: not manager.busy and manager.level == self.model.LEVEL_OK)
        self.assertEqual(manager.window.status.table.item(0, 2).text(), "1.1")

    def test_an_unreachable_repository_is_a_problem_not_a_crash(self):
        self.write_local(hosts={"maya": [SERIES]}, remote_repository=str(self.tmp / "gone"))
        manager = self.make_manager()
        self.wait_for(lambda: not manager.busy and manager.window.status.table.rowCount() == 1)
        self.assertEqual(manager.level, self.model.LEVEL_PROBLEM)

    def test_closing_the_window_hides_it_and_keeps_the_app_running(self):
        manager = self.make_manager()
        manager.window.bring_to_front()
        self.assertTrue(manager.window.isVisible())
        manager.window.close()
        self.assertFalse(manager.window.isVisible())

    def test_a_second_launch_is_refused_while_the_first_holds_the_lock(self):
        first = self.app.acquire_single_instance()
        try:
            self.assertIsNotNone(first)
            self.assertIsNone(self.app.acquire_single_instance())
        finally:
            first.unlock()
