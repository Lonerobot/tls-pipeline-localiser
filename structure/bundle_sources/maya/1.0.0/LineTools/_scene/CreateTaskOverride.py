import sys
import json
import os
import maya.OpenMayaUI as omui
from PySide2.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QSpinBox, QPushButton, QWidget, QSpacerItem, QSizePolicy, QFrame)

from PySide2.QtCore import Qt
from PySide2 import QtGui

from shiboken2 import wrapInstance
from maya import cmds

from pathlib import Path
from playblast_plus.lib import widgets, utils

def maya_main_window():
    """
    Return the Maya main window widget as a Python object
    """
    main_window_ptr = omui.MQtUtil.mainWindow()
    if sys.version_info.major >= 3:
        return wrapInstance(int(main_window_ptr), QWidget)
    else:
        return wrapInstance(long(main_window_ptr), QWidget)

class PreviewOverrideDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.setWindowTitle(" ")
        self.setWindowFlags(Qt.Tool)        
        self.setWindowTitle(" ")
        
        self.setFixedHeight(270)  # Set a fixed height for the dialog
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)  # Allow horizontal expansion only

        self.json_file = "_preview_override.json"
        self.data = {"Settings": {"render.resolution_x": 0, "render.resolution_y": 0},
                     "Preview": {"preview.resolution_x": 0, "preview.resolution_y": 0}}

        self.get_ayon_context()       
        
        if self.project_name:
            self._create_widgets()
            self._create_layouts()
            self._connect_signals()            
            self.load_json()
        else:
            pass
            # we don't have pype installed

    def get_ayon_context(self):
        from ayon_core.pipeline import context_tools 
        context = context_tools.get_current_context()
        self.project_name = context["project_name"]       
        self.task_name =  context["task_name"]       
        self.folder_path = context["folder_path"]

        import os
        self.work_dir = Path(os.environ["AYON_WORKDIR"])  
        self.json_template_path = self.work_dir / self.json_file   

    def _create_widgets(self):
        """ Creates the widget elements the user will interact with
        """
        self.header = widgets.ToolHeader('tor_header', 'Task Override ')   

        self.open_workfolder_button = QPushButton("Open current work folder")
        self.half_res_button = QPushButton("Calculate Half Res")
        self.half_res_button.setFixedWidth(260)   

        self.help_button = QPushButton("Show Help")

        self.set_res_to_preview_button = QPushButton("Res to preview")
        self.set_res_to_preview_button.setFixedWidth(100) 

        self.set_res_to_render_button = QPushButton("Res to full")
        self.set_res_to_render_button.setFixedWidth(100) 


        # Settings Section
        self.settings_label = QLabel("Scene Resolution")
        self.settings_x_spin = QSpinBox()        
        self.settings_y_spin = QSpinBox()
        self.settings_x_spin.setMaximum(10000)
        self.settings_y_spin.setMaximum(10000)
        self.settings_x_spin.setFixedWidth(70)
        self.settings_y_spin.setFixedWidth(70)
        self.x_label_settings = QLabel("X")
        self.x_label_settings.setAlignment(Qt.AlignCenter)
        
        # Preview Section
        self.preview_label = QLabel("Review Resolution")
        self.preview_x_spin = QSpinBox()
        self.preview_y_spin = QSpinBox()
        self.preview_x_spin.setMaximum(10000)
        self.preview_y_spin.setMaximum(10000)
        self.preview_x_spin.setFixedWidth(70)
        self.preview_y_spin.setFixedWidth(70)
        self.x_label_preview = QLabel("X")
        self.x_label_preview.setAlignment(Qt.AlignCenter)
        self.overrides_label = QLabel("Options") 
        self.save_button = QPushButton("Save")
        self.remove_button = QPushButton("Remove")
        self.cancel_button = QPushButton("Cancel")
   
    def _create_layouts(self):
        
        self.layout = QVBoxLayout()
        self.layout.setMargin(6)
        self.layout.setSpacing(6)
        self.layout.setAlignment(Qt.AlignTop)
        self.layout.addWidget (self.header)
  
        self.frame0 = QFrame()
        self.frame0.setFrameShape(QFrame.StyledPanel)
        self.frame0_layout = QVBoxLayout(self.frame0)
        self.frame0_layout.setMargin(2)
        self.frame0_layout.setSpacing(6)
        self.frame0_layout.addWidget(self.open_workfolder_button)

        self.layout.addWidget(self.frame0)
        self.settings_layout = QHBoxLayout()
        self.settings_layout.setMargin(2)
        self.settings_layout.setSpacing(6)
        
        self.frame1 = QFrame()
        self.frame1.setFrameShape(QFrame.StyledPanel)
        self.frame1_layout = QVBoxLayout(self.frame1)
        self.frame1_layout.setMargin(2)
        self.frame1_layout.setSpacing(6)

        self.frame1_layout.setMargin(4)
        self.frame1_layout.setSpacing(4)

        self.frame1_layout.addWidget(self.settings_label)

        self.settings_inner_layout = QHBoxLayout()
        self.settings_inner_layout.addWidget(self.settings_x_spin)        
        self.settings_inner_layout.addWidget(self.x_label_settings)
        self.settings_inner_layout.addWidget(self.settings_y_spin)  
      
        self.settings_inner_layout.addWidget(self.set_res_to_render_button)  

        self.settings_layout.addSpacerItem(QSpacerItem(0, 0, QSizePolicy.Expanding, QSizePolicy.Minimum))
        self.settings_layout.addLayout(self.settings_inner_layout)
        self.settings_layout.addSpacerItem(QSpacerItem(0, 0, QSizePolicy.Expanding, QSizePolicy.Minimum))
        self.frame1_layout.addLayout(self.settings_layout)
        
        self.layout.addSpacerItem(QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding))

 
        # Preview Section
        self.frame1_layout.addWidget(self.preview_label)
        self.preview_layout = QHBoxLayout()
        self.preview_inner_layout = QHBoxLayout()       
        self.preview_inner_layout.addWidget(self.preview_x_spin)
        self.preview_inner_layout.addWidget(self.x_label_preview)
        self.preview_inner_layout.addWidget(self.preview_y_spin)
      
      
        self.preview_inner_layout.addWidget(self.set_res_to_preview_button)

        self.preview_layout.addSpacerItem(QSpacerItem(0, 0, QSizePolicy.Expanding, QSizePolicy.Minimum))
        self.preview_layout.addLayout(self.preview_inner_layout)
        self.preview_layout.addSpacerItem(QSpacerItem(0, 0, QSizePolicy.Expanding, QSizePolicy.Minimum))

        self.frame1_layout.addLayout(self.preview_layout)
        
        self.frame1_layout.addSpacerItem(QSpacerItem(40, 40, QSizePolicy.Minimum, QSizePolicy.Expanding))

        
        self.frame1_layout.addWidget(self.half_res_button, 0, Qt.AlignCenter)

        self.layout.addWidget(self.frame1)

        self.frame2 = QFrame()
        self.frame2.setFrameShape(QFrame.StyledPanel)
        self.frame2_layout = QHBoxLayout(self.frame2)
        self.frame2_layout.setMargin(4)
        self.frame2_layout.setSpacing(4)
        
        self.layout.addSpacerItem(QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding))

        
        self.button_layout = QHBoxLayout()

        self.frame2_layout.addWidget(self.save_button)
        self.frame2_layout.addWidget(self.remove_button)
        self.frame2_layout.addWidget(self.cancel_button)
        self.layout.addWidget(self.frame2)
        self.setLayout(self.layout)

    def _connect_signals(self):

        self.save_button.clicked.connect(self.save_json)
        self.cancel_button.clicked.connect(self.reject)
        self.remove_button.clicked.connect(self.remove_json)
        self.half_res_button.clicked.connect(self.half_res)
        self.open_workfolder_button.clicked.connect(self.open_work_directory)
        self.preview_x_spin.valueChanged.connect(self.update_preview_y)
        self.preview_y_spin.valueChanged.connect(self.update_preview_x)
        self.set_res_to_preview_button.clicked.connect( lambda : self.set_maya_resolution("preview"))
        self.set_res_to_render_button.clicked.connect( lambda : self.set_maya_resolution("full"))

    def open_work_directory(self):
        if self.work_dir and self.work_dir.exists():
            utils.FolderOps.explore(self.work_dir )    
        
    def set_maya_resolution(self,type):

        if type == "preview":
            w = int(self.preview_x_spin.value())
            h = int(self.preview_y_spin.value())
        else:
            w = int(self.settings_x_spin.value())
            h = int(self.settings_y_spin.value())

        pAx = 1.0
        pAr = float(w)/h
        cmds.setAttr("defaultResolution.aspectLock", 0)
        cmds.setAttr("defaultResolution.width", w)
        cmds.setAttr("defaultResolution.height", h)
        cmds.setAttr("defaultResolution.pixelAspect", pAx)
        cmds.setAttr("defaultResolution.deviceAspectRatio", pAr)

    def load_json(self):              
        
        if self.json_template_path.exists():
            with open(self.json_template_path, 'r') as f:
                self.data = json.load(f)
            
            self.settings_x_spin.setValue(self.data["Settings"]["render.resolution_x"])
            self.settings_y_spin.setValue(self.data["Settings"]["render.resolution_y"])
            self.preview_x_spin.setValue(self.data["Preview"]["preview.resolution_x"])
            self.preview_y_spin.setValue(self.data["Preview"]["preview.resolution_y"])
        else:
            self.layout.addWidget(QLabel("No JSON file found."))  
            
            
            
            self.data['Settings']['render.resolution_x'] = cmds.getAttr("defaultResolution.width")
            self.data['Settings']['render.resolution_y'] = cmds.getAttr("defaultResolution.height")
          
            self.settings_x_spin.setValue(self.data['Settings']['render.resolution_x'])
            self.settings_y_spin.setValue(self.data['Settings']['render.resolution_y'])
            self.half_res()
 
    def save_json(self):
        self.data["Settings"]["render.resolution_x"] = self.settings_x_spin.value()
        self.data["Settings"]["render.resolution_y"] = self.settings_y_spin.value()
        self.data["Preview"]["preview.resolution_x"] = self.preview_x_spin.value()
        self.data["Preview"]["preview.resolution_y"] = self.preview_y_spin.value()
        
        with open(self.json_template_path, 'w') as f:
            json.dump(self.data, f, indent=4)
            
        print (f'Override written to {self.json_template_path}')
        
        self.accept()
        
    def remove_json(self):
        self.json_template_path.unlink()

    def half_res(self):
        half_x = (self.settings_x_spin.value() // 2) & ~1
        half_y = (self.settings_y_spin.value() // 2) & ~1
        
        self.data['Preview']['preview.resolution_x'] = half_x
        self.data['Preview']['preview.resolution_y'] = half_y
        
        self.preview_x_spin.setValue(half_x)
        self.preview_y_spin.setValue(half_y)

    def update_preview_y(self):
        aspect_ratio = self.settings_x_spin.value() / self.settings_y_spin.value()
        new_y = int(self.preview_x_spin.value() / aspect_ratio)
        self.preview_y_spin.blockSignals(True)
        self.preview_y_spin.setValue(new_y)
        self.preview_y_spin.blockSignals(False)

    def update_preview_x(self):
        aspect_ratio = self.settings_x_spin.value() / self.settings_y_spin.value()
        new_x = int(self.preview_y_spin.value() * aspect_ratio)
        self.preview_x_spin.blockSignals(True)
        self.preview_x_spin.setValue(new_x)
        self.preview_x_spin.blockSignals(False)

def show_dialog():
    dialog = PreviewOverrideDialog(parent=maya_main_window())
    dialog.show()

if __name__ == '__main__':
    show_dialog()


