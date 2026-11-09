"""The pipeline manager window: what each application is running, and the settings behind it."""
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from localiser.config import MAX_CHECK_INTERVAL_MINUTES, MIN_CHECK_INTERVAL_MINUTES
from localiser.hosts import HOSTS

from . import model
from .icons import COLOURS, level_icon

STATE_LEVEL = {
    "current": model.LEVEL_OK,
    "update_available": model.LEVEL_UPDATE,
    "not_prepared": model.LEVEL_UPDATE,
    "offline": model.LEVEL_PROBLEM,
    "error": model.LEVEL_PROBLEM,
    "unsupported": model.LEVEL_IDLE,
}
COLUMNS = ("Application", "Version", "Installed", "Studio release", "Status")


def location_text(location) -> str:
    return getattr(location, "location", None) or str(location)


class StatusPage(QWidget):
    checkRequested = Signal()
    syncRequested = Signal()

    def __init__(self):
        super().__init__()
        self.summary = QLabel()
        self.summary.setStyleSheet("font-size: 15px; font-weight: bold;")
        self.checked = QLabel()
        self.table = QTableWidget(0, len(COLUMNS))
        self.table.setHorizontalHeaderLabels(COLUMNS)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.table.verticalHeader().setVisible(False)
        self.table.setIconSize(QSize(20, 20))
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(len(COLUMNS) - 1, QHeaderView.ResizeMode.Stretch)
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

    def show_entries(self, entries, checked_at: datetime | None):
        level, text = model.overall(entries)
        self.summary.setText(text)
        self.summary.setStyleSheet(f"font-size: 15px; font-weight: bold; color: {COLOURS[level]};")
        self.checked.setText(f"Last checked {checked_at.astimezone():%d %b %Y %H:%M}" if checked_at else "Not checked yet")
        self.table.setRowCount(len(entries))
        for row, entry in enumerate(entries):
            info = HOSTS.get(entry.host)
            name = QTableWidgetItem(model.display_name(entry.host))
            if info and info.icon:
                name.setIcon(QIcon(str(info.icon)))
            status = QTableWidgetItem(model.describe(entry))
            status.setIcon(level_icon(STATE_LEVEL.get(entry.state, model.LEVEL_IDLE), badge=False))
            if entry.message and entry.state in ("error", "offline"):
                status.setToolTip(entry.message)
            cells = (name, QTableWidgetItem(entry.series), QTableWidgetItem(entry.selected or "-"),
                     QTableWidgetItem(entry.target or "-"), status)
            for column, item in enumerate(cells):
                self.table.setItem(row, column, item)
        self.sync.setEnabled(bool(entries))

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
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        browse = QPushButton("Browse...")
        browse.clicked.connect(lambda: self._browse(edit))
        layout.addWidget(edit, 1)
        layout.addWidget(browse)
        return row

    def _browse(self, edit: QLineEdit):
        chosen = QFileDialog.getExistingDirectory(self, "Choose a folder", edit.text() or str(Path.home()))
        if chosen:
            edit.setText(str(Path(chosen)))

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
            icon_label.setFixedWidth(20)
            if choice.icon:
                icon_label.setPixmap(QIcon(str(choice.icon)).pixmap(20, 20))
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
            "remote_repository": self.remote.text().strip(),
            "check_interval_minutes": self.interval.value(),
            "auto_sync": self.auto_sync.isChecked(),
        }
        if self.bundles.text().strip():
            other["bundle_repository"] = self.bundles.text().strip()
        return hosts, other

    def _emit_save(self):
        self.saveRequested.emit(*self.values())


class MainWindow(QMainWindow):
    """Closing it hides it: the app keeps running in the tray."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("THE LINE Pipeline")
        self.setWindowIcon(level_icon(model.LEVEL_OK))
        self.resize(760, 520)
        self.status = StatusPage()
        self.settings = SettingsPage()
        self.tabs = QTabWidget()
        self.tabs.addTab(self.status, "Status")
        self.tabs.addTab(self.settings, "Settings")
        self.setCentralWidget(self.tabs)
        self.settings.revert.clicked.connect(self.revert_requested)
        self._reload = None

    def on_revert(self, callback):
        self._reload = callback

    def revert_requested(self):
        if self._reload:
            self._reload()

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
