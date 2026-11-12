"""Small widgets shared by the manager's pages."""
from pathlib import Path

from PySide6.QtWidgets import QFileDialog, QHBoxLayout, QLineEdit, QPushButton, QWidget


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
