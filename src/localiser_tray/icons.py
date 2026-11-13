"""Tray and window icons, drawn in code so the app has no image assets of its own to ship."""
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QFont, QFontMetricsF, QIcon, QPainter, QPainterPath, QPen, QPixmap

from localiser.hosts import ICONS_DIR

from .model import LEVEL_IDLE, LEVEL_OK, LEVEL_PROBLEM, LEVEL_UPDATE

LOGO = ICONS_DIR / "TheLineLogo.svg"

COLOURS = {
    LEVEL_IDLE: "#7a7f87",
    LEVEL_OK: "#2e9e5b",
    LEVEL_UPDATE: "#e0a020",
    LEVEL_PROBLEM: "#d64545",
}


BRAND_BACKGROUND = "#FF391E"
BRAND_FOREGROUND = "#F8F8F8"


def _pixmap(colour: str, size: int, badge: bool, border: bool = True, text_colour: str = "white") -> QPixmap:
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(QPen(QColor("#1b1d21"), max(1, size // 16)) if border else Qt.PenStyle.NoPen)
    painter.setBrush(QBrush(QColor(colour)))
    margin = size * 0.06 if border else 0
    painter.drawEllipse(QRectF(margin, margin, size - 2 * margin, size - 2 * margin))
    if badge:
        font = QFont()
        font.setBold(True)
        font.setPixelSize(int(size * 0.5))
        painter.setFont(font)
        painter.setPen(QColor(text_colour))
        # Centre the letters themselves: the font's own box has room for descenders, which put them low.
        tight = QFontMetricsF(font).tightBoundingRect("TL")
        painter.drawText(
            QPointF((size - tight.width()) / 2 - tight.left(), size / 2 - (tight.top() + tight.height() / 2)), "TL"
        )
    painter.end()
    return pixmap


def level_icon(level: str, badge: bool = True) -> QIcon:
    """A round icon coloured by state; with the "TL" badge for the tray, plain for list rows."""
    icon = QIcon()
    colour = COLOURS.get(level, COLOURS[LEVEL_IDLE])
    for size in (16, 24, 32, 48, 64):
        icon.addPixmap(_pixmap(colour, size, badge))
    return icon


def brand_icon() -> QIcon:
    """The THE LINE badge in the brand colours, with no border, for windows and popups."""
    icon = QIcon()
    for size in (16, 24, 32, 48, 64, 128):
        icon.addPixmap(_pixmap(BRAND_BACKGROUND, size, True, border=False, text_colour=BRAND_FOREGROUND))
    return icon


def tray_icon(level: str) -> QIcon:
    """The brand badge with a dot in the corner coloured by state (grey nothing enabled, green current, amber
    updates waiting, red a problem), so the tray icon is the logo and still says how things are."""
    icon = QIcon()
    colour = QColor(COLOURS.get(level, COLOURS[LEVEL_IDLE]))
    for size in (16, 24, 32, 48, 64):
        pixmap = _pixmap(BRAND_BACKGROUND, size, True, border=False, text_colour=BRAND_FOREGROUND)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        radius = size * 0.24
        centre = size - radius - size * 0.02
        painter.setPen(QPen(QColor("#1b1d21"), max(1.0, size / 24)))  # a dark ring so the dot reads on the red
        painter.setBrush(QBrush(colour))
        painter.drawEllipse(QRectF(centre - radius, centre - radius, 2 * radius, 2 * radius))
        painter.end()
        icon.addPixmap(pixmap)
    return icon


def _rocket_pixmap(size: int, colour: str) -> QPixmap:
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.scale(size / 100, size / 100)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QBrush(QColor(colour)))
    body = QPainterPath()  # nose at the top right, flying up and to the right
    body.moveTo(50, 8)
    body.cubicTo(72, 22, 72, 52, 66, 70)
    body.lineTo(34, 70)
    body.cubicTo(28, 52, 28, 22, 50, 8)
    painter.drawPath(body)
    for sign in (-1, 1):  # the two fins
        fin = QPainterPath()
        fin.moveTo(50 + sign * 16, 52)
        fin.lineTo(50 + sign * 34, 78)
        fin.lineTo(50 + sign * 16, 70)
        painter.drawPath(fin)
    flame = QPainterPath()
    flame.moveTo(42, 76)
    flame.lineTo(50, 96)
    flame.lineTo(58, 76)
    painter.setBrush(QBrush(QColor("#f0a030")))
    painter.drawPath(flame)
    painter.setBrush(QBrush(QColor("#1b1d21")))
    painter.drawEllipse(QRectF(41, 30, 18, 18))  # the window
    painter.end()
    return pixmap


def rocket_icon(colour: str = "#d8dce2") -> QIcon:
    """A small rocket for the Launch buttons, drawn in code like the other icons."""
    icon = QIcon()
    for size in (16, 24, 32, 48):
        icon.addPixmap(_rocket_pixmap(size, colour))
    return icon


def _mode_pixmap(kind: str, size: int, colour: str) -> QPixmap:
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.scale(size / 100, size / 100)
    pen = QPen(QColor(colour), 7)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    painter.setPen(pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    if kind == "publish":  # an arrow rising out of a tray
        painter.drawLine(50, 62, 50, 14)
        painter.drawLine(30, 34, 50, 14)
        painter.drawLine(70, 34, 50, 14)
        tray = QPainterPath()
        tray.moveTo(14, 66)
        tray.lineTo(14, 86)
        tray.lineTo(86, 86)
        tray.lineTo(86, 66)
        painter.drawPath(tray)
    else:  # a folder, with code for the local-bundle choice
        folder = QPainterPath()
        folder.moveTo(10, 78)
        folder.lineTo(10, 24)
        folder.lineTo(36, 24)
        folder.lineTo(44, 34)
        folder.lineTo(90, 34)
        folder.lineTo(90, 78)
        folder.closeSubpath()
        painter.drawPath(folder)
        if kind != "folder":
            painter.drawLine(40, 50, 30, 58)
            painter.drawLine(30, 58, 40, 66)
            painter.drawLine(60, 50, 70, 58)
            painter.drawLine(70, 58, 60, 66)
    painter.end()
    return pixmap


def mode_icon(kind: str, colour: str = "#d8dce2") -> QIcon:
    """An outline icon for the Create tab's two choices: "local" (a folder of code) or "publish" (an arrow
    rising from a tray)."""
    icon = QIcon()
    for size in (24, 32, 48, 64, 96):
        icon.addPixmap(_mode_pixmap(kind, size, colour))
    return icon


def folder_icon(colour: str = "#d8dce2") -> QIcon:
    """A plain outline folder matching the Create tab's line icons."""
    icon = QIcon()
    for size in (16, 20, 24, 32, 48):
        icon.addPixmap(_mode_pixmap("folder", size, colour))
    return icon


def admin_icon(colour: str = "#f0a030") -> QIcon:
    """A shield with a key hole, for admin mode."""
    icon = QIcon()
    for size in (16, 24, 32, 48):
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.scale(size / 100, size / 100)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(QColor(colour)))
        shield = QPainterPath()
        shield.moveTo(50, 6)
        shield.lineTo(88, 20)
        shield.lineTo(88, 50)
        shield.cubicTo(88, 74, 70, 90, 50, 96)
        shield.cubicTo(30, 90, 12, 74, 12, 50)
        shield.lineTo(12, 20)
        shield.closeSubpath()
        painter.drawPath(shield)
        painter.setBrush(QBrush(QColor("#1b1d21")))
        painter.drawEllipse(QRectF(38, 30, 24, 24))  # the key hole: a round top and a stem
        painter.drawRect(QRectF(46, 48, 8, 24))
        painter.end()
        icon.addPixmap(pixmap)
    return icon


def logo_pixmap(width: int) -> QPixmap | None:
    """THE LINE logo rendered `width` pixels wide, or None if the SVG support isn't available."""
    try:
        from PySide6.QtSvg import QSvgRenderer
    except ImportError:
        return None
    renderer = QSvgRenderer(str(LOGO))
    if not renderer.isValid():
        return None
    size = renderer.defaultSize()
    height = max(1, round(width * size.height() / max(1, size.width())))
    pixmap = QPixmap(width, height)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.end()
    return pixmap
