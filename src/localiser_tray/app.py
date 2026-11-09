"""The tray app: keeps the local pipeline bundles current and lets a user choose what to keep current.

It calls the localiser core and nothing else; every decision it makes lives in `model`, which has no Qt in it.
A check runs when the app starts and then whenever the configured interval has passed, off the UI thread.
"""
import os
import sys
import tempfile
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping

from PySide6.QtCore import QLockFile, QObject, QTimer, Signal
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from localiser import apply_hosts, pipeline_root, read_status
from localiser.config import LocalConfig, default_pipeline_root, load_local_config
from localiser.errors import ConfigError, LocaliserError

from . import model
from .icons import level_icon
from .window import MainWindow

TICK_SECONDS = 60  # how often to ask whether a check is due; cheap, it only reads the status file
APP_NAME = "THE LINE Pipeline"


class Manager(QObject):
    cycleFinished = Signal(object, bool)  # CycleResult, whether the user asked for it
    cycleFailed = Signal(str, bool)

    def __init__(self, environ: Mapping[str, str] | None = None):
        super().__init__()
        self.environ = dict(os.environ if environ is None else environ)
        self.config: LocalConfig | None = None
        self.problem = ""
        self.root: Path | None = None
        self.busy = False
        self.level = model.LEVEL_IDLE
        self.summary = ""
        self._notified: set = set()

        self.window = MainWindow()
        self.tray = QSystemTrayIcon(level_icon(self.level))
        self._build_menu()
        self.tray.activated.connect(self._tray_activated)
        self.window.status.checkRequested.connect(lambda: self.start_cycle(manual=True))
        self.window.status.syncRequested.connect(lambda: self.start_cycle(manual=True, sync=True))
        self.window.settings.saveRequested.connect(self.save_settings)
        self.window.on_revert(self.reload)
        self.cycleFinished.connect(self._finished)
        self.cycleFailed.connect(self._failed)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)

    # setup ---------------------------------------------------------------------------------------

    def _build_menu(self):
        menu = QMenu()
        self.status_action = menu.addAction("Starting...")
        self.status_action.setEnabled(False)
        menu.addSeparator()
        menu.addAction("Open pipeline manager", self.window.bring_to_front)
        self.check_action = menu.addAction("Check for updates", lambda: self.start_cycle(manual=True))
        self.sync_action = menu.addAction("Update now", lambda: self.start_cycle(manual=True, sync=True))
        menu.addAction("Settings...", self.window.show_settings)
        menu.addSeparator()
        menu.addAction("Quit", QApplication.quit)
        self.menu = menu
        self.tray.setContextMenu(menu)

    def start(self, show_window: bool = False):
        self.reload()
        self.tray.show()
        self.timer.start(TICK_SECONDS * 1000)
        if self.config is None:  # nothing to manage yet: the first run is the settings page
            self.window.show_settings()
        elif show_window:
            self.window.bring_to_front()
        self._tick()

    def reload(self):
        """Read the config and the versions found on this computer, and refresh what the window shows."""
        self.config, self.problem = None, ""
        try:
            self.root = pipeline_root(self.environ)
        except ConfigError:
            self.root = default_pipeline_root(self.environ)
        if self.root is None:
            self.problem = "No place to keep the pipeline could be found for this user."
        elif not (self.root / "config.json").exists():
            self.problem = "Set the pipeline repository below to get started."
        else:
            try:
                self.config = load_local_config(self.root / "config.json")
            except ConfigError as exc:
                self.problem = str(exc)
        warning = self.problem
        if self.config and not (self.root / "bootstrap").is_dir():
            warning = f"The pipeline files are missing from {self.root}; applications can't load it until it is installed."
        self.window.settings.load(self.config, model.host_choices(self.config), warning)
        self._show_last_status()

    def _show_last_status(self):
        document = read_status(self.config) if self.config else None
        entries = [model.EntryStatus(**entry) for entry in (document or {}).get("entries", [])]
        self.window.status.show_entries(entries, model.parse_time((document or {}).get("checked_at")))
        if self.config is None:
            self._set_level(model.LEVEL_IDLE, self.problem)
        else:
            self._set_level(*model.overall(entries))

    # scheduling ----------------------------------------------------------------------------------

    def _tick(self):
        if self.busy or self.config is None:
            return
        if model.is_due(read_status(self.config), self.config.check_interval_minutes):
            self.start_cycle(manual=False)

    def start_cycle(self, manual: bool, sync: bool = False):
        if self.busy:
            return
        if self.config is None:
            if manual:
                self.window.show_settings()
            return
        self._set_busy(True)

        def work():
            try:
                config = load_local_config(self.root / "config.json")  # a fresh read: edits and installs apply
                run = model.sync_now if sync else model.run_cycle
                result = run(config, self.environ)
            except Exception as exc:  # the worker must report, never die silently
                self.cycleFailed.emit(str(exc), manual)
            else:
                self.cycleFinished.emit(result, manual)

        threading.Thread(target=work, name="pipeline-cycle", daemon=True).start()

    def _set_busy(self, busy: bool):
        self.busy = busy
        self.window.status.set_busy(busy)
        for action in (self.check_action, self.sync_action):
            action.setEnabled(not busy)
        if busy:
            self.status_action.setText("Checking...")

    # results -------------------------------------------------------------------------------------

    def _finished(self, result, manual: bool):
        self._set_busy(False)
        self.reload_config_only()
        self.window.status.show_entries(result.entries, datetime.now(timezone.utc))
        self._set_level(*model.overall(result.entries))
        if result.changes:
            self.tray.showMessage(APP_NAME, model.change_message(result.changes), QSystemTrayIcon.MessageIcon.Information, 10000)
        elif result.level == model.LEVEL_UPDATE:
            waiting = frozenset((e.host, e.series, e.target) for e in result.entries if e.state in model.NEEDS_SYNC)
            if waiting not in self._notified:  # once per set of updates, not on every check
                self._notified.add(waiting)
                self.tray.showMessage(APP_NAME, self.summary, QSystemTrayIcon.MessageIcon.Information, 8000)
        elif manual and result.level == model.LEVEL_OK:
            self.tray.showMessage(APP_NAME, self.summary, QSystemTrayIcon.MessageIcon.Information, 4000)

    def _failed(self, message: str, manual: bool):
        self._set_busy(False)
        self._set_level(model.LEVEL_PROBLEM, "The last check failed")
        if manual:
            self.window.show_error("Check failed", message)

    def reload_config_only(self):
        try:
            self.config = load_local_config(self.root / "config.json")
        except (ConfigError, OSError):
            pass

    def _set_level(self, level: str, summary: str):
        self.level, self.summary = level, summary
        self.tray.setIcon(level_icon(level))
        self.tray.setToolTip(f"{APP_NAME}\n{summary}")
        self.status_action.setText(summary)

    def _tray_activated(self, reason):
        if reason in (QSystemTrayIcon.ActivationReason.DoubleClick, QSystemTrayIcon.ActivationReason.Trigger):
            self.window.bring_to_front()

    # settings ------------------------------------------------------------------------------------

    def save_settings(self, hosts: dict, other: dict):
        """Write the config and the per-application entries in one step, then update straight away."""
        if self.root is None:
            self.window.show_error("Can't save", self.problem)
            return
        try:
            apply_hosts(self.root, hosts, self.environ, other)
        except (LocaliserError, OSError) as exc:
            self.window.show_error("Can't save settings", str(exc))
            return
        self.reload()
        self._notified.clear()
        self.start_cycle(manual=True, sync=True)


def acquire_single_instance() -> QLockFile | None:
    """A lock so a second launch (at login and from a shortcut, say) doesn't start a second tray icon."""
    lock = QLockFile(str(Path(tempfile.gettempdir()) / "theline-pipeline-manager.lock"))
    lock.setStaleLockTime(0)  # a lock left by a crashed run is never held against a new launch
    return lock if lock.tryLock(100) else None


def main(argv=None) -> int:
    argv = list(sys.argv if argv is None else argv)
    app = QApplication(argv)
    app.setApplicationName(APP_NAME)
    app.setQuitOnLastWindowClosed(False)  # the tray keeps it alive
    lock = acquire_single_instance()
    if lock is None:
        print(f"{APP_NAME} is already running.")
        return 0
    if not QSystemTrayIcon.isSystemTrayAvailable():
        print("No system tray is available on this desktop; the window opens instead.")
    manager = Manager()
    manager.start(show_window="--show" in argv or not QSystemTrayIcon.isSystemTrayAvailable())
    code = app.exec()
    lock.unlock()
    return code
