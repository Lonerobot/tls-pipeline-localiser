"""Popups that appear above the taskbar, in place of the system toast: an icon, a title and a line of text.

Used for "Launching Nuke 17.0" (with the application's own icon) and for the update messages. They never take
focus, stack upwards when there are several, stay while the pointer is over them, and go on a click.
"""
from PySide6.QtCore import QEasingCurve, QPropertyAnimation, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QCursor, QIcon, QPixmap
from PySide6.QtWidgets import QApplication, QHBoxLayout, QLabel, QVBoxLayout, QWidget

ICON_SIZE = 44
MARGIN = 20  # from the screen edge
GAP = 10  # between stacked popups
LINGER_MS = 1500  # how long a popup stays after the pointer leaves it
ACCENT = "#2e9e5b"
OVERRIDE_ACCENT = "#f0a030"

STYLE = """
QWidget#notification {
    background-color: #2b2b2b;
    border: 1px solid #484848;
    border-left: 4px solid %(accent)s;
}
QLabel { background: transparent; border: none; }
QLabel#title { color: #ffffff; font-size: 13px; font-weight: 600; }
QLabel#message { color: #c8c8c8; font-size: 12px; }
"""


def _pixmap(icon, size: int) -> QPixmap:
    """`icon` (a QIcon, QPixmap or a file path) as a pixmap no larger than `size`, or an empty one."""
    if isinstance(icon, QPixmap):
        pixmap = icon
    else:
        pixmap = (icon if isinstance(icon, QIcon) else QIcon(str(icon))).pixmap(QSize(size, size))
    if pixmap.isNull():
        return pixmap
    return pixmap.scaled(
        QSize(size, size), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
    )


class NotificationPopup(QWidget):
    closed = Signal(object)  # emitted once, with this popup, when it has gone

    def __init__(self, title: str, message: str = "", icon=None, duration: int = 4000, accent: str = ACCENT):
        super().__init__(
            None,
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.WindowDoesNotAcceptFocus,
        )
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)  # a flat, opaque rectangle: no transparency, which draws nothing on some Windows setups
        self.setObjectName("notification")
        self.setAutoFillBackground(True)
        self.setFixedWidth(340)
        self.setStyleSheet(STYLE % {"accent": accent})
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.duration = duration
        self._dismissing = False

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 12, 16, 12)
        layout.setSpacing(14)
        self.icon_label = QLabel()
        self.icon_label.setFixedSize(ICON_SIZE, ICON_SIZE)
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pixmap = _pixmap(icon, ICON_SIZE) if icon is not None else QPixmap()
        self.icon_label.setPixmap(pixmap)
        self.icon_label.setVisible(not pixmap.isNull())
        layout.addWidget(self.icon_label, 0, Qt.AlignmentFlag.AlignTop)

        text = QVBoxLayout()
        text.setSpacing(3)
        self.title_label = QLabel(title)
        self.title_label.setObjectName("title")
        self.title_label.setWordWrap(True)
        self.message_label = QLabel(message)
        self.message_label.setObjectName("message")
        self.message_label.setWordWrap(True)
        self.message_label.setVisible(bool(message))
        text.addWidget(self.title_label)
        text.addWidget(self.message_label)
        layout.addLayout(text, 1)

        self.setWindowOpacity(0.0)
        self.fade_in = self._fade(0.0, 1.0, 180, QEasingCurve.Type.OutCubic)
        self.fade_out = self._fade(1.0, 0.0, 280, QEasingCurve.Type.InCubic)
        self.fade_out.finished.connect(self.close)
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.dismiss)

    def _fade(self, start: float, end: float, ms: int, curve) -> QPropertyAnimation:
        animation = QPropertyAnimation(self, b"windowOpacity", self)
        animation.setDuration(ms)
        animation.setStartValue(start)
        animation.setEndValue(end)
        animation.setEasingCurve(curve)
        return animation

    def showEvent(self, event):
        super().showEvent(event)
        self.fade_in.start()
        if self.duration > 0:
            self.timer.start(self.duration)

    def dismiss(self):
        """Fade out and close. Safe to call more than once."""
        if self._dismissing:
            return
        self._dismissing = True
        self.timer.stop()
        self.fade_in.stop()
        self.fade_out.setStartValue(self.windowOpacity())
        self.fade_out.start()

    def enterEvent(self, event):
        if not self._dismissing:
            self.timer.stop()
        super().enterEvent(event)

    def leaveEvent(self, event):
        if not self._dismissing and self.duration > 0:
            self.timer.start(LINGER_MS)
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        self.dismiss()

    def closeEvent(self, event):
        super().closeEvent(event)
        self.closed.emit(self)
        self.deleteLater()


class NotificationManager:
    """Shows popups in the bottom right corner of the screen the pointer is on, newest at the bottom."""

    def __init__(self):
        self._popups: list[NotificationPopup] = []

    @property
    def popups(self) -> list:
        return list(self._popups)

    def show(self, title: str, message: str = "", icon=None, duration: int = 4000, accent: str = ACCENT):
        popup = NotificationPopup(title, message, icon, duration, accent)
        popup.closed.connect(self._remove)
        popup.adjustSize()
        self._popups.append(popup)
        self._arrange()
        popup.show()
        return popup

    def _remove(self, popup):
        if popup in self._popups:
            self._popups.remove(popup)
        self._arrange()

    def _arrange(self):
        screen = QApplication.screenAt(QCursor.pos()) or QApplication.primaryScreen()
        if screen is None:
            return
        area = screen.availableGeometry()
        y = area.bottom() + 1 - MARGIN
        for popup in reversed(self._popups):  # the newest is lowest, older ones move up
            y -= popup.height()
            popup.move(area.right() + 1 - MARGIN - popup.width(), y)
            y -= GAP
