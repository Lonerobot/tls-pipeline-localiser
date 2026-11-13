"""The pipeline manager window: what each application is running, and the settings behind it."""
from datetime import datetime

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QIcon
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QComboBox,
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
from .create_page import CreatePage
from .icons import COLOURS, admin_icon, brand_icon, level_icon, rocket_icon
from .widgets import open_folder_button, with_browse

STATE_LEVEL = {
    "current": model.LEVEL_OK,
    "update_available": model.LEVEL_UPDATE,
    "not_prepared": model.LEVEL_UPDATE,
    "no_bundle": model.LEVEL_UPDATE,
    "offline": model.LEVEL_PROBLEM,
    "error": model.LEVEL_PROBLEM,
    "unsupported": model.LEVEL_IDLE,
}
COLUMNS = ("Application", "Version", "Installed", "Studio release", "Status", "")
OVERRIDE_COLOUR = "#f0a030"  # a row whose host launches from a bundle made on the Create tab instead of the studio release


def location_text(location) -> str:
    return getattr(location, "location", None) or str(location)


class StatusPage(QWidget):
    checkRequested = Signal()
    syncRequested = Signal()
    launchRequested = Signal(str, str)  # host, series
    overrideRequested = Signal(str, str, object)  # host, series, the clone tag to launch from, or None to clear
    studioReleaseRequested = Signal(str, str, object)  # admin: host, series, the studio release, or None for none

    def __init__(self):
        super().__init__()
        self.entries, self.checked_at = [], None
        self.overrides, self.clones = {}, {}  # "host/series" -> tag; host -> tags
        self.launch_buttons, self.override_buttons, self.override_boxes = {}, {}, {}
        self.admin = False
        self.studio = {}  # (host, series) -> the studio config's bundle version, or None (admin)
        self.studio_editable = (True, "")  # whether the studio config can be written, and if not why (admin)
        self.release_choices = {}  # host -> the published releases to offer (admin)
        self.studio_boxes = {}
        self.summary = QLabel()
        self.summary.setStyleSheet("font-size: 15px; font-weight: bold;")
        self.admin_icon = QLabel()
        self.admin_icon.setPixmap(admin_icon().pixmap(22, 22))
        self.admin_label = QLabel("ADMIN MODE")
        self.admin_label.setStyleSheet(f"color: {OVERRIDE_COLOUR}; font-weight: bold;")
        self.admin_icon.setToolTip("Admin mode: the Studio release column changes what everyone gets")
        self.admin_icon.setVisible(False)
        self.admin_label.setVisible(False)
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
        heading = QHBoxLayout()
        heading.addWidget(self.summary, 1)
        heading.addWidget(self.admin_icon)
        heading.addWidget(self.admin_label)
        layout = QVBoxLayout(self)
        layout.addLayout(heading)
        layout.addWidget(self.table, 1)
        layout.addLayout(buttons)

    def set_admin(self, admin: bool):
        self.admin = admin
        self.admin_icon.setVisible(admin)
        self.admin_label.setVisible(admin)
        self.refresh()

    def set_studio_view(self, studio: dict, editable: tuple[bool, str]):
        """What admin mode needs: the studio config's entries, and whether it can be edited from here."""
        self.studio, self.studio_editable = dict(studio), editable
        if self.admin:
            self.refresh()

    def set_release_choices(self, host: str, choices: list):
        self.release_choices[host] = list(choices)
        if self.admin:
            self.refresh()

    def show_entries(self, entries, checked_at: datetime | None, overrides=None, clones=None):
        """Show one row per entry. `overrides` maps "host/series" to the clone it launches from; `clones` maps a
        host to the clone tags it can choose from."""
        self.entries, self.checked_at = list(entries), checked_at
        self.overrides, self.clones = dict(overrides or {}), dict(clones or {})
        self.refresh()

    def refresh(self):
        entries = self.entries
        rows = model.admin_rows(entries, self.studio) if self.admin else entries
        level, text = model.overall(entries)
        self.summary.setText(text)
        self.summary.setStyleSheet(f"font-size: 15px; font-weight: bold; color: {COLOURS[level]};")
        self.checked.setText(
            f"Last checked {self.checked_at.astimezone():%d %b %Y %H:%M}" if self.checked_at else "Not checked yet"
        )
        self.launch_buttons, self.override_buttons, self.override_boxes, self.studio_boxes = {}, {}, {}, {}
        self.table.setRowCount(len(rows))
        for row, entry in enumerate(rows):
            enabled_here = entry.state != model.NOT_ENABLED
            override = self.overrides.get(f"{entry.host}/{entry.series}") if enabled_here else None
            tags = list(self.clones.get(entry.host, ()))
            info = HOSTS.get(entry.host)
            name = QTableWidgetItem(model.display_name(entry.host))
            if info and info.icon:
                name.setIcon(QIcon(str(info.icon)))
            status = QTableWidgetItem(f"Override: {override}" if override else model.describe(entry))
            status.setIcon(level_icon(STATE_LEVEL.get(entry.state, model.LEVEL_IDLE), badge=False))
            if entry.message and entry.state in ("error", "offline"):
                status.setToolTip(entry.message)
            studio_text = "" if self.admin else (entry.target or ("(none)" if entry.state == model.NO_BUNDLE else "-"))
            cells = (name, QTableWidgetItem(entry.series), QTableWidgetItem(entry.selected or "-"),
                     QTableWidgetItem(studio_text), status)
            for column, item in enumerate(cells):
                if override:
                    item.setBackground(QBrush(QColor(OVERRIDE_COLOUR)))
                    item.setForeground(QBrush(QColor("#1b1d21")))
                self.table.setItem(row, column, item)
            # Drop-downs left from an earlier refresh would cover the text underneath, so each cell is set or cleared.
            if self.admin:
                self.table.setCellWidget(row, 3, self._studio_picker(entry))
            else:
                self.table.removeCellWidget(row, 3)
            if override:
                self.table.setCellWidget(row, len(cells) - 1, self._override_picker(entry, override, tags))
            else:
                self.table.removeCellWidget(row, len(cells) - 1)
            if enabled_here:
                self.table.setCellWidget(row, len(cells), self._actions(entry, override, tags))
            else:
                self.table.removeCellWidget(row, len(cells))
        self.sync.setEnabled(bool(entries))

    def _studio_picker(self, entry) -> QWidget:
        """Admin: the studio release of this row, as a drop-down of `(none)` and every published release."""
        key = (entry.host, entry.series)
        current = self.studio.get(key, entry.target)
        box = QComboBox()
        box.addItem("(none)", "")
        ids = [choice.release_id for choice in self.release_choices.get(entry.host, [])]
        for release in ids if current in (None, *ids) else [current, *ids]:
            box.addItem(release, release)
        box.setCurrentIndex(max(box.findData(current or ""), 0))
        editable, why = self.studio_editable
        box.setEnabled(editable)
        box.setToolTip(
            "The bundle everyone gets for this version: choosing another changes the studio config and syncs"
            if editable else f"The studio config can't be edited here: {why}"
        )
        box.activated.connect(
            lambda _=0, h=entry.host, s=entry.series, b=box: self.studioReleaseRequested.emit(h, s, b.currentData() or None)
        )
        self.studio_boxes[key] = box
        return box

    def _tinted(self, widget: QWidget, overridden: bool):
        if overridden:
            widget.setObjectName("overridden")
            widget.setStyleSheet(f"QWidget#overridden {{ background-color: {OVERRIDE_COLOUR}; }}")
        return widget

    def _override_picker(self, entry, override: str, tags: list) -> QWidget:
        """The Status cell of an overridden row: a drop-down of the bundles made for this host."""
        cell = QWidget()
        layout = QHBoxLayout(cell)
        layout.setContentsMargins(4, 2, 4, 2)
        box = QComboBox()
        box.addItems(tags if override in tags else [override, *tags])
        box.setCurrentText(override)
        box.setToolTip("The bundle, made on the Create tab, that this application launches from")
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
            "Launch from a bundle made on the Create tab, instead of the studio release"
            if tags or override else "Nothing to override with yet: create a bundle on the Create tab"
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


class SettingsPage(QWidget):
    saveRequested = Signal(dict, dict)  # hosts enabled, other settings

    def __init__(self):
        super().__init__()
        self.series_boxes = {}  # (host, series) -> QCheckBox
        self.hosts_layout = QVBoxLayout()
        self.hosts_group = QGroupBox("Applications to keep up to date")
        self.hosts_group.setLayout(self.hosts_layout)
        hosts = self.hosts_group

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
        self.version_label = QLabel(f"Application version: {QApplication.applicationVersion()}")
        self.version_label.setToolTip("Version of the running application, matching its installer release.")
        self.version_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.save.clicked.connect(self._emit_save)
        buttons = QHBoxLayout()
        buttons.addWidget(self.version_label)
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
        row = with_browse(edit, self)
        row.layout().addWidget(open_folder_button(edit, self))
        return row

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

    adminChanged = Signal(bool)

    TITLE = "THE LINE Pipeline"
    ADMIN_TITLE = "THE LINE Pipeline - ADMIN MODE"

    def __init__(self):
        super().__init__()
        self.admin = False
        self.setWindowTitle(self.TITLE)
        self.setWindowIcon(brand_icon())
        self.resize(760, 520)
        self.status = StatusPage()
        self.create = CreatePage()
        self.settings = SettingsPage()
        self.tabs = QTabWidget()
        self.tabs.addTab(self.status, "Status")
        self.tabs.addTab(self.create, "Create")
        self.tabs.addTab(self.settings, "Settings")
        self.setCentralWidget(self.tabs)
        self.progress = QProgressBar()
        self.progress.setMaximumWidth(260)
        self.progress.setTextVisible(True)
        self.progress.setVisible(False)
        self.statusBar().addPermanentWidget(self.progress)
        self.settings.revert.clicked.connect(self.revert_requested)
        self._reload = None
        self.tabs.setTabVisible(self.tabs.indexOf(self.create), False)  # Create is for admins only

    def set_admin(self, admin: bool):
        """Admin mode enables studio release changes and the Create tab until switched off or closed."""
        if admin == self.admin:
            return
        self.admin = admin
        self.setWindowTitle(self.ADMIN_TITLE if admin else self.TITLE)
        was_on_create = self.tabs.currentWidget() is self.create
        self.tabs.setTabVisible(self.tabs.indexOf(self.create), admin)
        if not admin and was_on_create:
            self.tabs.setCurrentWidget(self.status)
        self.status.set_admin(admin)
        self.adminChanged.emit(admin)

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

    def confirm(self, title: str, text: str) -> bool:
        return QMessageBox.question(self, title, text) == QMessageBox.StandardButton.Yes

    def show_settings(self):
        self.tabs.setCurrentWidget(self.settings)
        self.bring_to_front()

    def bring_to_front(self):
        self.show()
        self.raise_()
        self.activateWindow()

    def closeEvent(self, event):
        event.ignore()
        self.set_admin(False)  # admin mode never outlives the window
        self.hide()
