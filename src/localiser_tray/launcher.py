"""The launcher: THE LINE logo and one button per application. It starts things and changes nothing."""
from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QHBoxLayout, QLabel, QToolButton, QVBoxLayout, QWidget

from localiser.hosts import HOSTS

from . import model
from .icons import brand_icon, level_icon, logo_pixmap

BUTTON_SIZE = 72
STYLE = """
QWidget#launcher { background: #262626; }
QLabel { color: #d8dce2; }
QToolButton { background: transparent; border: 1px solid transparent; border-radius: 6px; padding: 6px; }
QToolButton:hover { background: #343434; border-color: #4a4a4a; }
QToolButton:pressed { background: #3f3f3f; }
"""


class LauncherWindow(QWidget):
    """Closing it hides it: the app keeps running in the tray."""

    launchRequested = Signal(str, str)  # host, series

    def __init__(self):
        super().__init__()
        self.setObjectName("launcher")
        self.setWindowTitle("THE LINE Launcher")
        self.setWindowIcon(brand_icon())
        self.setStyleSheet(STYLE)
        self.buttons = {}  # (host, series) -> QToolButton
        logo = logo_pixmap(220)
        self.logo = QLabel()
        self.logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        if logo is not None:
            self.logo.setPixmap(logo)
        else:
            self.logo.setText("THE LINE")
            self.logo.setStyleSheet("font-size: 28px; font-weight: bold;")
        self.empty = QLabel("No applications are enabled.\nChoose them under Settings.")
        self.empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.row = QHBoxLayout()
        self.row.setSpacing(8)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(18)
        layout.addWidget(self.logo)
        layout.addLayout(self.row)
        layout.addWidget(self.empty)
        self.show_choices([])

    def show_choices(self, choices):
        """One button for each (host, series) given; clicking it asks for that application to be launched."""
        while self.row.count():
            item = self.row.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.buttons = {}
        for host, series in choices:
            info = HOSTS.get(host)
            button = QToolButton()
            button.setIcon(QIcon(str(info.icon)) if info and info.icon else level_icon(model.LEVEL_IDLE))
            button.setIconSize(QSize(BUTTON_SIZE, BUTTON_SIZE))
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setToolTip(f"Launch {model.display_name(host)} {series}")
            button.setAutoRaise(True)
            button.clicked.connect(lambda _=False, h=host, s=series: self.launchRequested.emit(h, s))
            self.row.addWidget(button)
            self.buttons[(host, series)] = button
        self.empty.setVisible(not choices)
        self.adjustSize()

    def closeEvent(self, event):
        event.ignore()
        self.hide()

    def bring_to_front(self):
        self.show()
        self.raise_()
        self.activateWindow()
