"""Tray and window icons, drawn in code so the app has no image assets of its own to ship."""
from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QFont, QIcon, QPainter, QPen, QPixmap

from .model import LEVEL_IDLE, LEVEL_OK, LEVEL_PROBLEM, LEVEL_UPDATE

COLOURS = {
    LEVEL_IDLE: "#7a7f87",
    LEVEL_OK: "#2e9e5b",
    LEVEL_UPDATE: "#e0a020",
    LEVEL_PROBLEM: "#d64545",
}


def _pixmap(colour: str, size: int, badge: bool) -> QPixmap:
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(QPen(QColor("#1b1d21"), max(1, size // 16)))
    painter.setBrush(QBrush(QColor(colour)))
    margin = size * 0.06
    painter.drawEllipse(QRectF(margin, margin, size - 2 * margin, size - 2 * margin))
    if badge:
        font = QFont()
        font.setBold(True)
        font.setPixelSize(int(size * 0.55))
        painter.setFont(font)
        painter.setPen(QColor("white"))
        painter.drawText(QRectF(0, 0, size, size), Qt.AlignmentFlag.AlignCenter, "L")
    painter.end()
    return pixmap


def level_icon(level: str, badge: bool = True) -> QIcon:
    """A round icon coloured by state; with the "L" badge for the tray and window, plain for list rows."""
    icon = QIcon()
    colour = COLOURS.get(level, COLOURS[LEVEL_IDLE])
    for size in (16, 24, 32, 48, 64):
        icon.addPixmap(_pixmap(colour, size, badge))
    return icon
