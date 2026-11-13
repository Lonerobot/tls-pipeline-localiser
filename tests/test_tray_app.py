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
        self.assertFalse(manager.window.create.open_dev.isEnabled())

    def test_the_organisations_repository_locks_the_field_and_needs_no_first_run_setup(self):
        from PySide6.QtWidgets import QToolButton

        self.environ["TLS_PIPELINE_REPOSITORY"] = str(self.repo)
        manager = self.make_manager()
        self.wait_for(lambda: not manager.busy)
        settings = manager.window.settings
        self.assertIsNotNone(manager.config)
        self.assertTrue(manager.config.remote_locked)
        self.assertTrue(settings.remote.isReadOnly())
        self.assertFalse(settings.remote_browse.isEnabled())
        self.assertTrue(settings.remote.parentWidget().findChild(QToolButton).isEnabled())
        self.assertFalse(settings.remote_note.isHidden())
        self.assertEqual(settings.remote.text(), str(self.repo))
        self.assertNotIn("remote_repository", settings.values()[1])
        self.assertNotIn("remote_repository", json.loads((self.root / "config.json").read_text(encoding="utf-8")))

    def test_folder_shortcuts_open_current_locations_and_handle_web_repositories(self):
        from pathlib import Path
        from PySide6.QtWidgets import QAbstractSpinBox, QLineEdit, QToolButton
        from localiser_tray.window import SettingsPage

        settings = SettingsPage()
        self.addCleanup(settings.deleteLater)
        location_fields = {
            edit for edit in settings.findChildren(QLineEdit)
            if not isinstance(edit.parentWidget(), QAbstractSpinBox)
        }
        self.assertEqual(location_fields, {settings.remote, settings.bundles})
        remote_button = settings.remote.parentWidget().findChild(QToolButton)
        self.assertFalse(remote_button.isEnabled())
        settings.remote.setText("https://example.com/pipeline")
        self.assertFalse(remote_button.isEnabled())
        self.assertIn("web address", remote_button.toolTip())
        settings.remote.setText(str(self.repo))
        releases = self.tmp / "local releases"
        releases.mkdir()
        settings.bundles.setText(str(releases))
        with patch("localiser_tray.widgets.QDesktopServices.openUrl", return_value=True) as opened:
            for edit in (settings.remote, settings.bundles):
                button = edit.parentWidget().findChild(QToolButton)
                self.assertEqual(button.text(), "")
                self.assertFalse(button.icon().isNull())
                button.click()
                self.assertEqual(Path(opened.call_args.args[0].toLocalFile()), Path(edit.text()).absolute())
        settings.bundles.clear()
        self.assertFalse(settings.bundles.parentWidget().findChild(QToolButton).isEnabled())

    def test_folder_shortcuts_report_missing_folders_and_desktop_open_failures(self):
        from PySide6.QtWidgets import QToolButton
        from localiser_tray.window import SettingsPage

        settings = SettingsPage()
        self.addCleanup(settings.deleteLater)
        missing = self.tmp / "not created"
        settings.bundles.setText(str(missing))
        button = settings.bundles.parentWidget().findChild(QToolButton)
        with patch("localiser_tray.widgets.QMessageBox.warning") as warning, \
                patch("localiser_tray.widgets.QDesktopServices.openUrl", return_value=False) as opened:
            button.click()
            opened.assert_not_called()
            self.assertIn(str(missing), warning.call_args.args[2])
            self.assertFalse(missing.exists())
            settings.bundles.setText(str(self.repo))
            button.click()
            opened.assert_called_once()
            self.assertIn("could not be opened", warning.call_args.args[2])

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

    def test_plain_tray_click_opens_only_the_launcher(self):
        manager = self.make_manager()
        manager.window.hide()
        with patch.object(
            self.app.QApplication, "keyboardModifiers", return_value=self.app.Qt.KeyboardModifier.ShiftModifier
        ), patch.object(
            self.app.QApplication, "queryKeyboardModifiers", return_value=self.app.Qt.KeyboardModifier.NoModifier
        ):
            manager._tray_activated(self.app.QSystemTrayIcon.ActivationReason.Trigger)
        self.assertTrue(manager.launcher.isVisible())
        self.assertFalse(manager.window.isVisible())
        manager.launcher.hide()

    def test_shift_tray_click_opens_normal_settings_even_after_admin_mode(self):
        manager = self.make_manager()
        for was_admin in (False, True):
            with self.subTest(was_admin=was_admin):
                manager.window.set_admin(was_admin)
                manager.window.hide()
                manager.launcher.hide()
                with patch.object(
                    self.app.QApplication, "keyboardModifiers", return_value=self.app.Qt.KeyboardModifier.NoModifier
                ), patch.object(
                    self.app.QApplication, "queryKeyboardModifiers", return_value=self.app.Qt.KeyboardModifier.ShiftModifier
                ):
                    manager._tray_activated(self.app.QSystemTrayIcon.ActivationReason.Trigger)
                self.assertTrue(manager.window.isVisible())
                self.assertIs(manager.window.tabs.currentWidget(), manager.window.settings)
                self.assertFalse(manager.window.admin)
                self.assertFalse(manager.window.tabs.isTabVisible(manager.window.tabs.indexOf(manager.window.create)))
                self.assertFalse(manager.window.settings.hosts_group.isHidden())
                self.assertFalse(manager.launcher.isVisible())

    def test_settings_displays_the_running_application_version_in_both_modes(self):
        original = self.qt.applicationVersion()
        self.addCleanup(self.qt.setApplicationVersion, original)
        self.qt.setApplicationVersion("9.8.7")
        manager = self.make_manager()
        for admin in (False, True):
            with self.subTest(admin=admin):
                manager.window.set_admin(admin)
                manager.window.show_settings()
                label = manager.window.settings.version_label
                self.assertEqual(label.text(), "Application version: 9.8.7")
                self.assertTrue(label.isVisible())

    def test_dark_theme_overrides_a_light_palette_for_windows_and_controls(self):
        from PySide6.QtGui import QColor, QPalette

        original = self.qt.palette()
        self.addCleanup(self.qt.setPalette, original)
        light = QPalette()
        for role in (QPalette.ColorRole.Window, QPalette.ColorRole.Base, QPalette.ColorRole.Button):
            light.setColor(role, QColor("white"))
        self.qt.setPalette(light)
        self.app.apply_dark_theme(self.qt)
        manager = self.make_manager()
        for widget, background, foreground in (
            (manager.window, QPalette.ColorRole.Window, QPalette.ColorRole.WindowText),
            (manager.window.settings.remote, QPalette.ColorRole.Base, QPalette.ColorRole.Text),
            (manager.window.settings.save, QPalette.ColorRole.Button, QPalette.ColorRole.ButtonText),
            (manager.menu, QPalette.ColorRole.Window, QPalette.ColorRole.WindowText),
        ):
            with self.subTest(widget=type(widget).__name__):
                palette = widget.palette()
                self.assertLess(palette.color(background).lightness(), 80)
                self.assertGreater(palette.color(foreground).lightness(), 180)
                self.assertGreater(
                    palette.color(QPalette.ColorGroup.Disabled, foreground).lightness(),
                    palette.color(background).lightness(),
                )

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

    def test_creating_then_overriding_launches_from_the_new_bundle_and_shows_the_row_in_orange(self):
        self.write_local(hosts={"maya": [SERIES]})
        manager = self.make_manager()
        self.wait_for(lambda: not manager.busy and manager.level == self.model.LEVEL_OK)
        status = manager.window.status
        self.assertFalse(status.override_buttons[("maya", SERIES)].isEnabled())  # nothing created yet
        page = manager.window.create
        page.tag.setText("mine")
        self.wait_for(lambda: page.release.count() > 0)
        page.release.setCurrentIndex(page.release.findData("1.0"))
        page.create_button.click()
        self.wait_for(lambda: not manager.creating)
        self.assertIn("Created", page.result.text())
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

    def test_the_release_list_marks_the_studio_default_and_follows_the_chosen_application(self):
        self.publish("maya", "0.9")  # published but never installed here
        self.publish("nuke", "5.0")
        self.write_studio_config({"maya": "1.0", "nuke": {"17.0": "5.0"}})
        self.write_local(hosts={"maya": [SERIES]})
        manager = self.make_manager()
        page = manager.window.create
        self.wait_for(lambda: page.release.count() == 2)
        labels = [page.release.itemText(i) for i in range(page.release.count())]
        self.assertEqual(page.release.itemData(0), "1.0")
        self.assertIn("studio default", labels[0])
        self.assertIn("downloaded when used", labels[1])  # 0.9 isn't installed
        self.assertEqual(page.release.currentData(), "1.0")  # starts on the studio default
        page.host.setCurrentIndex(page.host.findData("nuke"))  # another application: its own releases, no leftovers
        self.wait_for(lambda: [page.release.itemData(i) for i in range(page.release.count())] == ["5.0"])
        self.assertEqual(page.request().get("release"), "5.0")

    def test_a_zipped_source_asks_before_unzipping(self):
        import zipfile

        self.write_local(hosts={"maya": [SERIES]})
        manager = self.make_manager()
        self.wait_for(lambda: not manager.busy)
        folder = self.tmp / "zipped"
        folder.mkdir()
        with zipfile.ZipFile(folder / "pipeline.zip", "w") as archive:
            archive.writestr("__init__.py", "VALUE = 1\n")
        page = manager.window.create
        page.from_source.setChecked(True)
        page.source.setText(str(folder))
        page.tag.setText("from-zip")
        asked = []
        manager.window.confirm = lambda title, text: asked.append(text) or False
        page.create_button.click()
        self.wait_for(lambda: bool(asked) and not manager.creating)
        self.assertIn("zipped bundle", asked[0])
        self.assertFalse((self.root / "bundles" / "dev" / "maya" / "from-zip").exists())
        manager.window.confirm = lambda title, text: True
        page.create_button.click()
        self.wait_for(lambda: (self.root / "bundles" / "dev" / "maya" / "from-zip" / "__init__.py").is_file())
        self.wait_for(lambda: not manager.creating)
        self.assertIn("Created", page.result.text())

    def test_the_create_tab_asks_what_to_create_and_shows_only_that_form(self):
        self.write_local(hosts={"maya": [SERIES]})
        manager = self.make_manager()
        self.wait_for(lambda: not manager.busy)
        page = manager.window.create
        self.assertEqual(page.mode, "local")
        self.assertEqual(page.mode_local.title_label.text(), "A local pipeline bundle")
        self.assertEqual(page.mode_publish.title_label.text(), "Publish new studio bundle")
        self.assertTrue(page.mode_local.isChecked() and not page.mode_publish.isChecked())
        shown = lambda widget: widget.isVisibleTo(page)  # noqa: E731
        self.assertTrue(shown(page.local_panel) and shown(page.create_button))
        self.assertFalse(shown(page.publish_panel) or shown(page.publish_button))
        page.mode_publish.click()
        self.assertEqual(page.mode, "publish")
        self.assertFalse(page.mode_local.isChecked())  # one at a time
        self.assertFalse(shown(page.local_panel) or shown(page.create_button))
        self.assertTrue(shown(page.publish_panel) and shown(page.publish_button))
        page.mode_local.click()
        self.assertTrue(shown(page.local_panel))

    def test_the_host_icon_follows_the_application_for_both_source_folder_modes(self):
        from PySide6.QtGui import QIcon
        from localiser.hosts import HOSTS
        from localiser_tray.create_page import CreatePage

        page = CreatePage()
        self.addCleanup(page.deleteLater)
        page.from_source.setChecked(True)
        page.pub_from_source.setChecked(True)
        for mode, request in ((page.mode_local, page.request), (page.mode_publish, page.publish_request)):
            mode.click()
            for host, info in HOSTS.items():
                with self.subTest(mode=page.mode, host=host):
                    page.host.setCurrentIndex(page.host.findData(host))
                    self.assertTrue(page.host_icon.isVisibleTo(page))
                    self.assertFalse(page.host_icon.pixmap().isNull())
                    self.assertEqual(page.host_icon.toolTip(), f"Selected application: {info.display_name}")
                    self.assertEqual(page.host_icon.pixmap().toImage(), QIcon(str(info.icon)).pixmap(40, 40).toImage())
                    self.assertEqual(request()["host"], host)

    def test_the_dev_folder_shortcut_uses_the_configured_releases_folder_in_both_modes(self):
        from pathlib import Path

        self.write_local(hosts={"maya": [SERIES]}, bundle_repository=str(self.tmp / "custom bundles"))
        manager = self.make_manager()
        self.wait_for(lambda: not manager.busy)
        dev_folder = manager.config.bundle_repository / "dev"
        dev_folder.mkdir()
        page = manager.window.create
        with patch("localiser_tray.widgets.QDesktopServices.openUrl", return_value=True) as opened:
            for mode in (page.mode_local, page.mode_publish):
                mode.click()
                self.assertTrue(page.open_dev.isEnabled())
                self.assertEqual(page.open_dev.text(), "")
                self.assertFalse(page.open_dev.icon().isNull())
                page.open_dev.click()
                self.assertEqual(Path(opened.call_args.args[0].toLocalFile()), dev_folder)

    def test_publishing_a_dev_bundle_asks_first_and_uses_its_name_as_the_version(self):
        from localiser import clone_bundle

        self.write_local(hosts={"maya": [SERIES]})
        manager = self.make_manager()
        self.wait_for(lambda: not manager.busy)
        clone_bundle(manager.config, "maya", "2.0-wip", release="1.0")
        manager._refresh_bundles()
        page = manager.window.create
        page.mode_publish.click()
        self.assertEqual(page.bundle.currentData(), "2.0-wip")
        self.assertEqual(page.version.text(), "2.0-wip")  # the folder name, until the user says otherwise
        page.version.textEdited.emit("2.0")  # typing a version of their own: no longer follows the bundle name
        page.version.setText("2.0")
        asked = []
        manager.window.confirm = lambda title, text: asked.append(text) or False
        page.publish_button.click()
        self.assertIn("can't be changed or removed", asked[0])
        self.assertFalse((self.repo / "hosts" / "maya" / "2.0").exists())  # declined: nothing published
        manager.window.confirm = lambda title, text: True
        page.publish_button.click()
        self.wait_for(lambda: (self.repo / "hosts" / "maya" / "2.0" / "pipeline.zip").is_file())
        self.wait_for(lambda: not manager.creating)
        self.assertIn("Published Maya 2.0", page.result.text())
        self.assertIn("bundle_version", page.result.text())
        self.assertFalse(page.open_folder.isHidden())  # to see the release in the repository

    def test_publishing_says_what_is_missing_without_asking(self):
        self.write_local(hosts={"maya": [SERIES]})
        manager = self.make_manager()
        self.wait_for(lambda: not manager.busy)
        page = manager.window.create
        page.mode_publish.click()
        asked = []
        manager.window.confirm = lambda title, text: asked.append(text) or True
        page.publish_button.click()
        self.assertIn("version", page.result.text())
        page.version.setText("3.0")
        page.publish_button.click()
        self.assertIn("development bundle", page.result.text())
        page.pub_from_source.setChecked(True)
        page.publish_button.click()
        self.assertIn("source folder", page.result.text())
        self.assertEqual(asked, [])

    # admin mode

    def enter_admin(self, manager):
        with patch.object(self.app.QApplication, "keyboardModifiers", return_value=self.app.Qt.KeyboardModifier.ShiftModifier):
            manager.open_settings()

    def test_shift_on_settings_opens_admin_mode_and_plain_settings_leaves_it(self):
        self.write_local(hosts={"maya": [SERIES]})
        manager = self.make_manager()
        self.wait_for(lambda: not manager.busy)
        window = manager.window
        self.assertFalse(window.tabs.isTabVisible(window.tabs.indexOf(window.create)))  # Create is for admins only
        manager.open_settings()
        self.assertFalse(window.admin)
        self.assertEqual(window.windowTitle(), "THE LINE Pipeline")
        self.assertFalse(window.settings.hosts_group.isHidden())
        self.enter_admin(manager)
        self.assertTrue(window.admin)
        self.assertEqual(window.windowTitle(), "THE LINE Pipeline - ADMIN MODE")
        self.assertTrue(window.tabs.isTabVisible(window.tabs.indexOf(window.create)))
        self.assertFalse(window.settings.hosts_group.isHidden())
        self.assertFalse(window.status.admin_label.isHidden())
        self.assertFalse(window.status.admin_icon.isHidden())
        window.tabs.setCurrentWidget(window.create)
        manager.open_settings()  # Settings... again without Shift
        self.assertFalse(window.admin)
        self.assertFalse(window.tabs.isTabVisible(window.tabs.indexOf(window.create)))
        self.assertIs(window.tabs.currentWidget(), window.status)  # not left on the tab that has gone
        self.assertFalse(window.settings.hosts_group.isHidden())
        self.assertTrue(window.status.admin_label.isHidden())
        window.hide()

    def test_closing_the_window_ends_admin_mode(self):
        manager = self.make_manager()
        self.enter_admin(manager)
        self.assertTrue(manager.window.admin)
        manager.window.close()
        self.assertFalse(manager.window.admin)
        self.assertEqual(manager.window.windowTitle(), "THE LINE Pipeline")

    def test_admin_save_keeps_the_enabled_applications(self):
        self.write_local(hosts={"maya": [SERIES]})
        manager = self.make_manager()
        self.wait_for(lambda: not manager.busy)
        self.enter_admin(manager)
        self.assertEqual(manager.window.settings.values()[0], {"maya": [SERIES]})
        manager.window.close()

    def studio_ready(self, manager, key=("maya", SERIES), count=3):
        status = manager.window.status
        self.wait_for(lambda: key in status.studio_boxes and status.studio_boxes[key].count() >= count)
        return status.studio_boxes[key]

    def test_admin_status_offers_none_and_every_published_release_in_the_studio_column(self):
        self.publish("maya", "1.1")
        self.write_local(hosts={"maya": [SERIES]})
        manager = self.make_manager()
        self.wait_for(lambda: not manager.busy and manager.level == self.model.LEVEL_OK)
        self.assertNotIn(("maya", SERIES), manager.window.status.studio_boxes)  # plain mode: text only
        self.enter_admin(manager)
        box = self.studio_ready(manager)
        self.assertEqual([box.itemData(i) for i in range(box.count())], ["", "1.1", "1.0"])
        self.assertEqual(box.currentData(), "1.0")
        self.assertEqual(manager.window.status.table.item(0, 3).text(), "")  # the drop-down alone shows it; text underneath would garble it
        manager.window.close()
        self.assertEqual(manager.window.status.studio_boxes, {})
        self.assertIsNone(manager.window.status.table.cellWidget(0, 3))
        self.assertEqual(manager.window.status.table.item(0, 3).text(), "1.0")  # the text is back once the drop-down goes

    def test_choosing_another_studio_release_writes_the_studio_config_and_syncs(self):
        self.publish("maya", "1.1")
        self.write_local(hosts={"maya": [SERIES]})
        manager = self.make_manager()
        self.wait_for(lambda: not manager.busy and manager.level == self.model.LEVEL_OK)
        self.enter_admin(manager)
        box = self.studio_ready(manager)
        index = box.findData("1.1")
        box.setCurrentIndex(index)
        box.activated.emit(index)
        self.wait_for(lambda: json.loads((self.repo / "config.json").read_text())["hosts"]["maya"][SERIES]["bundle_version"] == "1.1")
        self.wait_for(lambda: not manager.busy and manager.window.status.table.item(0, 2).text() == "1.1")
        self.assertIn("Up to date", manager.window.status.table.item(0, 4).text())
        manager.window.close()

    def test_choosing_none_selects_no_bundle_and_the_row_says_so(self):
        self.write_local(hosts={"maya": [SERIES]})
        manager = self.make_manager()
        self.wait_for(lambda: not manager.busy and manager.level == self.model.LEVEL_OK)
        self.enter_admin(manager)
        box = self.studio_ready(manager, count=2)
        box.setCurrentIndex(0)
        box.activated.emit(0)
        self.wait_for(lambda: json.loads((self.repo / "config.json").read_text())["hosts"]["maya"][SERIES]["bundle_version"] is None)
        self.wait_for(lambda: not manager.busy and manager.window.status.table.item(0, 2).text() == "-")
        self.assertIn("No studio bundle", manager.window.status.table.item(0, 4).text())
        self.assertEqual(manager.level, self.model.LEVEL_UPDATE)
        manager.window.close()

    def test_admin_status_also_lists_studio_versions_not_enabled_here(self):
        self.write_studio_config({"maya": {SERIES: "1.0", "2025": "1.0"}})
        self.write_local(hosts={"maya": [SERIES]})
        manager = self.make_manager()
        self.wait_for(lambda: not manager.busy and manager.level == self.model.LEVEL_OK)
        status = manager.window.status
        self.assertEqual(status.table.rowCount(), 1)
        self.enter_admin(manager)
        self.studio_ready(manager, ("maya", "2025"), 2)
        self.assertEqual(status.table.rowCount(), 2)
        self.assertIn("Not enabled", status.table.item(1, 4).text())
        self.assertIsNone(status.table.cellWidget(1, 5))  # nothing to launch or override
        manager.window.close()
        self.assertEqual(status.table.rowCount(), 1)

    def test_a_web_repository_disables_the_studio_drop_downs_with_the_reason(self):
        self.write_local(hosts={"maya": [SERIES]}, remote_repository="https://example.com/studio")
        manager = self.make_manager()
        self.enter_admin(manager)
        status = manager.window.status
        self.wait_for(lambda: status.studio_editable[0] is False)
        box = status.studio_boxes.get(("maya", SERIES))
        if box is not None:
            self.assertFalse(box.isEnabled())
            self.assertIn("web address", box.toolTip())
        manager.window.close()

    def test_a_studio_write_that_fails_says_why(self):
        self.write_local(hosts={"maya": [SERIES]})
        manager = self.make_manager()
        self.wait_for(lambda: not manager.busy and manager.level == self.model.LEVEL_OK)
        self.enter_admin(manager)
        shown = []
        manager.window.show_error = lambda title, text: shown.append(text)
        (self.repo / "config.json").write_text("{ not json", encoding="utf-8")
        manager.change_studio_release("maya", SERIES, "1.0")
        self.wait_for(lambda: bool(shown))
        self.assertIn("not valid JSON", shown[0])
        manager.window.close()

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

    def test_creating_with_no_tag_says_what_is_missing(self):
        self.write_local(hosts={"maya": [SERIES]})
        manager = self.make_manager()
        self.wait_for(lambda: not manager.busy)
        page = manager.window.create
        page.create_button.click()
        self.wait_for(lambda: not manager.creating)
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
