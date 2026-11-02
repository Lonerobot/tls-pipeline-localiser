"""Publish Plus UI


"""

# Globals
UI_NAME = "publish_plus_dialog"

from playblast_plus.lib.dcc import Host
from playblast_plus.lib import logger

# custom imports
from playblast_plus.vendor.Qt import QtWidgets, QtGui, QtCore

from playblast_plus.lib import utils as utils, widgets, settings, preset, encode
from playblast_plus import PLAYBLAST_PLUS_MODULE_ROOT as module_root, version

from . import PUBLISH_PLUS_MODULE_ROOT
from .main import PublishPlus 

# standard lib imports
from pathlib import Path
from typing import Union
import copy        
import subprocess 

from . import __version__ as version

HOST = Host()
UI_BASECLASS = HOST.UIBASECLASS

class MessageBox(QtWidgets.QDialog):
    def __init__(self, title, message, parent=None):
        super(MessageBox, self).__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self.setWindowFlags(QtCore.Qt.Tool)

        layout = QtWidgets.QVBoxLayout()
        label = QtWidgets.QLabel(message)
        label.setWordWrap(True)
        label.setTextFormat(QtCore.Qt.RichText)
        
        layout.addWidget(label)
        button = QtWidgets.QPushButton("OK")
        button.clicked.connect(self.accept)
        layout.addWidget(button)

        self.setLayout(layout)

    def showEvent(self, event):
        # Get the parent dialog's geometry
        parent_geometry = self.parent().geometry()

        # Set the size of the MessageBox to the same size as the parent dialog
        self.resize(parent_geometry.width() , parent_geometry.height())
        # Calculate the position to place the MessageBox on the right-hand edge of the parent dialog
        x = parent_geometry.x() + parent_geometry.width() + 6
        y = parent_geometry.y() - self.parent().style().pixelMetric(
           QtWidgets.QStyle.PM_TitleBarHeight
     
        )  # Adjust for title bar height
        self.move(x, y)

        super().showEvent(event)
        
class PublishPlusLogger(logger.Logger):
    LOGGER_NAME = "PlayBlastPlusLogger - Publish"

class PublishPlusUI(UI_BASECLASS):
    """
    PlayBlastPlus User Interface
    """
    
    def __init__(self, host:Host):
        super(PublishPlusUI, self).__init__(parent=host.main_window)
        self.host = host
                
        self.publish_plus = PublishPlus()         

        # sets title and object name
        self.setWindowTitle(" ")
        self.setObjectName(UI_NAME)
        self.setWindowFlags(QtCore.Qt.Tool)

        self.setMinimumWidth(350)
        
        # creates main layout widget
        self.main_layout = QtWidgets.QVBoxLayout(self)
        self.main_layout.setMargin(2)
        self.main_layout.setSpacing(6)
        self.main_layout.setAlignment(QtCore.Qt.AlignTop)

        self.process = QtCore.QProcess(self)
        # call the widget creation method
        self._create_widgets()
        # connects signals
        self._connect_signals()

    def CloseEvent (self,event):
        event.accept()
        
    def _connect_signals(self):
        """ Connects widget signals to functionalities
        """
        self.playblast_button.clicked.connect(self.create_review)
        self.publish_button.clicked.connect(self.publish_review)

        self.setup_button.clicked.connect(self.create_sets)
        self.help_button.clicked.connect(self.display_help)
        self.folder_button.clicked.connect(self.open_playblast_directory)
        self.closeEvent = self.CloseEvent

        self.process.readyReadStandardOutput.connect(self.handle_stdout)
        self.process.readyReadStandardError.connect(self.handle_stderr)
        self.process.finished.connect(self.process_finished)

    def _create_widgets(self):
        """ Creates the widget elements the user will interact with
        """
       
        frame_layout = QtWidgets.QVBoxLayout()
        frame_layout.setMargin(4)
        frame_layout.setSpacing(4)

        main_layout = QtWidgets.QGridLayout()

        # bold font for the heading labels
        custom_font = QtGui.QFont()
        custom_font.setBold(True)

        # Add widgets to the layout
        # ToolHeader is a custom label widget imported from lib.widgets
        header = widgets.ToolHeader('pbp_header', 'Publish Review ')  
 
        cam_formlayout = QtWidgets.QGridLayout()
        cam_formlayout.setMargin(0)

        style = widgets.Styles.BUTTON_HERO

        if self.publish_plus.preview_override_data:
            PREVIEW_BTN_STR = "Override Review"
        else:
            PREVIEW_BTN_STR = "Create Review"

        self.playblast_button = QtWidgets.QPushButton(PREVIEW_BTN_STR)
        self.playblast_button.setStyleSheet(style)

        style = widgets.Styles.BUTTON_SIDEKICK
        self.publish_button = QtWidgets.QPushButton("P U B L I S H")
        self.publish_button.setStyleSheet(style)


        # edit frame border and layout
        edit_frame = QtWidgets.QFrame()
        edit_frame.setFrameStyle(6)
        locations_layout = QtWidgets.QGridLayout(edit_frame)
        locations_layout.setMargin(4)
        locations_layout.setSpacing(4)

        # reset
        
        self.setup_button = QtWidgets.QPushButton("Create Publish Sets")
        self.help_button = QtWidgets.QPushButton("Show Help")
        self.folder_button = QtWidgets.QPushButton("Open Output Folder")

        # Overides 
        overrides_frame = QtWidgets.QFrame()
        overrides_frame.setFrameStyle(6)

        overrides_layout = QtWidgets.QGridLayout(overrides_frame)
        overrides_layout.setColumnStretch(1,4)
        
        self.half_res_box = QtWidgets.QCheckBox("Remove Background Images after comp")
        self.half_res_box.setChecked(True)

        self.isolate_box = QtWidgets.QCheckBox("Clear directory before Playblast")
        self.isolate_box.setChecked(True)

        overrides_label = QtWidgets.QLabel("Options")
        overrides_label.setFont(custom_font)
        
        overrides_layout.addWidget(overrides_label, 1,0,1,4) 
                    
        options_button_layout = QtWidgets.QHBoxLayout()          
        options_button_layout.addWidget(self.help_button)          
        options_button_layout.addWidget(self.folder_button)
        overrides_layout.addWidget(self.isolate_box,2,1,1,1)
        overrides_layout.addWidget(self.half_res_box,3,1,1,1)
        overrides_layout.addLayout(options_button_layout,4,1,1,1)

        locations_layout.addWidget(self.setup_button, 0,0,1,5)

        capture_frame = QtWidgets.QFrame()
        capture_frame.setFrameStyle(6)        
        capture_layout = QtWidgets.QGridLayout(capture_frame)
        capture_layout.setMargin(4)
        capture_layout.setSpacing(4)       
        
        capture_layout.addWidget(self.playblast_button,1,2,1,1)
        capture_layout.addWidget(self.publish_button,1,4,1,1)

        # Create the output display widget
        self.mini_console = QtWidgets.QTextEdit(self)
        self.mini_console.setReadOnly(True) 
        self.mini_console.setFixedHeight(100)

        # Style the QTextEdit widget to look like a console
        self.mini_console.setStyleSheet("""
            background-color: rgb(46, 46, 46);                           
            color: lightgreen;
            font-family: 'Courier New', Courier, monospace;
            font-size: 8pt;
        """)

        # add widgets to layouts
        self.main_layout.addWidget(header)
        #self.main_layout.setMenuBar(self.menu_bar)      
        
        self.main_layout.addLayout(frame_layout)
        
        frame_layout.addLayout(cam_formlayout)
        frame_layout.addWidget(edit_frame)        
        frame_layout.addWidget(overrides_frame)           
        frame_layout.addLayout(options_button_layout)                
        frame_layout.addWidget(capture_frame)
        frame_layout.addWidget(self.mini_console)
           
    def log_message_to_qt_console(self, title, message=''):
        console_message = f'{title}{" : " + str(message) if message else ""}'
        PublishPlusLogger.info (console_message)
        self.mini_console.append(f'{console_message}')
        cursor = self.mini_console.textCursor()
        cursor.movePosition(QtGui.QTextCursor.End)
        self.mini_console.setTextCursor(cursor)
        self.mini_console.ensureCursorVisible()
        QtWidgets.QApplication.processEvents()

    def display_help(self):
        
        help_str ="""
        <h3>Publish Review Help</h3>        
        <p>Look for a set in the outliner called <b><span style='color:lightgreen'>pbp_publish.</span></b>
        It contains 2 sets for the foreground and background layers.</p>
        <ul style="list-style-type:square;" >
        <li><b><span style='color:lightpink'>pbp_background</span></b></li>        
        <p>Place the camera (with imageplane) in this set</p>             
        <li><b><span style='color:lightpink'>pbp_foreground</span></b></li>        
        <p>This should contain the animated 3d objects. Just add the top group for the whole rig.</p>
        </ul>        
        <p>You can also add any extra geometry into either set.</p>
        <p>Remember that anything added in the foreground layer will be rendered in the pubished frame sequence.
        </p>
        <p> Anything in the background layer will feature in the review, but not in the foreground frames</p>
        """
             
        message_box = MessageBox(" ", help_str, self)
        message_box.exec_()
        
    
    def create_review(self):
        
        clean = self.half_res_box.isChecked()
        purge = self.isolate_box.isChecked()  


        if self.publish_plus.preview_override_data:
            self.log_message_to_qt_console('Creating Review' , 'PREVIEW OVERIDE ON')
            self.publish_plus.create_media_from_task_override(purge_directory=purge, cleanup=clean)
        else:
            self.log_message_to_qt_console('Creating Review...')
            self.publish_plus.create_publish_media(purge_directory=purge, cleanup=clean)
   
    def publish_review(self):
        
        def run_command(command):
            # can we add the working folder here???
            working_directory = Path(__file__).parent.absolute()
            module_directory = str(working_directory.parent)

            import sys
            sys.path.append(module_directory)
            self.log_message_to_qt_console('Working Directory' , working_directory)

            import os
            os.chdir(working_directory)

            # process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True)

            # Extract the first entry into a new variable and leave the rest of the list intact
            exe_path, *args = command
            self.process.start (exe_path, args)
  
        from ayon_core.lib import get_ayon_launcher_args
        pb_path = str( PUBLISH_PLUS_MODULE_ROOT / 'publishReview.py')
        self.log_message_to_qt_console("Starting Publish...")
        args = get_ayon_launcher_args("run", pb_path, str(self.publish_plus.output_root) )
        self.log_message_to_qt_console (f'Executing Publish Args - {args}')
        
        try:
            run_command(args)
        except subprocess.CalledProcessError as e:
            self.log_message_to_qt_console("Command failed with return code", f"{e.returncode}: {e.cmd}")
  
        # subprocess.run(args)

    def handle_stdout(self):
        data = self.process.readAllStandardOutput()
        stdout = bytes(data).decode("utf8")
        self.log_message_to_qt_console("Progress", stdout)

    def handle_stderr(self):
        data = self.process.readAllStandardError()
        stderr = bytes(data).decode("utf8")
        self.log_message_to_qt_console("ERROR", stderr)

    def process_finished(self):
        self.log_message_to_qt_console("Progress", 'Publish finished.')
   
    def create_sets(self):
        self.log_message_to_qt_console("Info", 'Review publishing sets created.')
        # print ("CREATE SETS PRESSED")
        self.publish_plus.create_sets()

    def clear_playblast_directory(self):
        utils.FolderOps.purge_contents(self.current_playblast_directory)
        self.log_message_to_qt_console("Info", "Playblast directory was cleared.")
        
    def open_playblast_directory(self):
        utils.FolderOps.explore(self.publish_plus.output_root)
        self.log_message_to_qt_console("Current Playblast Directory", self.publish_plus.output_root)

def run(**kwargs):  # @unusedVariable
    """
    Opens the Playblast Plus UI
    """
    PublishPlusLogger.info(version)

    if HOST:
        tool = PublishPlusUI(host=HOST)
        tool.show()
    else:
        PublishPlusLogger.info(
            f"PlayblastPlus Host environment not present or supported..")

if __name__ == "__main__":
    run()
