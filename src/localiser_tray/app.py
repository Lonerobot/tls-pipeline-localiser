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

from localiser import (
    apply_hosts,
    clean_legacy_dev_copies,
    clone_bundle,
    install_pipeline_code,
    installed_releases,
    list_clones,
    pipeline_root,
    read_overrides,
    read_status,
    save_local_config,
    set_override,
)
from localiser.config import LocalConfig, default_pipeline_root, load_local_config, managed_repository
from localiser.errors import ConfigError, LocaliserError
from localiser.hosts import HOSTS
from localiser.launch import launch_host

from . import model
from .icons import brand_icon, tray_icon
from .launcher import LauncherWindow
from .notification import ACCENT, OVERRIDE_ACCENT, NotificationManager
from .window import MainWindow

TICK_SECONDS = 60  # how often to ask whether a check is due; cheap, it only reads the status file
APP_NAME = "THE LINE Pipeline"


class Manager(QObject):
    cycleFinished = Signal(object, bool)  # CycleResult, whether the user asked for it
    cycleFailed = Signal(str, bool)
    progressChanged = Signal(int, int, str)  # done, total, what is being worked on; emitted from the worker thread
    cloneFinished = Signal(str)  # the folder made
    cloneFailed = Signal(str)

    def __init__(self, environ: Mapping[str, str] | None = None):
        super().__init__()
        self.environ = dict(os.environ if environ is None else environ)
        self.config: LocalConfig | None = None
        self.problem = ""
        self.root: Path | None = None
        self.busy = False
        self.cloning = False
        self._syncing = False
        self.level = model.LEVEL_IDLE
        self.summary = ""
        self._notified: set = set()

        self.window = MainWindow()
        self.launcher = LauncherWindow()
        self.notifications = NotificationManager()
        self.tray = QSystemTrayIcon(tray_icon(self.level))
        self._build_menu()
        self.tray.activated.connect(self._tray_activated)
        self.launcher.launchRequested.connect(self.launch)
        self.window.status.checkRequested.connect(lambda: self.start_cycle(manual=True))
        self.window.status.syncRequested.connect(lambda: self.start_cycle(manual=True, sync=True))
        self.window.status.launchRequested.connect(self.launch)
        self.window.status.overrideRequested.connect(self.change_override)
        self.window.release.cloneRequested.connect(self.clone)
        self.window.settings.saveRequested.connect(self.save_settings)
        self.window.on_revert(self.reload)
        self.cycleFinished.connect(self._finished)
        self.cycleFailed.connect(self._failed)
        self.progressChanged.connect(self._progress)
        self.cloneFinished.connect(self._cloned)
        self.cloneFailed.connect(self._clone_failed)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)

    # setup ---------------------------------------------------------------------------------------

    def _build_menu(self):
        menu = QMenu()
        launcher = menu.addAction("Launcher", self.launcher.bring_to_front)
        font = launcher.font()
        font.setBold(True)
        launcher.setFont(font)
        menu.addSeparator()
        self.status_action = menu.addAction("Starting...")
        self.status_action.setEnabled(False)
        self.check_action = menu.addAction("Check for updates", lambda: self.start_cycle(manual=True))
        self.sync_action = menu.addAction("Update now", lambda: self.start_cycle(manual=True, sync=True))
        menu.addSeparator()
        menu.addAction("Settings...", self.window.bring_to_front)
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
        if self.root is not None and not (self.root / "config.json").exists() and managed_repository(self.environ):
            try:  # the organisation supplies the repository, so there is nothing to ask for on the first run
                save_local_config(self.root / "config.json", {}, self.environ)
            except (ConfigError, OSError) as exc:
                self.problem = str(exc)
        if self.root is None:
            self.problem = "No place to keep the pipeline could be found for this user."
        elif not (self.root / "config.json").exists():
            self.problem = self.problem or "Set the pipeline repository below to get started."
        else:
            try:
                self.config = load_local_config(self.root / "config.json", self.environ)
            except ConfigError as exc:
                self.problem = str(exc)
        warning = self.problem
        install_problem = ""
        if self.root is not None:
            try:
                install_pipeline_code(self.root)  # keeps the stubs and core in the root current, so a launch finds them
            except (LocaliserError, OSError) as exc:
                install_problem = f"The pipeline files could not be installed into {self.root}: {exc}"
        if install_problem:
            warning = install_problem
        elif self.config and not (self.root / "bootstrap").is_dir():
            warning = f"The pipeline files are missing from {self.root}; applications can't load it until it is installed."
        self.window.settings.load(self.config, model.host_choices(self.config), warning)
        if self.config:
            try:
                clean_legacy_dev_copies(self.config)  # throwaway copies older versions made at every start
            except OSError:
                pass
        self.launcher.show_choices(model.launcher_choices(self.config))
        self._show_last_status()

    def _show_last_status(self):
        document = read_status(self.config) if self.config else None
        entries = [model.EntryStatus(**entry) for entry in (document or {}).get("entries", [])]
        self.window.status.show_entries(
            entries, model.parse_time((document or {}).get("checked_at")), *self._override_view()
        )
        self.window.release.set_releases(self._release_choices(entries))
        if self.config is None:
            self._set_level(model.LEVEL_IDLE, self.problem)
        else:
            self._set_level(*model.overall(entries))

    def _override_view(self):
        """What the Status tab needs to offer overrides: the saved overrides and the clones each host has."""
        if self.config is None:
            return {}, {}
        return read_overrides(self.config), {host: list_clones(self.config, host) for host in HOSTS}

    def _release_choices(self, entries) -> dict:
        """The published releases the Release tab offers for each host: those installed and those the studio asks for."""
        if self.config is None:
            return {}
        choices = {}
        for host in HOSTS:
            ids = set(installed_releases(self.config, host)) | {e.target for e in entries if e.host == host and e.target}
            choices[host] = sorted(ids)
        return choices

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
        self._syncing = sync
        self._set_busy(True)

        def work():
            try:
                config = load_local_config(self.root / "config.json", self.environ)  # a fresh read: edits and installs apply
                run = model.sync_now if sync else model.run_cycle
                result = run(config, self.environ, progress=self.progressChanged.emit)
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
            self.status_action.setText("Updating..." if self._syncing else "Checking...")
            self.window.show_progress("Updating..." if self._syncing else "Checking...")
        else:
            self.window.hide_progress()

    def _progress(self, done: int, total: int, label: str):
        """Worker progress, delivered on the UI thread: a bar counting entries, and the same words in the tray."""
        if not self.busy or not total:
            return
        verb = "Updating" if self._syncing else "Checking"
        text = f"{verb} {label} ({min(done + 1, total)} of {total})" if done < total else f"{label}..."
        self.window.show_progress(text, done, total)
        self.status_action.setText(text)
        self.tray.setToolTip(f"{APP_NAME}\n{text}")

    # results -------------------------------------------------------------------------------------

    def _finished(self, result, manual: bool):
        self._set_busy(False)
        self.reload_config_only()
        self.window.status.show_entries(result.entries, datetime.now(timezone.utc), *self._override_view())
        self.window.release.set_releases(self._release_choices(result.entries))
        self._set_level(*model.overall(result.entries))
        if result.changes:
            self.notify(APP_NAME, model.change_message(result.changes), duration=10000)
        elif result.level == model.LEVEL_UPDATE:
            waiting = frozenset((e.host, e.series, e.target) for e in result.entries if e.state in model.NEEDS_SYNC)
            if waiting not in self._notified:  # once per set of updates, not on every check
                self._notified.add(waiting)
                self.notify(APP_NAME, self.summary, duration=8000)
        elif manual and result.level == model.LEVEL_OK:
            self.notify(APP_NAME, self.summary)

    def _failed(self, message: str, manual: bool):
        self._set_busy(False)
        self._set_level(model.LEVEL_PROBLEM, "The last check failed")
        if manual:
            self.window.show_error("Check failed", message)

    def reload_config_only(self):
        try:
            self.config = load_local_config(self.root / "config.json", self.environ)
        except (ConfigError, OSError):
            pass

    def _set_level(self, level: str, summary: str):
        self.level, self.summary = level, summary
        self.tray.setIcon(tray_icon(level))
        self.tray.setToolTip(f"{APP_NAME}\n{summary}")
        self.status_action.setText(summary)

    def _tray_activated(self, reason):
        if reason in (QSystemTrayIcon.ActivationReason.DoubleClick, QSystemTrayIcon.ActivationReason.Trigger):
            self.launcher.bring_to_front()

    # launching, overrides and cloning ------------------------------------------------------------

    def change_override(self, host: str, series: str, tag):
        """Launch `host` `series` from the clone `tag` (remembered), or back to the studio release when None."""
        if self.config is None:
            return
        try:
            set_override(self.config, host, series, tag)
        except (LocaliserError, OSError) as exc:
            self.window.show_error("Can't change the override", str(exc))
        self.window.status.show_entries(
            self.window.status.entries, self.window.status.checked_at, *self._override_view()
        )

    def clone(self, request: dict):
        """Make a clone in the dev folder, off the UI thread, and say where it is when it's done."""
        if self.config is None:
            self.window.release.show_result(False, "Set the pipeline repository on the Settings tab first.")
            return
        if self.cloning:
            return
        self.cloning = True
        self.window.release.set_busy(True)
        self.window.show_progress("Cloning...")
        config = self.config

        def work():
            try:
                if not request.get("tag"):
                    raise ConfigError("Enter a version tag for the clone.")
                if "release" in request:
                    if not request["release"]:
                        raise ConfigError("Choose the published release to clone.")
                elif not request.get("source"):
                    raise ConfigError("Choose the bundle source folder to clone.")
                folder = clone_bundle(
                    config, request["host"], request["tag"], release=request.get("release"),
                    source=request.get("source"), shared=request.get("shared", ()),
                )
            except Exception as exc:  # the worker must report, never die silently
                self.cloneFailed.emit(str(exc))
            else:
                self.cloneFinished.emit(str(folder))

        threading.Thread(target=work, name="pipeline-clone", daemon=True).start()

    def _cloned(self, folder: str):
        self._clone_done()
        self.window.release.show_result(True, f"Cloned to {folder}", folder)
        self.window.status.show_entries(
            self.window.status.entries, self.window.status.checked_at, *self._override_view()
        )
        self.window.release.set_releases(self._release_choices(self.window.status.entries))

    def _clone_failed(self, message: str):
        self._clone_done()
        self.window.release.show_result(False, message)

    def _clone_done(self):
        self.cloning = False
        if not self.busy:
            self.window.hide_progress()
        self.window.release.set_busy(False)

    def launch(self, host: str, series: str):
        """Start the application with the pipeline environment (supplied to that process only), without waiting."""
        if self.root is None:
            self.window.show_error("Can't launch", self.problem)
            return
        name = f"{model.display_name(host)} {series}"
        try:
            config = load_local_config(self.root / "config.json", self.environ)
            launch_host(host, series, config, self.environ)
        except (LocaliserError, OSError) as exc:
            self.window.show_error(f"Can't launch {name}", str(exc))
            return
        info = HOSTS.get(host)
        override = read_overrides(config).get(f"{host}/{series}")
        selected = next((e.selected for e in self.window.status.entries if (e.host, e.series) == (host, series)), None)
        detail = f"Override: {override}" if override else (f"Pipeline {selected}" if selected else "")
        self.notify(
            f"Launching {name}", detail, info.icon if info else None, 3500,
            OVERRIDE_ACCENT if override else ACCENT,
        )

    def notify(self, title: str, message: str = "", icon=None, duration: int = 4000, accent: str = ACCENT):
        """A popup above the taskbar; with no icon given it carries the pipeline's own."""
        self.notifications.show(title, message, icon if icon is not None else brand_icon(), duration, accent)

    # settings ------------------------------------------------------------------------------------

    def save_settings(self, hosts: dict, other: dict):
        """Write the config and the per-application entries in one step, then update straight away."""
        if self.root is None:
            self.window.show_error("Can't save", self.problem)
            return
        try:
            apply_hosts(self.root, hosts, other, self.environ)
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
