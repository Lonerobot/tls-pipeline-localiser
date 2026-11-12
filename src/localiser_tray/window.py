"""The pipeline manager window: what each application is running, and the settings behind it."""
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QSize, Qt, QUrl, Signal
from PySide6.QtGui import QBrush, QColor, QDesktopServices, QIcon
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from localiser.config import MAX_CHECK_INTERVAL_MINUTES, MIN_CHECK_INTERVAL_MINUTES, REPOSITORY_VARIABLE
from localiser.hosts import HOSTS

from . import model
from .icons import COLOURS, brand_icon, level_icon, rocket_icon

STATE_LEVEL = {
    "current": model.LEVEL_OK,
    "update_available": model.LEVEL_UPDATE,
    "not_prepared": model.LEVEL_UPDATE,
    "offline": model.LEVEL_PROBLEM,
    "error": model.LEVEL_PROBLEM,
    "unsupported": model.LEVEL_IDLE,
}
COLUMNS = ("Application", "Version", "Installed", "Studio release", "Status", "")
OVERRIDE_COLOUR = "#f0a030"  # a row whose host launches from a cloned bundle instead of the studio release


def location_text(location) -> str:
    return getattr(location, "location", None) or str(location)


class StatusPage(QWidget):
    checkRequested = Signal()
    syncRequested = Signal()
    launchRequested = Signal(str, str)  # host, series
    overrideRequested = Signal(str, str, object)  # host, series, the clone tag to launch from, or None to clear

    def __init__(self):
        super().__init__()
        self.entries, self.checked_at = [], None
        self.overrides, self.clones = {}, {}  # "host/series" -> tag; host -> tags
        self.launch_buttons, self.override_buttons, self.override_boxes = {}, {}, {}
        self.summary = QLabel()
        self.summary.setStyleSheet("font-size: 15px; font-weight: bold;")
        self.checked = QLabel()
        self.table = QTableWidget(0, len(COLUMNS))
        self.table.setHorizontalHeaderLabels(COLUMNS)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.table.verticalHeader().setVisible(False)
        self.table.setIconSize(QSize(24, 24))
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(len(COLUMNS) - 2, QHeaderView.ResizeMode.Stretch)
        self.check = QPushButton("Check now")
        self.sync = QPushButton("Update now")
        self.check.clicked.connect(self.checkRequested)
        self.sync.clicked.connect(self.syncRequested)
        buttons = QHBoxLayout()
        buttons.addWidget(self.checked, 1)
        buttons.addWidget(self.check)
        buttons.addWidget(self.sync)
        layout = QVBoxLayout(self)
        layout.addWidget(self.summary)
        layout.addWidget(self.table, 1)
        layout.addLayout(buttons)

    def show_entries(self, entries, checked_at: datetime | None, overrides=None, clones=None):
        """Show one row per entry. `overrides` maps "host/series" to the clone it launches from; `clones` maps a
        host to the clone tags it can choose from."""
        self.entries, self.checked_at = list(entries), checked_at
        self.overrides, self.clones = dict(overrides or {}), dict(clones or {})
        self.refresh()

    def refresh(self):
        entries = self.entries
        level, text = model.overall(entries)
        self.summary.setText(text)
        self.summary.setStyleSheet(f"font-size: 15px; font-weight: bold; color: {COLOURS[level]};")
        self.checked.setText(
            f"Last checked {self.checked_at.astimezone():%d %b %Y %H:%M}" if self.checked_at else "Not checked yet"
        )
        self.launch_buttons, self.override_buttons, self.override_boxes = {}, {}, {}
        self.table.setRowCount(len(entries))
        for row, entry in enumerate(entries):
            key = (entry.host, entry.series)
            override = self.overrides.get(f"{entry.host}/{entry.series}")
            tags = list(self.clones.get(entry.host, ()))
            info = HOSTS.get(entry.host)
            name = QTableWidgetItem(model.display_name(entry.host))
            if info and info.icon:
                name.setIcon(QIcon(str(info.icon)))
            status = QTableWidgetItem(f"Override: {override}" if override else model.describe(entry))
            status.setIcon(level_icon(STATE_LEVEL.get(entry.state, model.LEVEL_IDLE), badge=False))
            if entry.message and entry.state in ("error", "offline"):
                status.setToolTip(entry.message)
            cells = (name, QTableWidgetItem(entry.series), QTableWidgetItem(entry.selected or "-"),
                     QTableWidgetItem(entry.target or "-"), status)
            for column, item in enumerate(cells):
                if override:
                    item.setBackground(QBrush(QColor(OVERRIDE_COLOUR)))
                    item.setForeground(QBrush(QColor("#1b1d21")))
                self.table.setItem(row, column, item)
            if override:
                self.table.setCellWidget(row, len(cells) - 1, self._override_picker(entry, override, tags))
            else:  # a drop-down left from when this row was overridden would cover the status text
                self.table.removeCellWidget(row, len(cells) - 1)
            self.table.setCellWidget(row, len(cells), self._actions(entry, override, tags))
        self.sync.setEnabled(bool(entries))

    def _tinted(self, widget: QWidget, overridden: bool):
        if overridden:
            widget.setObjectName("overridden")
            widget.setStyleSheet(f"QWidget#overridden {{ background-color: {OVERRIDE_COLOUR}; }}")
        return widget

    def _override_picker(self, entry, override: str, tags: list) -> QWidget:
        """The Status cell of an overridden row: a drop-down of the bundles cloned for this host."""
        cell = QWidget()
        layout = QHBoxLayout(cell)
        layout.setContentsMargins(4, 2, 4, 2)
        box = QComboBox()
        box.addItems(tags if override in tags else [override, *tags])
        box.setCurrentText(override)
        box.setToolTip("The cloned bundle this application launches from")
        box.activated.connect(
            lambda _=0, h=entry.host, s=entry.series, b=box: self.overrideRequested.emit(h, s, b.currentText())
        )
        layout.addWidget(box, 1)
        self.override_boxes[(entry.host, entry.series)] = box
        return self._tinted(cell, True)

    def _actions(self, entry, override, tags: list) -> QWidget:
        cell = QWidget()
        layout = QHBoxLayout(cell)
        layout.setContentsMargins(4, 2, 4, 2)
        toggle = QPushButton("Override")
        toggle.setCheckable(True)
        toggle.setChecked(bool(override))
        toggle.setEnabled(bool(tags) or bool(override))
        toggle.setToolTip(
            "Launch from a bundle cloned on the Release tab, instead of the studio release"
            if tags or override else "Nothing to override with yet: clone a bundle on the Release tab"
        )
        toggle.clicked.connect(
            lambda checked, h=entry.host, s=entry.series, t=tags: self.overrideRequested.emit(
                h, s, (t[0] if t else None) if checked else None
            )
        )
        rocket = QPushButton()
        rocket.setIcon(rocket_icon())
        rocket.setIconSize(QSize(20, 20))
        rocket.setToolTip(f"Launch {model.display_name(entry.host)} {entry.series} with the pipeline")
        rocket.clicked.connect(
            lambda _=False, h=entry.host, s=entry.series: self.launchRequested.emit(h, s)
        )
        layout.addWidget(toggle)
        layout.addWidget(rocket)
        self.override_buttons[(entry.host, entry.series)] = toggle
        self.launch_buttons[(entry.host, entry.series)] = rocket
        return self._tinted(cell, bool(override))

    def set_busy(self, busy: bool):
        self.check.setEnabled(not busy)
        self.sync.setEnabled(not busy and self.table.rowCount() > 0)
        if busy:
            self.checked.setText("Working...")


class ReleasePage(QWidget):
    """Clone a bundle into the dev folder, to edit and run in place. Nothing is published from here."""

    cloneRequested = Signal(dict)  # host, tag and either release or source (+ shared)

    def __init__(self):
        super().__init__()
        self.releases = {}  # host -> release ids to offer
        self.host = QComboBox()
        for name, info in HOSTS.items():
            self.host.addItem(info.display_name, name)
        self.from_release = QRadioButton("A published release")
        self.from_source = QRadioButton("A bundle source folder")
        self.from_release.setChecked(True)
        self.release = QComboBox()
        self.release.setEditable(True)
        self.source = QLineEdit()
        self.source.setPlaceholderText("e.g. structure/bundle_sources/nuke/2.0.0")
        self.shared = QLineEdit()
        self.shared.setPlaceholderText("Optional: folder of shared packages to merge in")
        self.tag = QLineEdit()
        self.tag.setPlaceholderText("e.g. 2.1.0-wip")
        self.result = QLabel()
        self.result.setWordWrap(True)
        self.open_folder = QPushButton("Open folder")
        self.open_folder.setVisible(False)
        self.clone = QPushButton("Clone bundle")
        self.folder = None

        source_box = QGroupBox("Clone from")
        form = QFormLayout(source_box)
        form.addRow(self.from_release, self.release)
        form.addRow(self.from_source, _with_browse(self.source, self))
        form.addRow("Shared packages", _with_browse(self.shared, self))
        details = QGroupBox("New bundle")
        form2 = QFormLayout(details)
        form2.addRow("Application", self.host)
        form2.addRow("Version tag", self.tag)
        note = QLabel("The clone is made in the dev folder of the local releases folder: dev/<application>/<version tag>. "
                      "Edit it there, then override an application with it on the Status tab.")
        note.setWordWrap(True)
        buttons = QHBoxLayout()
        buttons.addWidget(self.result, 1)
        buttons.addWidget(self.open_folder)
        buttons.addWidget(self.clone)
        layout = QVBoxLayout(self)
        layout.addWidget(details)
        layout.addWidget(source_box)
        layout.addWidget(note)
        layout.addStretch(1)
        layout.addLayout(buttons)

        self.host.currentIndexChanged.connect(self._fill_releases)
        for button in (self.from_release, self.from_source):
            button.toggled.connect(self._update_enabled)
        self.clone.clicked.connect(self._emit_clone)
        self.open_folder.clicked.connect(self._open_folder)
        self._update_enabled()

    def set_releases(self, releases: dict):
        self.releases = {host: list(ids) for host, ids in releases.items()}
        self._fill_releases()

    def _fill_releases(self):
        current = self.release.currentText()
        self.release.clear()
        self.release.addItems(self.releases.get(self.host.currentData(), []))
        self.release.setEditText(current if current else (self.release.itemText(0) if self.release.count() else ""))

    def _update_enabled(self):
        release = self.from_release.isChecked()
        self.release.setEnabled(release)
        self.source.setEnabled(not release)
        self.shared.setEnabled(not release)

    def request(self) -> dict:
        request = {"host": self.host.currentData(), "tag": self.tag.text().strip()}
        if self.from_release.isChecked():
            request["release"] = self.release.currentText().strip()
        else:
            request["source"] = self.source.text().strip()
            request["shared"] = [p for p in (self.shared.text().strip(),) if p]
        return request

    def _emit_clone(self):
        self.cloneRequested.emit(self.request())

    def set_busy(self, busy: bool):
        self.clone.setEnabled(not busy)
        if busy:
            self.result.setStyleSheet("")
            self.result.setText("Cloning...")
            self.open_folder.setVisible(False)

    def show_result(self, ok: bool, text: str, folder=None):
        self.result.setStyleSheet("" if ok else "color: #d64545;")
        self.result.setText(text)
        self.folder = folder if ok else None
        self.open_folder.setVisible(bool(self.folder))

    def _open_folder(self):
        if self.folder:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.folder)))


def _with_browse(edit: QLineEdit, parent: QWidget) -> QWidget:
    row = QWidget()
    layout = QHBoxLayout(row)
    layout.setContentsMargins(0, 0, 0, 0)
    browse = QPushButton("Browse...")

    def choose():
        chosen = QFileDialog.getExistingDirectory(parent, "Choose a folder", edit.text() or str(Path.home()))
        if chosen:
            edit.setText(str(Path(chosen)))

    browse.clicked.connect(choose)
    layout.addWidget(edit, 1)
    layout.addWidget(browse)
    return row


class SettingsPage(QWidget):
    saveRequested = Signal(dict, dict)  # hosts enabled, other settings

    def __init__(self):
        super().__init__()
        self.series_boxes = {}  # (host, series) -> QCheckBox
        self.hosts_layout = QVBoxLayout()
        hosts = QGroupBox("Applications to keep up to date")
        hosts.setLayout(self.hosts_layout)

        self.remote = QLineEdit()
        self.remote.setPlaceholderText("A shared folder, or an https address")
        self.bundles = QLineEdit()
        self.bundles.setToolTip("Where downloaded releases are kept on this computer. Existing releases are not moved.")
        self.interval = QSpinBox()
        self.interval.setRange(MIN_CHECK_INTERVAL_MINUTES, MAX_CHECK_INTERVAL_MINUTES)
        self.interval.setSuffix(" minutes")
        self.auto_sync = QCheckBox("Install updates automatically (applications pick them up when next started)")
        self.warning = QLabel()
        self.warning.setWordWrap(True)
        self.warning.setStyleSheet("color: #d64545;")

        locations = QGroupBox("Locations and updates")
        form = QFormLayout(locations)
        form.addRow("Pipeline repository", self._with_browse(self.remote))
        self.remote_browse = self.remote.parentWidget().findChild(QPushButton)
        self.remote_note = QLabel(f"Controlled by your organisation ({REPOSITORY_VARIABLE}); it can't be changed here.")
        self.remote_note.setStyleSheet("color: #e08a1e;")
        self.remote_note.setVisible(False)
        form.addRow("", self.remote_note)
        form.addRow("Local releases folder", self._with_browse(self.bundles))
        form.addRow("Check every", self.interval)
        form.addRow("", self.auto_sync)

        self.save = QPushButton("Save")
        self.revert = QPushButton("Revert")
        self.save.clicked.connect(self._emit_save)
        buttons = QHBoxLayout()
        buttons.addStretch(1)
        buttons.addWidget(self.revert)
        buttons.addWidget(self.save)
        layout = QVBoxLayout(self)
        layout.addWidget(self.warning)
        layout.addWidget(hosts)
        layout.addWidget(locations)
        layout.addStretch(1)
        layout.addLayout(buttons)

    def _with_browse(self, edit: QLineEdit) -> QWidget:
        return _with_browse(edit, self)

    def load(self, config, choices, warning: str = ""):
        """Fill the form from the saved config and the versions found on this computer."""
        while self.hosts_layout.count():
            item = self.hosts_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.series_boxes = {}
        for choice in choices:
            row = QWidget()
            layout = QHBoxLayout(row)
            layout.setContentsMargins(0, 0, 0, 0)
            icon_label = QLabel()  # always present, so hosts without an icon still line up
            icon_label.setFixedWidth(32)
            if choice.icon:
                icon_label.setPixmap(QIcon(str(choice.icon)).pixmap(24, 24))
            layout.addWidget(icon_label)
            name = QLabel(choice.display_name)
            name.setMinimumWidth(80)
            layout.addWidget(name)
            if not choice.series:
                layout.addWidget(QLabel("not found on this computer"))
            for series, installed, enabled in choice.series:
                box = QCheckBox(series if installed else f"{series} (not installed)")
                box.setChecked(enabled)
                self.series_boxes[(choice.host, series)] = box
                layout.addWidget(box)
            layout.addStretch(1)
            self.hosts_layout.addWidget(row)
        self.remote.setText(location_text(config.remote_repository) if config else "")
        locked = bool(config and config.remote_locked)
        self.remote.setReadOnly(locked)
        self.remote_browse.setEnabled(not locked)
        self.remote_note.setVisible(locked)
        self.bundles.setText(str(config.bundle_repository) if config else "")
        self.interval.setValue(config.check_interval_minutes if config else 240)
        self.auto_sync.setChecked(config.auto_sync if config else True)
        self.warning.setText(warning)
        self.warning.setVisible(bool(warning))

    def values(self) -> tuple[dict, dict]:
        hosts = {}
        for (host, series), box in self.series_boxes.items():
            if box.isChecked():
                hosts.setdefault(host, []).append(series)
        other = {
            "check_interval_minutes": self.interval.value(),
            "auto_sync": self.auto_sync.isChecked(),
        }
        if not self.remote.isReadOnly():
            other["remote_repository"] = self.remote.text().strip()
        if self.bundles.text().strip():
            other["bundle_repository"] = self.bundles.text().strip()
        return hosts, other

    def _emit_save(self):
        self.saveRequested.emit(*self.values())


class MainWindow(QMainWindow):
    """The pipeline manager. Closing it hides it: the app keeps running in the tray."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("THE LINE Pipeline")
        self.setWindowIcon(brand_icon())
        self.resize(760, 520)
        self.status = StatusPage()
        self.release = ReleasePage()
        self.settings = SettingsPage()
        self.tabs = QTabWidget()
        self.tabs.addTab(self.status, "Status")
        self.tabs.addTab(self.release, "Release")
        self.tabs.addTab(self.settings, "Settings")
        self.setCentralWidget(self.tabs)
        self.progress = QProgressBar()
        self.progress.setMaximumWidth(260)
        self.progress.setTextVisible(True)
        self.progress.setVisible(False)
        self.statusBar().addPermanentWidget(self.progress)
        self.settings.revert.clicked.connect(self.revert_requested)
        self._reload = None

    def on_revert(self, callback):
        self._reload = callback

    def revert_requested(self):
        if self._reload:
            self._reload()

    def show_progress(self, label: str, done: int = 0, total: int = 0):
        """A bar while something runs: counting when `total` is known, otherwise a busy indicator."""
        self.progress.setVisible(True)
        self.progress.setRange(0, total)  # 0, 0 is the busy indicator
        self.progress.setValue(min(done, total) if total else 0)
        self.progress.setFormat(label.replace("%", "%%") if total else "")
        self.statusBar().showMessage(label)

    def hide_progress(self):
        self.progress.setVisible(False)
        self.statusBar().clearMessage()

    def show_error(self, title: str, text: str):
        QMessageBox.warning(self, title, text)

    def show_settings(self):
        self.tabs.setCurrentWidget(self.settings)
        self.bring_to_front()

    def bring_to_front(self):
        self.show()
        self.raise_()
        self.activateWindow()

    def closeEvent(self, event):
        event.ignore()
        self.hide()
