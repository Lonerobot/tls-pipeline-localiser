from maya import OpenMayaUI as omui
import maya.cmds as cmds
import random as random
from colorsys import hsv_to_rgb
from random import randint, uniform
from PySide2 import QtCore
from PySide2 import QtGui
from PySide2 import QtWidgets
from PySide2 import __version__
from shiboken2 import wrapInstance 
import sys

# -*- coding: utf-8 -*-
"""Example Google style docstrings.

This module demonstrates documentation as specified by the `Google Python
Style Guide`_. Docstrings may extend over multiple lines. Sections are created
with a section header and a colon followed by a block of indented text.
"""

def maya_main_window():
    """
    Return the Maya main window widget as a Python object
    Need to update this for Python 3 as well as 2
    """
    try:
        main_window_ptr = omui.MQtUtil.mainWindow()

        if sys.version_info.major >= 3:
            return wrapInstance(int(main_window_ptr), QtWidgets.QWidget)
        else:
            return wrapInstance(long(main_window_ptr), QtWidgets.QWidget)
    except:
        pass
    
class ColorRange():
    """A simple data holder to specify clean object names for a range to be randomised

    Attributes:
        blue: A range of HSV values to represent the blue spectrum
        yellow: A range of HSV values to represent the yellow spectrum
        green: A range of HSV values to represent the green spectrum
        red: A range of HSV values to represent the red spectrum
        orange: A range of HSV values to represent the orange spectrum
        purple: A range of HSV values to represent the purple spectrum
    """
    def __init__(self):
        self.blue = (0.53,0.65)
        self.yellow = (0.06,0.15)
        self.green = (0.25,0.38)
        self.red = (0.001,0.035)
        self.orange =(0.05,0.1)
        self.purple =(0.75,0.86)
        self.pink = (0.91,0.98)
        self.colorset = ["yellow","blue","green","red"]
     
        
class vxShellColourTool(QtWidgets.QDialog):
    def __init__(self, parent=maya_main_window()):
        super(vxShellColourTool, self).__init__(parent)
        self.qtSignal = QtCore.Signal()
        self.colorRange = ColorRange()
        
    def random_hue(self,col_range):
        """Picks a random hue between a color range and converts it to an RGB colour
        Args:
            col_range (ColorRange): A range between two values.
        Returns: 
            tuple: An RGB value
        """

        h = uniform(col_range[0], col_range[1]) # Select random green'ish hue from hue wheel
        s = uniform(0.6, 1)
        v = uniform(0.3, 0.7)

        r, g, b = hsv_to_rgb(h, s, v)
    
        return (r,g,b)
        
    def setRandomShellColors(self, ColorRange):
        shells = []  
        sel = cmds.ls(sl=True)

        for obj in sel:
            faces = cmds.ls(obj + ".f[*]", flatten=True)  # Get all face indexes from the object.

            for face in faces:
                index = int(face.split("[")[1].rstrip("]"))  # Extract the faces index number.
                cmds.polySelect(obj, extendToShell=index)  # Use the face's index to select the whole shell.

                new_faces = cmds.ls(sl=True, flatten=True)  # Now that the shell is selected, capture its faces.
                shells.append(new_faces)  # Append the face's as a new shell.

                # Remove indexes from the new shell from this current loop, to optimize, and to avoid adding duplicate shells.
                for new_face in new_faces:
                    if new_face in faces:
                        faces.pop(faces.index(new_face))

        cmds.select(sel)  # Restore selection.
        
                
        # Color each shell!
        for shell in shells:
            col = self.random_hue(ColorRange)
            cmds.polyColorPerVertex(shell, r=col[0], g=col[1], b=col[2], cdo=True)
    
        return shells

    def create(self):
        self.setWindowTitle("Set Vertex Colours")
        self.setWindowFlags(QtCore.Qt.Tool)
        self.resize(160, 100) # re-size the window
        self.mainLayout = QtWidgets.QVBoxLayout(self)
        self.titleBox = QtWidgets.QLabel(" Select the Character Meshes")         
        self.titleBox.setStyleSheet("color: black;background-color: white;")
        self.titleBox.setFixedSize(160,20)
        self.combo = QtWidgets.QComboBox(self)        
        self.combo.addItem( 'Azir' )        
        self.combo.addItem( 'Rell' )        
        self.combo.addItem( 'Thresh' )        
        self.combo.addItem( 'Twisted Fate' )        
        self.combo.setCurrentIndex(0)   
        
        self.swatchBox = QtWidgets.QLabel()         
        styleStr = "background-color: %s;" % self.colorRange.colorset[0]   
        self.swatchBox.setStyleSheet(styleStr)        
        self.swatchBox.setFixedSize(20,20)
        
        self.hLayout = QtWidgets.QHBoxLayout()
        self.hLayout.addWidget(self.combo)
        self.hLayout.addWidget(self.swatchBox)

        self.applyBtn = QtWidgets.QPushButton("Assign")    
        self.mainLayout.addWidget(self.titleBox)
        self.mainLayout.addLayout(self.hLayout)
        self.mainLayout.addWidget(self.applyBtn)

        self.combo.currentIndexChanged.connect(self.combo_onChanged)       
        self.applyBtn.clicked.connect(self.applyBtn_onClicked)                    

    def combo_onChanged(self, index):          
       styleStr = "background-color: %s;" % self.colorRange.colorset[index]
       self.swatchBox.setStyleSheet(styleStr)       
        
    def applyBtn_onClicked(self):  
        c = self.combo.currentText()
        vcRange = None
        if c == "Azir":
            vcRange = self.colorRange.yellow
        elif c == "Rell":
            vcRange = self.colorRange.blue
        elif c == "Thresh":
            vcRange = self.colorRange.green
        elif c == "Twisted Fate":
            vcRange = self.colorRange.red
        # check for selction first
        
        selectedObjs = cmds.ls(sl=True)
        selectedGeo = cmds.filterExpand( sm=12 )

        if selectedGeo:
            self.setRandomShellColors(vcRange)
        else:
            cmds.error( "Please select some geometry objects" )

def launch():
    """Builds the UI"""
    try:
        ui.deleteLater()
    except:
        pass
    ui = vxShellColourTool()
    
    try:
        ui.create()
        ui.show()
    except:
        ui.deleteLater()

if __name__ == "__main__":
    launch()
