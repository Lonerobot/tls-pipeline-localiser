"""Small widgets shared by the manager's pages."""
from pathlib import Path

from PySide6.QtCore import QSize, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QFileDialog, QHBoxLayout, QLineEdit, QMessageBox, QPushButton, QToolButton, QWidget,
)

from .icons import folder_icon


def open_folder(path: str | Path, parent: QWidget):
    try:
        folder = Path(path).expanduser()
        if not folder.is_dir():
            raise NotADirectoryError(f"The folder does not exist or is not accessible:\n{folder}")
        if not QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder.absolute()))):
            raise OSError(f"The folder could not be opened:\n{folder}")
    except (OSError, RuntimeError) as exc:
        QMessageBox.warning(parent, "Cannot open folder", str(exc))


def open_folder_button(edit: QLineEdit, parent: QWidget) -> QToolButton:
    button = QToolButton()
    button.setIcon(folder_icon())
    button.setIconSize(QSize(20, 20))
    button.setAutoRaise(True)
    button.setAccessibleName("Open folder")
    button.clicked.connect(lambda: open_folder(edit.text().strip(), parent))

    def update():
        text = edit.text().strip()
        web = QUrl(text).scheme().lower() in ("http", "https")
        button.setEnabled(bool(text) and not web)
        button.setToolTip(
            "The repository is a web address, not a local or network folder" if web
            else "Open folder" if text else "Choose a folder first"
        )

    edit.textChanged.connect(update)
    update()
    return button


def with_browse(edit: QLineEdit, parent: QWidget) -> QWidget:
    """`edit` with a Browse button beside it that fills it with a chosen folder."""
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
