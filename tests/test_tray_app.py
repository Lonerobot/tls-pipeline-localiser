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

    def test_the_first_run_has_no_config_and_asks_for_the_repository(self):
        manager = self.make_manager()
        self.assertIsNone(manager.config)
        self.assertIn("repository", manager.window.settings.warning.text())
        self.assertEqual(manager.level, self.model.LEVEL_IDLE)
        self.assertEqual(list(manager.window.settings.series_boxes), [("maya", SERIES)])  # installed here, not yet enabled

    def test_saving_the_first_run_settings_writes_the_config_enables_the_host_and_updates(self):
        manager = self.make_manager()
        settings = manager.window.settings
        settings.remote.setText(str(self.repo))
        settings.series_boxes[("maya", SERIES)].setChecked(True)
        settings.save.click()
        self.wait_for(lambda: manager.config is not None and not manager.busy and manager.level == self.model.LEVEL_OK)
        self.assertEqual(manager.config.hosts, {"maya": (SERIES,)})
        self.assertTrue((self.tmp / "maya" / "modules" / "TheLinePipeline.mod").is_file())
        table = manager.window.status.table
        self.assertEqual([table.item(0, c).text() for c in (0, 1, 2, 3)], ["Maya", SERIES, "1.0", "1.0"])
        self.assertIn("Up to date", table.item(0, 4).text())

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
