
"""
:module: smeardeform.ui

Smeardeform creation user interface

:author: Jerome Drese
"""

# imports
import os
import random
from maya import cmds
from maya import OpenMayaUI
from maya.app.general.mayaMixin import MayaQWidgetDockableMixin
from PySide2 import QtWidgets
from PySide2 import QtGui
from shiboken2 import wrapInstance
from PySide2 import QtCore
from anim.smeardeform.deformer import delete_smear_deformer
from anim.smeardeform.deformer import reset_smear_deformer_points
from anim.smeardeform.deformer import setup_smear_deformer
from anim.smeardeform.deformer import get_scene_cameras
from anim.smeardeform.deformer import key_points

# UI WIDGET NAME
UI_NAME = "smear_deformer_qdialog"


class SmearDeformeUI(MayaQWidgetDockableMixin, QtWidgets.QDialog):
    """ SmearDeformer User Interface class object
    """

    def __init__(self, parent=None):
        super(SmearDeformeUI, self).__init__(parent=parent)

        # checks for previous ui instances
        kill_ui("{}WorkspaceControl".format(UI_NAME))
        kill_ui(UI_NAME)

        # sets title and object name
        self.setWindowTitle("Smear Deformer")
        self.setObjectName(UI_NAME)

        # creates main layout widget
        self.main_layout = QtWidgets.QVBoxLayout(self)
        self.main_layout.setMargin(2)
        self.main_layout.setSpacing(6)
        self.main_layout.setAlignment(QtCore.Qt.AlignTop)

        # declares resource path
        self.resource_path = self.__get_resource_path()

        # creates ui widgets
        self._create_widgets()

        # connects signals
        self._connect_signals()

    @staticmethod
    def __get_resource_path():
        """ Returns the relative path to the resource folder
        """

        file_dir = os.path.dirname(__file__)

        if "\\" in file_dir:
            file_dir = file_dir.replace("\\", "/")

        return "{}/resources".format(file_dir)

    def _connect_signals(self):
        """ Connects widget signals to functionalities
        """

        # create
        self.create_button.clicked.connect(self._launch_smear_creation)

        # reset
        self.reset_button.clicked.connect(reset_smear_deformer_points)

        # key
        self.key_button.clicked.connect(key_points)

        # delete
        self.delete_button.clicked.connect(delete_smear_deformer)

        # modes
        self.object_mode_radial.clicked.connect(self._toggle_mode)
        self.camera_mode_radial.clicked.connect(self._toggle_mode)

    def _create_widgets(self):
        """ Creates the widget elements the user will interact with
        """

        # creates full frame border
        frame = QtWidgets.QFrame()
        frame.setFrameStyle(6)
        frame_layout = QtWidgets.QVBoxLayout(frame)
        frame_layout.setMargin(3)
        frame_layout.setSpacing(8)

        # creates settings frame border and layout
        settings_frame = QtWidgets.QFrame()
        settings_frame.setFrameStyle(6)
        settings_layout = QtWidgets.QGridLayout(settings_frame)
        settings_layout.setMargin(4)
        settings_layout.setSpacing(4)

        # settings labels
        custom_font = QtGui.QFont()
        custom_font.setBold(True)
        settings_label = QtWidgets.QLabel("-- Settings --")
        settings_label.setFont(custom_font)
        mode_label = QtWidgets.QLabel("Mode:")
        self.object_mode_radial = QtWidgets.QRadioButton("Object space")
        self.object_mode_radial.setChecked(True)
        self.camera_mode_radial = QtWidgets.QRadioButton("Camera space")
        self.camera_list = QtWidgets.QComboBox()
        self.camera_list.setEnabled(False)

        # x resolution
        pixmap = QtGui.QPixmap("{}/x_res.png".format(self.resource_path))
        x_res = QtWidgets.QLabel()
        x_res.setPixmap(pixmap)
        x_res.setMaximumWidth(32)
        self.x_rex_box = QtWidgets.QSpinBox()
        self.x_rex_box.setValue(3)
        self.x_rex_box.setMinimum(2)
        self.x_rex_box.setMaximumWidth(40)

        # y resolution
        pixmap = QtGui.QPixmap("{}/y_res.png".format(self.resource_path))
        y_res = QtWidgets.QLabel()
        y_res.setPixmap(pixmap)
        y_res.setMaximumWidth(32)
        self.y_rex_box = QtWidgets.QSpinBox()
        self.y_rex_box.setValue(3)
        self.y_rex_box.setMinimum(2)
        self.y_rex_box.setMaximumWidth(40)

        # z resolution
        pixmap = QtGui.QPixmap("{}/z_res.png".format(self.resource_path))
        self.z_res = QtWidgets.QLabel()
        self.z_res.setPixmap(pixmap)
        self.z_res.setMaximumWidth(32)
        self.z_rex_box = QtWidgets.QSpinBox()
        self.z_rex_box.setValue(3)
        self.z_rex_box.setMinimum(2)
        self.z_rex_box.setMaximumWidth(40)

        # extras
        extras_frame = QtWidgets.QFrame()
        extras_layout = QtWidgets.QGridLayout(extras_frame)
        extras_layout.setAlignment(QtCore.Qt.AlignCenter)
        extras_layout.setMargin(0)
        autokey_label = QtWidgets.QLabel("Auto keyframe smear on frame")
        self.autokey_box = QtWidgets.QCheckBox()
        self.autokey_box.setChecked(True)
        hidden_label = QtWidgets.QLabel("Ignore hidden shapes")
        self.hidden_box = QtWidgets.QCheckBox()
        self.hidden_box.setChecked(False)
        follow_cam_label = QtWidgets.QLabel("Follow camera")
        self.follow_box = QtWidgets.QCheckBox()
        self.follow_box.setChecked(True)
        self.follow_box.setDisabled(True)
        extras_layout.addWidget(self.autokey_box, 0, 0, 1, 1)
        extras_layout.addWidget(autokey_label, 0, 1, 1, 1)
        extras_layout.addWidget(self.hidden_box, 1, 0, 1, 1)
        extras_layout.addWidget(hidden_label, 1, 1, 1, 1)
        extras_layout.addWidget(self.follow_box, 2, 0, 1, 1)
        extras_layout.addWidget(follow_cam_label, 2, 1, 1, 1)

        # create
        style = ("QPushButton{"
                 "font: bold 14px;"
                 "color: rgb(220, 250, 250);"
                 "height: 25px;"
                 "background-color: rgb(85, 160, 20);"
                 "border:1px solid black;"
                 "border-radius:4px;}"
                 "QPushButton:pressed{"
                 "background-color: rgb(250, 140, 160);"
                 "}"
                 )
        self.create_button = QtWidgets.QPushButton("-- CREATE SMEAR --")
        self.create_button.setStyleSheet(style)

        # edit frame border and layout
        edit_frame = QtWidgets.QFrame()
        edit_frame.setFrameStyle(6)
        edit_layout = QtWidgets.QVBoxLayout(edit_frame)
        edit_layout.setMargin(4)
        edit_layout.setSpacing(4)

        # edit label
        edit_label = QtWidgets.QLabel("-- Edit --")
        edit_label.setFont(custom_font)

        # reset
        style = ("QPushButton{"
                 "font: 10px;"
                 "color: rgb(220, 250, 250);"
                 "height: 22px;"
                 "background-color: rgb(200, 120, 40);"
                 "border:1px solid black;"
                 "border-radius:4px;}"
                 "}"
                 "QPushButton:pressed{"
                 "background-color: rgb(250, 140, 160);"
                 )
        self.reset_button = QtWidgets.QPushButton("RESET SMEAR POINTS")
        self.reset_button.setStyleSheet(style)

        # key
        style = ("QPushButton{"
                 "font: 10px;"
                 "color: rgb(220, 250, 250);"
                 "height: 18px;"
                 "background-color: rgb(20, 120, 120);"
                 "border:1px solid black;"
                 "border-radius:4px;}"
                 "}"
                 "QPushButton:pressed{"
                 "background-color: rgb(250, 140, 160);"
                 )
        self.key_button = QtWidgets.QPushButton("KEY POINTS")
        self.key_button.setStyleSheet(style)

        # delete
        style = ("QPushButton{"
                 "font: 10px;"
                 "color: rgb(220, 250, 250);"
                 "height: 18px;"
                 "background-color: rgb(250, 60, 80);"
                 "border:1px solid black;"
                 "border-radius:4px;}"
                 "}"
                 "QPushButton:pressed{"
                 "background-color: rgb(250, 140, 160);"
                 )
        self.delete_button = QtWidgets.QPushButton("DELETE SMEAR")
        self.delete_button.setStyleSheet(style)

        # add widgets to layouts
        self.main_layout.addWidget(frame)
        frame_layout.addWidget(settings_frame)
        frame_layout.addWidget(self.create_button)
        frame_layout.addWidget(edit_frame)
        settings_layout.addWidget(settings_label, 0, 0, 1, 5)
        settings_layout.addWidget(mode_label, 1, 0, 1, 1)
        settings_layout.addWidget(self.object_mode_radial, 1, 1, 1, 2)
        settings_layout.addWidget(self.camera_mode_radial, 1, 3, 1, 2)
        settings_layout.addWidget(self.camera_list, 2, 0, 1, 6)
        settings_layout.addWidget(x_res, 3, 0, 1, 1)
        settings_layout.addWidget(self.x_rex_box, 3, 1, 1, 1)
        settings_layout.addWidget(y_res, 3, 2, 1, 1)
        settings_layout.addWidget(self.y_rex_box, 3, 3, 1, 1)
        settings_layout.addWidget(self.z_res, 3, 4, 1, 1)
        settings_layout.addWidget(self.z_rex_box, 3, 5, 1, 1)
        settings_layout.addWidget(extras_frame, 4, 0, 1, 6)
        edit_layout.addWidget(edit_label)
        edit_layout.addWidget(self.reset_button)
        edit_layout.addWidget(self.key_button)
        edit_layout.addWidget(self.delete_button)

    def _launch_smear_creation(self):
        """ Triggers Smear setup creation
        """

        # gets values
        resolution = [self.x_rex_box.value(),
                      self.y_rex_box.value(),
                      self.z_rex_box.value()]
        random_color = [random.random(), random.random(), random.random()]
        auto_key = self.autokey_box.isChecked()
        hidden = self.hidden_box.isChecked()
        camera = self.camera_list.currentText()
        follow = self.follow_box.isChecked()

        # launch process
        if self.object_mode_radial.isChecked():
            setup_smear_deformer(space="object",
                                 resolution=resolution,
                                 ignore_hidden=hidden,
                                 color=random_color,
                                 autokey=auto_key)
        else:
            setup_smear_deformer(space="camera",
                                 resolution=resolution,
                                 ignore_hidden=hidden,
                                 color=random_color,
                                 autokey=auto_key,
                                 camera=camera,
                                 follow=follow)

    def _toggle_mode(self):
        """ Handles UI modes display
        """

        if self.camera_mode_radial.isChecked():
            self.z_rex_box.setDisabled(True)
            self.z_res.setDisabled(True)
            self.follow_box.setEnabled(True)
            self.camera_list.setEnabled(True)
            self.camera_list.clear()
            self.camera_list.addItems(get_scene_cameras())
        else:
            self.z_rex_box.setEnabled(True)
            self.z_res.setEnabled(True)
            self.camera_list.setDisabled(True)
            self.camera_list.clear()
            self.follow_box.setDisabled(True)


def kill_ui(name):
    """ Deletes an already created widget

    Args:
        name (str): the widget object name
    """

    # finds workspace control if dockable widget
    if cmds.workspaceControl(name, exists=True):
        cmds.workspaceControl(name, edit=True, clp=False)
        cmds.deleteUI(name)

    # finds the widget
    widget = OpenMayaUI.MQtUtil.findWindow(name)

    if not widget:
        return

    # wraps the widget into a qt object
    qt_object = wrapInstance(long(widget), QtWidgets.QDialog)

    # sets the widget parent to none
    qt_object.setParent(None)

    # deletes the widget
    qt_object.deleteLater()
    del(qt_object)


def run(*args):  # @unusedVariable
    """ Opens the Cache Manager UI
    """

    tool = SmearDeformeUI()
    tool.show(dockable=True)
