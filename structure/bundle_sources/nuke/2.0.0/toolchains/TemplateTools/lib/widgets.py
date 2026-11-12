import nuke
from pathlib import Path

# PySide import switch:
# - Use PySide6 if Nuke version is 16 or above.
# - Use PySide2 if Nuke version is 11 or higher but below 16.
# - Use legacy PySide if Nuke version is below 11.
try:
    if hasattr(nuke, 'NUKE_VERSION_MAJOR') and nuke.NUKE_VERSION_MAJOR >= 16:
        from PySide6 import QtCore, QtGui, QtWidgets
        from PySide6.QtCore import Qt
        PYSIDE_VERSION = 6
    elif nuke.NUKE_VERSION_MAJOR < 11:
        from PySide import QtCore, QtGui, QtGui as QtWidgets
        from PySide.QtCore import Qt
        PYSIDE_VERSION = 1
    else:
        from PySide2 import QtCore, QtGui, QtWidgets
        from PySide2.QtCore import Qt
        PYSIDE_VERSION = 2
except ImportError:
    # Fallback: try using the Qt.py abstraction if available
    try:
        from Qt import QtCore, QtGui, QtWidgets
        PYSIDE_VERSION = 0  # Unknown/abstraction
    except ImportError:
        raise ImportError("No Qt bindings found. Please install PySide2, PySide6, or Qt.py.")


class ToolHeader(QtWidgets.QWidget):
    """A standardised Tool Header widget, with line Logo and a 
        setter for the script name field.

    Args:
        name (str): the control name (not needed)
        text (str): The title text to be shown on the header 
    
    Returns:
        A QWidget control item.
    
    **Useful code:**
    
    To get a visual representation of all icons loaded in Maya

    .. code-block:: python

        import maya.app.general.resourceBrowser as resourceBrowser
        resBrowser = resourceBrowser.resourceBrowser()
        path = resBrowser.run()
 
    """

    LINE_LOGO = 'tl_logo_white.png'
    # conform to the Line's re-brand
    STYLE_SHEET = (
            "font: bold 14px;"
            "color: #f8f8f8;"
            "background-color: #0B0B0B;"  
            "padding:2px"
                )

    def __init__(self, name='', text= '', parent=None):
            super(ToolHeader, self).__init__(parent)
            self.name = name
            self.headerTitle = text
            self.registerUserData = ""            
            self.setMinimumSize(QtCore.QSize(120, 40))
            self.setStyleSheet(self.STYLE_SHEET)             
            self.create_widgets()
            self.create_layout()
            self.create_actions()
        
    def create_widgets(self):
            
        self.labelIcon = ClickableLabel()
        self.labelIcon.setStyleSheet(self.STYLE_SHEET)          
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Minimum, 
                                           QtWidgets.QSizePolicy.Minimum)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(
            self.labelIcon.sizePolicy().hasHeightForWidth())
        self.labelIcon.setMaximumSize(QtCore.QSize(1600, 40))
        self.labelIcon.setSizePolicy(sizePolicy) 

        self.labelText = ClickableLabel()
        self.labelText.setStyleSheet(self.STYLE_SHEET)
        self.labelText.setText(self.headerTitle)
        # self.labelText.setMaximumSize(QtCore.QSize(10000, 40)) 

        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Expanding,
                                           QtWidgets.QSizePolicy.Fixed)

        # self.labelText.setSizePolicy(sizePolicy) 
        self.labelText.setAlignment(
            QtCore.Qt.AlignRight|QtCore.Qt.AlignLeading|QtCore.Qt.AlignVCenter)


    def create_layout(self): 
        
        self.gridLayout = QtWidgets.QGridLayout(self)
        self.gridLayout.setContentsMargins(0, 0, 0, 0)
        self.gridLayout.setVerticalSpacing(0)
        self.gridLayout.setHorizontalSpacing(0)
        self.gridLayout.setObjectName('gridLayout') 

        self.addHeaderIcon(self.labelIcon)
        
        self.gridLayout.addWidget(self.labelIcon,1,0)
        self.gridLayout.addWidget(self.labelText,1,1)
        self.setLayout(self.gridLayout) 

    def create_actions(self):
        self.labelIcon.clicked.connect(self.iconClicked)
        self.labelText.clicked.connect(self.iconClicked)

    def iconClicked(self):
        print (f"Icon clicked: {self.headerTitle}")
        # import webbrowser
        # webbrowser.open(settings.get_doclink())
        
    def setTitleText(self,text):
        self.headerTitle = text 
        self.labelText.setText(self.headerTitle)

            
    def addHeaderIcon(self, widget):
        # Get the correct path relative to this widgets.py file
        current_file = Path(__file__)
        icon_root = current_file.parent.parent / "icons"  # Go up from lib/ to 1.0.0/ then to icons/
        
        if icon_root.exists():
            image_path = icon_root / self.LINE_LOGO
            if image_path.exists():
                image = QtGui.QImage(str(image_path))
                if not image.isNull():
                    pixmap = QtGui.QPixmap()
                    pixmap.convertFromImage(image)
                    widget.setPixmap(pixmap)
                    print(f"Header icon loaded: {image_path}")
                else:
                    print(f"Failed to load image: {image_path}")
            else:
                print(f"Header icon file not found: {image_path}")
        else:
            print(f"Header icon directory not found: {icon_root}")

class ClickableLabel(QtWidgets.QLabel):
    clicked= QtCore.Signal()

    def mouseReleaseEvent(self, ev):
        self.clicked.emit()




class MetaDataButton(QtWidgets.QPushButton):
    # Color mapping for common tag categories
    TAG_COLORS = {
        'key': '#1976D2',
        'roto': '#F57C00',      
        # Color tags
        'color': '#D32F2F',            # Red
        'grading': '#D32F2F',
        'look-dev': '#D32F2F',  
        # 3D tags
        '3d': "#36B16D",               # Blue Grey
        'camera': '#36B16D',    
        # Effects tags
        'fx': '#E91E63',
        'particles': '#E91E63',
        # Default color
        'default': "#686868"           # Dark grey
    }
    
    def __init__(self, parent=None, text=''):
        super(MetaDataButton, self).__init__(parent)
        
        self.name = text
        self.setText(text)
        
        # Get color for this tag
        tag_color = self.get_tag_color(text.lower())
        
        # Create dynamic stylesheet with the tag color
        self.setStyleSheet(f"""
            QPushButton {{
                border: 2px solid {tag_color};
                border-radius: 6px;
                color: rgb(255,255,255);
                background-color: {tag_color};
                padding: 1px 2px;
                font-size: 10px;
                font-weight: bold;
                min-height: 14px;
                min-width: 36px;
            }}
            QPushButton:hover {{
                border: 2px solid #ffffff;
                background-color: {self.lighten_color(tag_color, 0.2)};
            }}
            QPushButton:pressed {{
                border: 2px solid #ffffff;
                background-color: {self.darken_color(tag_color, 0.2)};
            }}
        """)
        
        self.setAutoDefault(False)
    
    def get_tag_color(self, tag_text):
        """Get the color for a tag based on common tag mappings."""
        # Check exact matches first
        if tag_text in self.TAG_COLORS:
            return self.TAG_COLORS[tag_text]
        
        # Check for partial matches
        for tag_key, color in self.TAG_COLORS.items():
            if tag_key in tag_text or tag_text in tag_key:
                return color
        
        # Return default color if no match found
        return self.TAG_COLORS['default']
    
    def lighten_color(self, hex_color, factor=0.2):
        """Lighten a hex color by a given factor."""
        try:
            # Remove # if present
            hex_color = hex_color.lstrip('#')
            
            # Convert to RGB
            r = int(hex_color[0:2], 16)
            g = int(hex_color[2:4], 16)
            b = int(hex_color[4:6], 16)
            
            # Lighten
            r = min(255, int(r + (255 - r) * factor))
            g = min(255, int(g + (255 - g) * factor))
            b = min(255, int(b + (255 - b) * factor))
            
            return f"#{r:02x}{g:02x}{b:02x}"
        except:
            return hex_color
    
    def darken_color(self, hex_color, factor=0.2):
        """Darken a hex color by a given factor."""
        try:
            # Remove # if present
            hex_color = hex_color.lstrip('#')
            
            # Convert to RGB
            r = int(hex_color[0:2], 16)
            g = int(hex_color[2:4], 16)
            b = int(hex_color[4:6], 16)
            
            # Darken
            r = max(0, int(r * (1 - factor)))
            g = max(0, int(g * (1 - factor)))
            b = max(0, int(b * (1 - factor)))
            
            return f"#{r:02x}{g:02x}{b:02x}"
        except:
            return hex_color


class FlowLayout(QtWidgets.QLayout):
    """
    A layout that arranges widgets in a flow, wrapping to the next line when needed.
    Perfect for displaying tag buttons that can wrap to multiple lines.
    """
    def __init__(self, parent=None, margin=0, spacing=-1):
        super(FlowLayout, self).__init__(parent)
        if parent is not None:
            self.setContentsMargins(margin, margin, margin, margin)
        self.setSpacing(spacing)
        self.itemList = []

    def addItem(self, item):
        self.itemList.append(item)

    def count(self):
        return len(self.itemList)

    def itemAt(self, index):
        if index >= 0 and index < len(self.itemList):
            return self.itemList[index]
        return None

    def takeAt(self, index):
        if index >= 0 and index < len(self.itemList):
            return self.itemList.pop(index)
        return None

    def expandingDirections(self):
        return QtCore.Qt.Orientations(QtCore.Qt.Orientation(0))

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        height = self.doLayout(QtCore.QRect(0, 0, width, 0), True)
        return height

    def setGeometry(self, rect):
        super(FlowLayout, self).setGeometry(rect)
        self.doLayout(rect, False)

    def sizeHint(self):
        return self.minimumSize()

    def minimumSize(self):
        size = QtCore.QSize()
        for item in self.itemList:
            size = size.expandedTo(item.minimumSize())
        margins = self.contentsMargins()
        size += QtCore.QSize(margins.left() + margins.right(), margins.top() + margins.bottom())
        return size

    def doLayout(self, rect, testOnly):
        x = rect.x()
        y = rect.y()
        lineHeight = 0
        for item in self.itemList:
            widget = item.widget()
            spaceX = self.spacing() + widget.style().layoutSpacing(
                QtWidgets.QSizePolicy.PushButton, QtWidgets.QSizePolicy.PushButton, QtCore.Qt.Horizontal)
            spaceY = self.spacing() + widget.style().layoutSpacing(
                QtWidgets.QSizePolicy.PushButton, QtWidgets.QSizePolicy.PushButton, QtCore.Qt.Vertical)
            nextX = x + item.sizeHint().width() + spaceX
            if nextX - spaceX > rect.right() and lineHeight > 0:
                x = rect.x()
                y = y + lineHeight + spaceY
                nextX = x + item.sizeHint().width() + spaceX
                lineHeight = 0
            if not testOnly:
                item.setGeometry(QtCore.QRect(QtCore.QPoint(x, y), item.sizeHint()))
            x = nextX
            lineHeight = max(lineHeight, item.sizeHint().height())
        return y + lineHeight - rect.y()

class ClearSearchButton(QtWidgets.QPushButton):
    """A small button with a cross icon for clearing the search field."""
    
    def __init__(self, parent=None):
        super(ClearSearchButton, self).__init__(parent)
        
        # Load the X icon from SVG
        self.load_icon()
        
        self.setFixedSize(20, 20)
        self.setStyleSheet("""
            QPushButton {
                border: none;
                border-radius: 1px;
                background-color: #444444;
                padding: 0px;
            }
            QPushButton:hover {
                background-color: #666666;
            }
            QPushButton:pressed {
                background-color: #222222;
            }
        """)
        
        self.setToolTip("Clear search")
        self.setAutoDefault(False)
    
    def load_icon(self):
        """Load the X icon from SVG."""
        try:
            # Get the correct path relative to this widgets.py file
            current_file = Path(__file__)
            icon_root = current_file.parent.parent / "icons"
            icon_path = icon_root / "x-octagon.svg"
            
            if icon_path.exists():
                # Load SVG as pixmap using version-aware imports
                try:
                    if PYSIDE_VERSION == 6:
                        from PySide6.QtSvg import QSvgRenderer
                        from PySide6.QtGui import QPixmap, QPainter
                    elif PYSIDE_VERSION == 2:
                        from PySide2.QtSvg import QSvgRenderer
                        from PySide2.QtGui import QPixmap, QPainter
                    else:
                        # PySide 1 doesn't have QtSvg in the same way, use fallback
                        raise ImportError("SVG not supported in PySide 1")
                    
                    renderer = QSvgRenderer(str(icon_path))
                    pixmap = QPixmap(16, 16)  # 16x16 for the 20x20 button
                    pixmap.fill(QtCore.Qt.transparent)
                    
                    painter = QPainter(pixmap)
                    renderer.render(painter)
                    painter.end()
                    
                    icon = QtGui.QIcon(pixmap)
                    self.setIcon(icon)
                except ImportError:
                    # Fallback to text if SVG support not available
                    self.setText("×")
            else:
                # Fallback to text if icon not found
                self.setText("×")
                
        except Exception as e:
            # Fallback to text if anything goes wrong
            self.setText("×")
            print(f"Could not load clear search icon: {e}")

class VideoIconButton(QtWidgets.QPushButton):
    """A small icon button with video icon for animation preview."""
    
    def __init__(self, parent=None):
        super(VideoIconButton, self).__init__(parent)
        
        # Load the video icon from SVG
        self.load_icon()
        
        self.setFixedSize(32, 32)
        self.setStyleSheet("""
            QPushButton {
                border: none;
                border-radius: 1px;
                background-color: rgba(68, 68, 68, 180);
                padding: 0px;
            }
            QPushButton:hover {
                background-color: rgba(102, 102, 102, 200);
            }
            QPushButton:pressed {
                background-color: rgba(34, 34, 34, 220);
            }
        """)
        
        self.setToolTip("Show animation preview")
        self.setAutoDefault(False)
    
    def load_icon(self):
        """Load the video icon from SVG."""
        try:
            # Get the correct path relative to this widgets.py file
            current_file = Path(__file__)
            icon_root = current_file.parent.parent / "icons"
            icon_path = icon_root / "video.svg"
            
            if icon_path.exists():
                # Load SVG as pixmap using version-aware imports
                try:
                    if PYSIDE_VERSION == 6:
                        from PySide6.QtSvg import QSvgRenderer
                        from PySide6.QtGui import QPixmap, QPainter
                    elif PYSIDE_VERSION == 2:
                        from PySide2.QtSvg import QSvgRenderer
                        from PySide2.QtGui import QPixmap, QPainter
                    else:
                        # PySide 1 doesn't have QtSvg in the same way, use fallback
                        raise ImportError("SVG not supported in PySide 1")
                    
                    renderer = QSvgRenderer(str(icon_path))
                    pixmap = QPixmap(20, 20)  # 20x20 for the 32x32 button
                    pixmap.fill(QtCore.Qt.transparent)
                    
                    painter = QPainter(pixmap)
                    renderer.render(painter)
                    painter.end()
                    
                    icon = QtGui.QIcon(pixmap)
                    self.setIcon(icon)
                except ImportError:
                    # Fallback to text if SVG support not available
                    self.setText("▶")
            else:
                # Fallback to text if icon not found
                self.setText("▶")
                
        except Exception as e:
            # Fallback to text if anything goes wrong
            self.setText("▶")
            print(f"Could not load video icon: {e}")