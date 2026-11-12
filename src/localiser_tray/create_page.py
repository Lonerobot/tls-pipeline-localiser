"""The Create tab: make a local bundle to develop with, or publish a bundle as a new studio release."""
from PySide6.QtCore import Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

from localiser.hosts import HOSTS

from .icons import mode_icon
from .widgets import with_browse

LOCAL, PUBLISH = "local", "publish"
BRAND = "#FF391E"

MODE_STYLE = """
QPushButton#mode {
    background-color: #2b2b2b; border: 1px solid #484848; border-left: 4px solid #484848; text-align: left;
}
QPushButton#mode:hover { background-color: #333333; }
QPushButton#mode:checked { border-color: %(brand)s; background-color: #33302f; }
QLabel { background: transparent; border: none; }
QLabel#modeTitle { color: #ffffff; font-size: 13px; font-weight: 600; }
QLabel#modeInfo { color: #c8c8c8; font-size: 12px; }
""" % {"brand": BRAND}


class ModeButton(QPushButton):
    """A big check button: an icon on the left, a title and a line of smaller text, like the popups."""

    def __init__(self, kind: str, title: str, info: str):
        super().__init__()
        self.setObjectName("mode")
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(78)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 12, 16, 12)
        layout.setSpacing(14)
        icon = QLabel()
        icon.setFixedSize(48, 48)
        icon.setPixmap(mode_icon(kind).pixmap(48, 48))
        text = QVBoxLayout()
        text.setSpacing(3)
        self.title_label = QLabel(title)
        self.title_label.setObjectName("modeTitle")
        self.title_label.setWordWrap(True)
        self.info_label = QLabel(info)
        self.info_label.setObjectName("modeInfo")
        self.info_label.setWordWrap(True)
        text.addStretch(1)
        text.addWidget(self.title_label)
        text.addWidget(self.info_label)
        text.addStretch(1)
        layout.addWidget(icon)
        layout.addLayout(text, 1)
        for child in (icon, self.title_label, self.info_label):
            child.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)


class CreatePage(QWidget):
    """What do you want to create? Either a local bundle in the dev folder, to edit and run in place, or a new
    release published to the studio repository from a dev bundle or a source folder."""

    createRequested = Signal(dict)  # host, tag and either release or source (+ shared)
    publishRequested = Signal(dict)  # host, version and either bundle or source (+ shared)
    hostChanged = Signal(str)  # the application chosen: the releases offered need refreshing

    def __init__(self):
        super().__init__()
        self.setStyleSheet(MODE_STYLE)
        self.releases = {}  # host -> ReleaseChoices to offer
        self.bundles = {}  # host -> tags of the bundles in the dev folder
        self.folder = None
        self._version_edited = False

        self.mode_local = ModeButton(LOCAL, "A local pipeline bundle", "Use for developing new features")
        self.mode_publish = ModeButton(PUBLISH, "Publish new studio bundle", "Push a new release to the studio repository")
        group = QButtonGroup(self)
        group.setExclusive(True)
        group.addButton(self.mode_local)
        group.addButton(self.mode_publish)
        self.mode_local.setChecked(True)
        modes = QHBoxLayout()
        modes.setSpacing(10)
        modes.addWidget(self.mode_local, 1)
        modes.addWidget(self.mode_publish, 1)
        question = QLabel("What do you want to create?")
        question.setStyleSheet("font-size: 15px; font-weight: bold;")

        self.host = QComboBox()
        for name, info in HOSTS.items():
            self.host.addItem(info.display_name, name)
        application = QFormLayout()
        application.addRow("Application", self.host)

        self.local_panel = self._build_local()
        self.publish_panel = self._build_publish()

        self.result = QLabel()
        self.result.setWordWrap(True)
        self.open_folder = QPushButton("Open folder")
        self.open_folder.setVisible(False)
        self.create_button = QPushButton("Create bundle")
        self.publish_button = QPushButton("Publish bundle")
        buttons = QHBoxLayout()
        buttons.addWidget(self.result, 1)
        buttons.addWidget(self.open_folder)
        buttons.addWidget(self.create_button)
        buttons.addWidget(self.publish_button)

        layout = QVBoxLayout(self)
        layout.addWidget(question)
        layout.addLayout(modes)
        layout.addLayout(application)
        layout.addWidget(self.local_panel)
        layout.addWidget(self.publish_panel)
        layout.addStretch(1)
        layout.addLayout(buttons)

        self.host.currentIndexChanged.connect(self._on_host_changed)
        group.buttonToggled.connect(lambda *_: self._apply_mode())
        for button in (self.from_release, self.from_source, self.pub_from_bundle, self.pub_from_source):
            button.toggled.connect(self._update_enabled)
        self.bundle.currentIndexChanged.connect(self._bundle_chosen)
        self.version.textEdited.connect(lambda _: setattr(self, "_version_edited", True))
        self.create_button.clicked.connect(lambda: self.createRequested.emit(self.request()))
        self.publish_button.clicked.connect(lambda: self.publishRequested.emit(self.publish_request()))
        self.open_folder.clicked.connect(self._open_folder)
        self._apply_mode()

    # building ------------------------------------------------------------------------------------

    def _build_local(self) -> QWidget:
        self.from_release = QRadioButton("A published release")
        self.from_source = QRadioButton("A bundle source folder")
        self.from_release.setChecked(True)
        self.release = QComboBox()  # only releases that exist: nothing to mistype
        self.release.setMinimumContentsLength(28)
        self.source = QLineEdit()
        self.source.setPlaceholderText("e.g. structure/bundle_sources/nuke/2.0.0")
        self.shared = QLineEdit()
        self.shared.setPlaceholderText("Optional: folder of shared packages to merge in")
        self.tag = QLineEdit()
        self.tag.setPlaceholderText("e.g. 2.1.0-wip")

        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        details = QGroupBox("New bundle")
        QFormLayout(details).addRow("Version tag", self.tag)
        start = QGroupBox("Start from")
        form = QFormLayout(start)
        form.addRow(self.from_release, self.release)
        form.addRow(self.from_source, with_browse(self.source, self))
        form.addRow("Shared packages", with_browse(self.shared, self))
        note = QLabel("The new bundle is made in the dev folder of the local releases folder: dev/<application>/<version tag>. "
                      "Edit it there, then override an application with it on the Status tab.")
        note.setWordWrap(True)
        layout.addWidget(details)
        layout.addWidget(start)
        layout.addWidget(note)
        return panel

    def _build_publish(self) -> QWidget:
        self.pub_from_bundle = QRadioButton("A local development bundle")
        self.pub_from_source = QRadioButton("A bundle source folder")
        self.pub_from_bundle.setChecked(True)
        self.bundle = QComboBox()
        self.bundle.setMinimumContentsLength(28)
        self.pub_source = QLineEdit()
        self.pub_source.setPlaceholderText("A version that lives somewhere else, to publish from there")
        self.pub_shared = QLineEdit()
        self.pub_shared.setPlaceholderText("Usually empty")
        self.version = QLineEdit()
        self.version.setPlaceholderText("e.g. 2.1.0")

        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        details = QGroupBox("New studio release")
        form0 = QFormLayout(details)
        form0.addRow("Release version", self.version)
        what = QGroupBox("Publish from")
        form = QFormLayout(what)
        form.addRow(self.pub_from_bundle, self.bundle)
        form.addRow(self.pub_from_source, with_browse(self.pub_source, self))
        form.addRow("Shared packages", with_browse(self.pub_shared, self))
        shared_note = QLabel("Shared packages (such as logging) rarely change, so they are normally already inside the "
                             "bundle: a development bundle has them, and so does a copy of an earlier release. Add a folder "
                             "only to merge in newer ones.")
        shared_note.setWordWrap(True)
        warning = QLabel("A published release can't be changed or removed, and nobody uses it until the studio config's "
                         "bundle_version selects it.")
        warning.setWordWrap(True)
        layout.addWidget(details)
        layout.addWidget(what)
        layout.addWidget(shared_note)
        layout.addWidget(warning)
        return panel

    # mode ----------------------------------------------------------------------------------------

    @property
    def mode(self) -> str:
        return PUBLISH if self.mode_publish.isChecked() else LOCAL

    def _apply_mode(self):
        publishing = self.mode == PUBLISH
        self.local_panel.setVisible(not publishing)
        self.publish_panel.setVisible(publishing)
        self.create_button.setVisible(not publishing)
        self.publish_button.setVisible(publishing)
        self.show_result(True, "")
        self._update_enabled()

    def _update_enabled(self):
        release = self.from_release.isChecked()
        self.release.setEnabled(release and self.release.count() > 0)
        self.source.setEnabled(not release)
        self.shared.setEnabled(not release)
        bundle = self.pub_from_bundle.isChecked()
        self.bundle.setEnabled(bundle and self.bundle.count() > 0)
        self.pub_source.setEnabled(not bundle)
        self.pub_shared.setEnabled(not bundle)

    # releases and bundles on offer ------------------------------------------------------------------

    def set_host_releases(self, host: str, choices: list):
        """The `ReleaseChoice`s found for `host`. Redrawn only if that application is the one chosen."""
        self.releases[host] = list(choices)
        if self.host.currentData() == host:
            self._fill_releases(keep=True)

    def set_bundles(self, bundles: dict):
        """The tags of the bundles in the dev folder, by host."""
        self.bundles = {host: list(tags) for host, tags in bundles.items()}
        self._fill_bundles(keep=True)

    def _on_host_changed(self):
        self._fill_releases(keep=False)  # another application's release can't be used for this one
        self._version_edited = False
        self._fill_bundles(keep=False)
        self.hostChanged.emit(self.host.currentData())

    def _fill_releases(self, keep: bool = False):
        previous = self.release.currentData() if keep else None
        choices = self.releases.get(self.host.currentData(), [])
        self.release.clear()
        for choice in choices:
            note = f"  ·  studio default ({', '.join(choice.studio_series)})" if choice.studio_series else ""
            if not choice.installed:
                note += "  ·  downloaded when used"
            self.release.addItem(f"{choice.release_id}{note}", choice.release_id)
        wanted = next((i for i in range(self.release.count()) if self.release.itemData(i) == previous), None)
        if wanted is None:  # start on the studio default, the usual place to start from
            wanted = next((i for i, c in enumerate(choices) if c.studio_series), 0)
        if self.release.count():
            self.release.setCurrentIndex(wanted)
        self.release.setToolTip("" if choices else "No published releases were found for this application")
        self._update_enabled()

    def _fill_bundles(self, keep: bool = False):
        previous = self.bundle.currentData() if keep else None
        tags = self.bundles.get(self.host.currentData(), [])
        self.bundle.blockSignals(True)
        self.bundle.clear()
        for tag in tags:
            self.bundle.addItem(tag, tag)
        index = self.bundle.findData(previous) if previous else -1
        if self.bundle.count():
            self.bundle.setCurrentIndex(max(index, 0))
        self.bundle.blockSignals(False)
        self.bundle.setToolTip("" if tags else "No bundles have been made for this application yet: use the first choice above")
        self._bundle_chosen()
        self._update_enabled()

    def _bundle_chosen(self):
        """The release version follows the bundle's name until the user types a version of their own."""
        if not self._version_edited and self.bundle.currentData():
            self.version.setText(self.bundle.currentData())

    # requests ------------------------------------------------------------------------------------

    def request(self) -> dict:
        request = {"host": self.host.currentData(), "tag": self.tag.text().strip()}
        if self.from_release.isChecked():
            request["release"] = self.release.currentData() or ""
        else:
            request["source"] = self.source.text().strip()
            request["shared"] = [p for p in (self.shared.text().strip(),) if p]
        return request

    def publish_request(self) -> dict:
        request = {"host": self.host.currentData(), "version": self.version.text().strip()}
        if self.pub_from_bundle.isChecked():
            request["bundle"] = self.bundle.currentData() or ""
        else:
            request["source"] = self.pub_source.text().strip()
            request["shared"] = [p for p in (self.pub_shared.text().strip(),) if p]
        return request

    # results -------------------------------------------------------------------------------------

    def set_busy(self, busy: bool):
        self.create_button.setEnabled(not busy)
        self.publish_button.setEnabled(not busy)
        if busy:
            self.result.setStyleSheet("")
            self.result.setText("Publishing..." if self.mode == PUBLISH else "Creating...")
            self.open_folder.setVisible(False)

    def show_result(self, ok: bool, text: str, folder=None):
        self.result.setStyleSheet("" if ok else "color: #d64545;")
        self.result.setText(text)
        self.folder = folder if ok else None
        self.open_folder.setVisible(bool(self.folder))

    def _open_folder(self):
        if self.folder:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.folder)))
