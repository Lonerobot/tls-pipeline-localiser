"""
Template Loader UI

A simplified Qt-based template browser with PNG frame previews for Nuke templates.
Uses FFmpeg to extract middle frames from MP4 files for reliable preview.

Author: Pipeline Team
Date: July 2025
"""

import sys
import os
import json
import platform
import traceback
import subprocess
import tempfile
import shutil
from pathlib import Path

from lib.widgets import ToolHeader

try:
    import nuke
    # PySide import switch:
    # - Use PySide6 if Nuke version is 16 or above.
    # - Use PySide2 if Nuke version is 11 or higher but below 16.
    # - Use legacy PySide if Nuke version is below 11.
    if hasattr(nuke, 'NUKE_VERSION_MAJOR') and nuke.NUKE_VERSION_MAJOR >= 16:
        from PySide6.QtWidgets import (
            QApplication, QWidget, QVBoxLayout, QHBoxLayout,
            QTreeWidget, QTreeWidgetItem, QPushButton, QLabel, QSplitter,
            QMessageBox, QLineEdit, QGroupBox, QDialog, QMenu, QAction
        )
        from PySide6.QtCore import Qt
        from PySide6.QtGui import QPixmap, QFont, QIcon
        PYSIDE_VERSION = 6
    elif nuke.NUKE_VERSION_MAJOR < 11:
        from PySide.QtGui import (
            QApplication, QWidget, QVBoxLayout, QHBoxLayout,
            QTreeWidget, QTreeWidgetItem, QPushButton, QLabel, QSplitter,
            QMessageBox, QLineEdit, QGroupBox, QDialog, QMenu, QAction
        )
        from PySide.QtCore import Qt
        from PySide.QtGui import QPixmap, QFont, QIcon
        PYSIDE_VERSION = 1
    else:
        from PySide2.QtWidgets import (
            QApplication, QWidget, QVBoxLayout, QHBoxLayout,
            QTreeWidget, QTreeWidgetItem, QPushButton, QLabel, QSplitter,
            QMessageBox, QLineEdit, QGroupBox, QDialog, QMenu, QAction
        )
        from PySide2.QtCore import Qt
        from PySide2.QtGui import QPixmap, QFont, QIcon
        PYSIDE_VERSION = 2
    QT_AVAILABLE = True
except ImportError:
    try:
        # Fallback: try using the Qt.py abstraction if available
        from Qt import QtWidgets, QtCore, QtGui
        from Qt.QtWidgets import (
            QApplication, QWidget, QVBoxLayout, QHBoxLayout,
            QTreeWidget, QTreeWidgetItem, QPushButton, QLabel, QSplitter,
            QMessageBox, QLineEdit, QGroupBox, QDialog, QMenu, QAction
        )
        from Qt.QtCore import Qt
        from Qt.QtGui import QPixmap, QFont, QIcon
        PYSIDE_VERSION = 0  # Unknown/abstraction
        QT_AVAILABLE = True
    except ImportError:
        QT_AVAILABLE = False
        raise ImportError("No Qt bindings found. Please install PySide2, PySide6, or Qt.py.")

# Add the toolchain directory to Python path for imports
toolchain_dir = Path(__file__).parent
if str(toolchain_dir) not in sys.path:
    sys.path.insert(0, str(toolchain_dir))

try:
    from template_library import TemplateLibrary
except ImportError:
    # Mock for testing outside Nuke
    class MockNuke:
        @staticmethod
        def tprint(msg): print(f"[Nuke] {msg}")
    nuke = MockNuke()


def debug_print(message):
    """Print debug messages that are visible in Nuke's Script Editor."""
    msg_str = str(message)
    print(msg_str)
    
    try:
        if hasattr(nuke, 'tprint'):
            nuke.tprint(msg_str)
        sys.stderr.write(f"[TemplateLoader] {msg_str}\n")
        sys.stderr.flush()
    except Exception:
        pass


def get_nuke_main_window():
    """Get the main Qt window of Nuke."""
    for widget in QApplication.topLevelWidgets():
        if widget.metaObject().className() == "Foundry::UI::DockMainWindow":
            return widget
    return None


class VideoPreviewUtils:
    """Simple utility for extracting PNG frames from MP4 videos using FFmpeg."""
    
    @staticmethod
    def find_ffmpeg():
        """Find ffmpeg executable in the system."""
        try:
            # Try common locations
            for cmd in ['ffmpeg', 'ffmpeg.exe']:
                try:
                    result = subprocess.run([cmd, '-version'], capture_output=True, text=True, timeout=5)
                    if result.returncode == 0:
                        return cmd
                except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
                    continue
            
            # Try Windows paths
            if platform.system() == "Windows":
                common_paths = [
                    r"C:\ffmpeg\bin\ffmpeg.exe",
                    r"C:\Program Files\ffmpeg\bin\ffmpeg.exe",
                ]
                for path in common_paths:
                    if os.path.isfile(path):
                        return path
            
            return None
        except Exception:
            return None
    
    @staticmethod
    def extract_middle_frame(video_path, output_path):
        """Extract the middle frame of a video as a PNG image."""
        ffmpeg_cmd = VideoPreviewUtils.find_ffmpeg()
        if not ffmpeg_cmd:
            debug_print(f"FFmpeg not found - cannot extract frame from {video_path}")
            return False
            
        try:
            # Try different timestamp strategies for problematic videos
            timestamps = ['00:00:01', '00:00:00.5', '00:00:02', '00:00:00.1']
            
            for timestamp in timestamps:
                # Clean up any previous attempt
                if os.path.exists(output_path):
                    try:
                        os.remove(output_path)
                    except:
                        pass
                
                # Extract frame at specific timestamp
                cmd = [
                    ffmpeg_cmd,
                    '-i', video_path,
                    '-ss', timestamp,
                    '-vframes', '1',    # Extract 1 frame
                    '-y',               # Overwrite output
                    '-f', 'image2',     # Force image format
                    '-loglevel', 'error',  # Reduce noise
                    output_path
                ]
                
                debug_print(f"Trying FFmpeg with timestamp {timestamp}")
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
                
                # Check if extraction was successful
                if result.returncode == 0 and os.path.isfile(output_path) and os.path.getsize(output_path) > 0:
                    debug_print(f"FFmpeg extraction successful at {timestamp}: {output_path}")
                    return True
                
                # If this attempt failed, log it and try next timestamp
                debug_print(f"FFmpeg failed at timestamp {timestamp}, return code: {result.returncode}")
            
            # All timestamps failed
            debug_print(f"FFmpeg extraction failed for all timestamps on {video_path}")
            if result.stderr:
                debug_print(f"Final FFmpeg stderr: {result.stderr[:200]}...")
            return False
                
        except subprocess.TimeoutExpired:
            debug_print(f"FFmpeg timeout extracting frame from {video_path}")
            return False
        except Exception as e:
            debug_print(f"FFmpeg extraction error: {e}")
            return False


class TemplateLoaderWindow(QDialog):
    """Simplified template loader with PNG frame preview."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Set proper window flags to ensure correct stacking order
        self.setWindowFlags(Qt.Dialog | Qt.WindowCloseButtonHint)
        
        try:
            from template_library import TemplateLibrary
            self.template_library = TemplateLibrary()
        except ImportError:
            self.template_library = None
        
        self.current_video_path = None
        self.temp_dir = tempfile.mkdtemp(prefix="nuke_template_previews_")
        
        # Load icons
        self.load_icons()
        
        self.setWindowTitle(" ")
        min_height = 80 + 200 + 325 + 70 + 50  # = 725px total
        self.setMinimumSize(500, min_height)
        self.resize(600, 800)
        self.setAttribute(Qt.WA_DeleteOnClose)
        
        self.setup_ui()
        self.load_templates()
        
        # Check FFmpeg availability
        if VideoPreviewUtils.find_ffmpeg():
            debug_print("FFmpeg found - frame extraction available")
        else:
            debug_print("FFmpeg not found - no frame preview available")
    
    def load_icons(self):
        """Load icons for folders, templates, and contact sheet."""
        # Get icons directory from TLA_COMP_CORE environment variable
        nuke_path = os.environ.get('TLA_COMP_CORE')
        if nuke_path:
            icons_dir = Path(nuke_path) / "icons"
        else:
            # Fallback to local icons if NUKE_PATH not set
            icons_dir = Path(__file__).parent / "icons"
        
        # Load local toolchain icons directory for contact icon
        local_icons_dir = Path(__file__).parent / "icons"
        
        self.folder_icon = QIcon()
        self.nuke_icon = QIcon()
        self.contact_icon_path = None
        
        # Load folder icon
        folder_icon_path = icons_dir / "folder.png"
        if folder_icon_path.exists():
            self.folder_icon = QIcon(str(folder_icon_path))
            debug_print(f"Folder icon loaded from: {folder_icon_path}")
        else:
            debug_print(f"Folder icon not found at: {folder_icon_path}")
        
        # Load Nuke icon
        nuke_icon_path = icons_dir / "nuke.png"
        if nuke_icon_path.exists():
            self.nuke_icon = QIcon(str(nuke_icon_path))
            debug_print(f"Nuke icon loaded from: {nuke_icon_path}")
        else:
            debug_print(f"Nuke icon not found at: {nuke_icon_path}")
        
        # Load contact icon from local toolchain icons
        contact_icon_path = local_icons_dir / "contact.png"
        if contact_icon_path.exists():
            self.contact_icon_path = str(contact_icon_path)
            debug_print(f"Contact icon loaded from: {contact_icon_path}")
        else:
            debug_print(f"Contact icon not found at: {contact_icon_path}")
    
    def setup_ui(self):
        """Setup the simplified single-column user interface."""
        main_layout = QVBoxLayout(self)
        
        # Header (fixed size)
        header_widget = self.create_header_widget()
        main_layout.addWidget(header_widget)
        
        # Template tree (dominant widget - gets most space)
        tree_panel = self.create_template_panel()
        main_layout.addWidget(tree_panel, 60)  # 60% stretch factor
        
        # Preview panel (fixed 16:9 aspect ratio)
        preview_panel = self.create_preview_panel()
        main_layout.addWidget(preview_panel, 0)  # No stretch - fixed size
        
        # Load button (fixed size)
        load_button = self.create_load_button()
        main_layout.addWidget(load_button, 0)  # No stretch - fixed size
    
    def create_header_widget(self):
        return ToolHeader(name='template_header', text='Template Loader')   
    
    def create_template_panel(self):
        """Create the template tree panel."""
        panel = QGroupBox("Templates")
        layout = QVBoxLayout(panel)
        
        # Search box with clear button
        search_container = QHBoxLayout()
        
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Search templates...")
        self.search_box.textChanged.connect(self.filter_templates)
        search_container.addWidget(self.search_box)
        
        # Import and create clear button
        from lib.widgets import ClearSearchButton
        self.clear_search_button = ClearSearchButton()
        self.clear_search_button.clicked.connect(self.clear_search)
        search_container.addWidget(self.clear_search_button)
        
        layout.addLayout(search_container)
        
        # Template tree with context menu
        self.template_tree = QTreeWidget()
        self.template_tree.setHeaderLabel("Template Categories")
        self.template_tree.itemSelectionChanged.connect(self.on_template_selected)
        self.template_tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.template_tree.customContextMenuRequested.connect(self.show_context_menu)
        layout.addWidget(self.template_tree)
        
        return panel
    
    def create_preview_panel(self):
        """Create the preview panel that scales with window width while maintaining aspect ratio."""
        panel = QGroupBox("Preview")
        layout = QVBoxLayout(panel)
        
        # Create a widget that will contain the preview image and overlay button
        self.preview_widget = QWidget()
        self.preview_widget.setMinimumSize(300, int(300 * 9 / 16))  # 16:9 aspect ratio minimum
        
        # Import QSizePolicy for the widget - use version-aware imports
        if PYSIDE_VERSION == 6:
            from PySide6.QtWidgets import QSizePolicy
        elif PYSIDE_VERSION == 2:
            from PySide2.QtWidgets import QSizePolicy
        elif PYSIDE_VERSION == 1:
            from PySide.QtGui import QSizePolicy
        else:
            from Qt.QtWidgets import QSizePolicy
        self.preview_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        
        # Preview image with 16:9 aspect ratio that scales with window
        self.preview_label = QLabel(self.preview_widget)
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.preview_label.setStyleSheet("""
            QLabel {
                border: none;
                background-color: #1a1a1a;
                border-radius: 5px;
            }
        """)
        self.preview_label.setText("No preview available")
        
        # Import and create video icon button - positioned over the preview
        from lib.widgets import VideoIconButton
        self.video_button = VideoIconButton(self.preview_widget)
        self.video_button.clicked.connect(self.open_video_externally)
        self.video_button.setVisible(False)  # Hidden by default until a template with video is selected
        
        # Override resize event to position elements properly
        def resizeEvent(event):
            # Calculate proper size to maintain 16:9 aspect ratio while filling width
            widget_width = self.preview_widget.width()
            widget_height = int(widget_width * 9 / 16)
            
            # Update the widget height to match the calculated aspect ratio
            self.preview_widget.setFixedHeight(widget_height)
            
            # Make preview label fill the entire widget
            self.preview_label.setGeometry(0, 0, widget_width, widget_height)
            
            # Position video button in bottom-right corner with 10px margin
            button_size = self.video_button.size()
            x = widget_width - button_size.width() - 10
            y = widget_height - button_size.height() - 10
            self.video_button.move(x, y)
            
            # Raise the button to ensure it's on top
            self.video_button.raise_()
        
        self.preview_widget.resizeEvent = resizeEvent
        
        # Add the preview widget directly to the layout
        layout.addWidget(self.preview_widget)
        
        # Tags display area
        tags_label = QLabel("Tags:")
        tags_label.setStyleSheet("font-weight: bold; color: #ccc;")
        layout.addWidget(tags_label)
        
        # Import FlowLayout from widgets
        from lib.widgets import FlowLayout
        
        # Create tags container with FlowLayout
        self.tags_container = QWidget()
        self.tags_layout = FlowLayout(self.tags_container, margin=2, spacing=5)
        self.tags_container.setLayout(self.tags_layout)
        
        # Set the tags container to expand horizontally but limit height to contents
        if PYSIDE_VERSION == 6:
            from PySide6.QtWidgets import QSizePolicy
        elif PYSIDE_VERSION == 2:
            from PySide2.QtWidgets import QSizePolicy
        elif PYSIDE_VERSION == 1:
            from PySide.QtGui import QSizePolicy
        else:
            from Qt.QtWidgets import QSizePolicy
        self.tags_container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        self.tags_container.setMaximumHeight(50)
        
        layout.addWidget(self.tags_container)
        
        # Description display area
        description_label = QLabel("Description:")
        description_label.setStyleSheet("font-weight: bold; color: #ccc;")
        layout.addWidget(description_label)
        
        # Description content
        self.description_content = QLabel("No description available")
        self.description_content.setWordWrap(True)
        self.description_content.setStyleSheet("""
            QLabel {
                color: #aaa;
                font-style: italic;
                padding: 5px;
                background-color: #2a2a2a;
                border-radius: 3px;
                font-size: 11px;
            }
        """)
        self.description_content.setMaximumHeight(60)
        layout.addWidget(self.description_content)
        
        # Set the panel to have a reasonable height based on minimum preview size
        panel_height = int(300 * 9 / 16) + 160  # Extra space for tags, description and margins
        panel.setMinimumHeight(panel_height)
        
        # Set size policy to prevent the preview panel from expanding vertically
        panel.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        
        return panel
    
    def create_load_button(self):
        """Create the load template button."""
        self.load_button = QPushButton("Load Selected Template")
        self.load_button.clicked.connect(self.load_selected_template)
        self.load_button.setEnabled(False)
        self.load_button.setMinimumHeight(50)
        self.load_button.setStyleSheet("""
            QPushButton {
                font-size: 14px;
                font-weight: bold;
                padding: 10px;
                background-color: #4a90e2;
                color: white;
                border: none;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #357abd;
            }
            QPushButton:disabled {
                background-color: #cccccc;
                color: #666666;
            }
        """)
        return self.load_button
    
    def load_templates(self):
        """Load templates into the tree widget."""
        self.template_tree.clear()
        
        try:
            # Get template directory from toolchain configuration
            template_path = None
            
            try:
                nuke_path = os.environ.get('TLA_COMP_CORE')
                if nuke_path:
                    config_path = Path(nuke_path) / "toolchains.json"
                    if config_path.exists():
                        with open(config_path, 'r') as f:
                            config = json.load(f)
                            template_tools_config = config.get("toolchains", {}).get("TemplateTools", {})
                            template_root_config = template_tools_config.get("config", {}).get("template_root", {})
                            current_platform = "windows" if platform.system() == "Windows" else "mac"
                            template_path = template_root_config.get(current_platform)
                            
                            if template_path and not Path(template_path).exists():
                                Path(template_path).mkdir(parents=True, exist_ok=True)
                                
            except Exception as e:
                debug_print(f"Could not load template directory from config: {e}")
            
            if not template_path or not Path(template_path).exists():
                error_item = QTreeWidgetItem(["No Template Directory Configured"])
                error_item.setIcon(0, self.nuke_icon)
                error_item.setData(0, Qt.UserRole, {"type": "error"})
                self.template_tree.addTopLevelItem(error_item)
                debug_print("No template directory found in toolchain configuration")
                return
            
            folder_path = Path(template_path)
            
            # Create root item for template directory
            root_item = QTreeWidgetItem(["Template Library"])
            root_item.setIcon(0, self.folder_icon)
            root_item.setData(0, Qt.UserRole, {"type": "root", "path": str(folder_path)})
            self.template_tree.addTopLevelItem(root_item)
            
            # Process categories
            for category_dir in folder_path.iterdir():
                if not category_dir.is_dir():
                    continue
                
                category_item = QTreeWidgetItem([category_dir.name.title()])
                category_item.setIcon(0, self.folder_icon)
                category_item.setData(0, Qt.UserRole, {"type": "category", "path": str(category_dir)})
                root_item.addChild(category_item)
                
                # Process template folders (new structure) and individual .nk files (legacy)
                template_folders = [d for d in category_dir.iterdir() if d.is_dir()]
                nk_files = list(category_dir.glob("*.nk"))
                
                # Process new folder-based templates
                for template_folder in template_folders:
                    nk_files_in_folder = list(template_folder.glob("*.nk"))
                    if nk_files_in_folder:
                        nk_file = nk_files_in_folder[0]
                        template_name = template_folder.name
                        template_item = QTreeWidgetItem([template_name])
                        template_item.setIcon(0, self.nuke_icon)
                        
                        # Look for MP4 in the template folder
                        mp4_files = list(template_folder.glob("*.mp4"))
                        mp4_path = str(mp4_files[0]) if mp4_files else str(template_folder / f"{template_name}.mp4")
                        
                        template_data = {
                            "type": "template",
                            "nk_path": str(nk_file),
                            "mp4_path": mp4_path,
                            "name": template_name,
                            "category": category_dir.name
                        }
                        template_item.setData(0, Qt.UserRole, template_data)
                        category_item.addChild(template_item)
                
                # Process legacy flat .nk files
                for nk_file in nk_files:
                    template_name = nk_file.stem
                    template_item = QTreeWidgetItem([template_name])
                    template_item.setIcon(0, self.nuke_icon)
                    
                    template_data = {
                        "type": "template",
                        "nk_path": str(nk_file),
                        "mp4_path": str(nk_file.with_suffix(".mp4")),
                        "name": template_name,
                        "category": category_dir.name
                    }
                    template_item.setData(0, Qt.UserRole, template_data)
                    category_item.addChild(template_item)
            
            root_item.setExpanded(True)
            
            # Build tag dictionary for search functionality
            self.build_tag_dictionary()
                
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to load templates: {str(e)}")
            debug_print(f"Error loading templates: {e}")
    
    def filter_templates(self, text):
        """Filter templates based on search text and tags."""
        def filter_item(item):
            text_lower = text.lower()
            item_text = item.text(0).lower()
            matches = text_lower in item_text
            
            # Check if this is a template item and search in tags
            data = item.data(0, Qt.UserRole)
            if data and data.get("type") == "template":
                # Check if search text matches any tags
                template_name = data.get("name", "")
                if hasattr(self, 'tag_to_templates'):
                    for tag, templates in self.tag_to_templates.items():
                        if text_lower in tag.lower() and template_name in templates:
                            matches = True
                            break
            
            # Check children
            for i in range(item.childCount()):
                child = item.child(i)
                if filter_item(child):
                    matches = True
            
            item.setHidden(not matches)
            return matches
        
        for i in range(self.template_tree.topLevelItemCount()):
            item = self.template_tree.topLevelItem(i)
            filter_item(item)
    
    def on_template_selected(self):
        """Handle template or category selection."""
        current_item = self.template_tree.currentItem()
        if not current_item:
            self.load_button.setEnabled(False)
            self.clear_preview()
            return
        
        data = current_item.data(0, Qt.UserRole)
        if not data:
            self.load_button.setEnabled(False)
            self.clear_preview()
            return
        
        item_type = data.get("type")
        
        if item_type == "template":
            self.load_button.setText("Load Selected Template")
            self.load_button.setEnabled(True)
            self.show_template_preview(data)
        elif item_type == "category":
            self.load_button.setText("Load Category as Contact Sheet")
            self.load_button.setEnabled(True)
            self.show_category_preview(data)
        else:
            self.load_button.setEnabled(False)
            self.clear_preview()
    
    def show_template_preview(self, template_data):
        """Show preview for the selected template."""
        template_name = template_data["name"]
        category = template_data["category"]
        nk_path = template_data["nk_path"]
        mp4_path = template_data["mp4_path"]
        
        # Check for video
        mp4_exists = Path(mp4_path).exists()
        if mp4_exists:
            self.current_video_path = mp4_path
            self.video_button.setVisible(True)
            self.load_frame_preview(mp4_path, nk_path)
        else:
            self.current_video_path = None
            self.video_button.setVisible(False)
            self.show_no_preview()
        
        # Load and display tags for the template
        self.display_template_tags(template_data)
    
    def show_category_preview(self, category_data):
        """Show preview for a selected category with contact icon background."""
        category_path = Path(category_data["path"])
        category_name = category_path.name
        
        # Count templates in category
        template_count = 0
        
        # Count folder-based templates
        for template_folder in category_path.iterdir():
            if template_folder.is_dir():
                nk_files = list(template_folder.glob("*.nk"))
                if nk_files:
                    template_count += 1
        
        # Count legacy flat .nk files
        nk_files = list(category_path.glob("*.nk"))
        template_count += len(nk_files)
        
        # Create category preview
        if self.contact_icon_path and Path(self.contact_icon_path).exists():
            self.create_category_preview_with_background(category_name, template_count)
        else:
            self.create_category_preview_text_only(category_name, template_count)
        
        # Hide video preview button for categories
        self.current_video_path = None
        self.video_button.setVisible(False)
        
        # Clear tags and description for categories
        if hasattr(self, 'tags_layout'):
            for i in reversed(range(self.tags_layout.count())):
                child = self.tags_layout.takeAt(i)
                if child.widget():
                    child.widget().deleteLater()
        
        if hasattr(self, 'description_content'):
            self.description_content.setText("Categories do not have descriptions")
            self.description_content.setStyleSheet("""
                QLabel {
                    color: #888;
                    font-style: italic;
                    padding: 5px;
                    background-color: #2a2a2a;
                    border-radius: 3px;
                    font-size: 11px;
                }
            """)
    
    def create_category_preview_with_background(self, category_name, template_count):
        """Create category preview with contact icon background and text overlay."""
        try:
            # Load the contact icon as background
            background_pixmap = QPixmap(self.contact_icon_path)
            if background_pixmap.isNull():
                debug_print(f"Failed to load contact icon: {self.contact_icon_path}")
                self.create_category_preview_text_only(category_name, template_count)
                return
            
            # Get label size for scaling
            label_size = self.preview_label.size()
            
            # Scale background to fit preview area while maintaining aspect ratio
            scaled_background = background_pixmap.scaled(
                label_size.width() - 4,
                label_size.height() - 4,
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )
            
            # Create a new pixmap to draw text overlay on
            overlay_pixmap = QPixmap(scaled_background.size())
            overlay_pixmap.fill(Qt.transparent)
            
            # Set up painter for text overlay
            if PYSIDE_VERSION == 6:
                from PySide6.QtGui import QPainter, QPen, QBrush, QColor
                from PySide6.QtCore import QRect
            elif PYSIDE_VERSION == 2:
                from PySide2.QtGui import QPainter, QPen, QBrush, QColor
                from PySide2.QtCore import QRect
            elif PYSIDE_VERSION == 1:
                from PySide.QtGui import QPainter, QPen, QBrush, QColor
                from PySide.QtCore import QRect
            else:
                from Qt.QtGui import QPainter, QPen, QBrush, QColor
                from Qt.QtCore import QRect
            
            painter = QPainter(overlay_pixmap)
            painter.setRenderHint(QPainter.Antialiasing)
            
            # Draw the background image first
            painter.drawPixmap(0, 0, scaled_background)
            
            # Set up text properties
            font = QFont("Arial", 11, QFont.Bold)
            painter.setFont(font)
            
            # Create text
            template_word = "Template" if template_count == 1 else "Templates"
            text_lines = [
                f"Category - {category_name.upper()} : {template_count} {template_word}"
            ]
            
            # Calculate text position (align at bottom with margin)
            line_height = 16
            total_text_height = len(text_lines) * line_height
            start_y = overlay_pixmap.height() - total_text_height - 20
            
            # Draw text with outline for better visibility
            for i, line in enumerate(text_lines):
                if not line:
                    continue
                    
                y_pos = start_y + (i * line_height)
                text_rect = QRect(10, y_pos, overlay_pixmap.width() - 20, line_height)
                
                # Draw text outline (black)
                painter.setPen(QPen(QColor(0, 0, 0), 2))
                painter.drawText(text_rect, Qt.AlignCenter, line)
                
                # Draw text fill (white)
                painter.setPen(QPen(QColor(255, 255, 255), 1))
                painter.drawText(text_rect, Qt.AlignCenter, line)
            
            painter.end()
            
            # Set the final pixmap to the label
            self.preview_label.setPixmap(overlay_pixmap)
            self.preview_label.setStyleSheet("""
                QLabel {
                    background-color: #1a1a1a;
                    border-radius: 5px;
                }
            """)
            
            debug_print(f"Category preview created with contact icon background: {category_name}")
            
        except Exception as e:
            debug_print(f"Error creating category preview with background: {e}")
            self.create_category_preview_text_only(category_name, template_count)
    
    def create_category_preview_text_only(self, category_name, template_count):
        """Create text-only category preview as fallback."""
        template_word = "Template" if template_count == 1 else "Templates"
        preview_text = f"Category - {category_name.upper()} : {template_count} {template_word}"
        self.preview_label.clear()
        self.preview_label.setText(preview_text)
        self.preview_label.setStyleSheet("""
            QLabel {
                background-color: #1a1a1a;
                border-radius: 5px;
                color: #4a90e2;
                font-size: 12px;
                padding: 20px;
            }
        """)

    def load_frame_preview(self, video_path, nk_path):
        """Extract and display frame preview from MP4 with persistent caching."""
        try:
            # Create persistent thumbnail path
            nk_file = Path(nk_path)
            persistent_thumbnail = nk_file.with_suffix('.png')
            
            # Check if persistent thumbnail already exists
            if persistent_thumbnail.exists():
                debug_print(f"Using cached thumbnail: {persistent_thumbnail.name}")
                self.display_preview_image(str(persistent_thumbnail))
                return
            
            # Check for existing PNG thumbnail in the template folder
            if nk_file.parent != nk_file.parent.parent:
                folder_thumbnail = nk_file.parent / f"{nk_file.parent.name}.png"
                if folder_thumbnail.exists():
                    debug_print(f"Using existing folder thumbnail: {folder_thumbnail.name}")
                    self.display_preview_image(str(folder_thumbnail))
                    return
            
            # No cached thumbnail, extract from video using FFmpeg
            video_name = Path(video_path).name
            debug_print(f"Creating new thumbnail from video: {video_name}")
            
            # Verify video file exists
            if not Path(video_path).exists():
                debug_print(f"Video file not found: {video_path}")
                self.show_no_preview("Video file not found")
                return
                
            # Create temporary path for extraction
            video_stem = os.path.splitext(os.path.basename(video_path))[0]
            temp_frame_path = os.path.join(self.temp_dir, f"{video_stem}_preview.png")
            
            # Extract frame using FFmpeg
            if VideoPreviewUtils.extract_middle_frame(video_path, temp_frame_path):
                # Successfully extracted, now save as persistent thumbnail
                try:
                    shutil.copy2(temp_frame_path, str(persistent_thumbnail))
                    debug_print(f"Thumbnail cached for future use: {persistent_thumbnail.name}")
                    
                    # Display the cached version
                    self.display_preview_image(str(persistent_thumbnail))
                    
                except Exception as e:
                    debug_print(f"Warning: Could not save persistent thumbnail: {e}")
                    # Fall back to displaying the temp version
                    self.display_preview_image(temp_frame_path)
            else:
                debug_print(f"FFmpeg frame extraction failed for: {video_name}")
                self.show_no_preview("FFmpeg frame extraction failed")
                
        except Exception as e:
            debug_print(f"Error loading frame preview: {e}")
            self.show_no_preview("Error extracting frame")
    
    def display_preview_image(self, image_path):
        """Display a preview image from the given path."""
        try:
            # Store current image path for resize handling
            self.current_preview_image = image_path
            
            # Verify image file exists
            if not os.path.exists(image_path):
                debug_print(f"Preview image file not found: {image_path}")
                self.show_no_preview("Preview image not found")
                return
                
            # Load and display the frame
            pixmap = QPixmap(image_path)
            if not pixmap.isNull():
                # Scale to fit the preview area while maintaining aspect ratio
                label_size = self.preview_label.size()
                scaled_pixmap = pixmap.scaled(
                    label_size.width() - 4,
                    label_size.height() - 4,
                    Qt.KeepAspectRatio, 
                    Qt.SmoothTransformation
                )
                self.preview_label.setPixmap(scaled_pixmap)
                self.preview_label.setStyleSheet("""
                    QLabel {
                        background-color: #1a1a1a;
                        border-radius: 5px;
                    }
                """)
                debug_print(f"Preview image displayed: {image_path}")
            else:
                debug_print(f"Failed to load pixmap from: {image_path}")
                self.show_no_preview("Failed to load image file")
        except Exception as e:
            debug_print(f"Error displaying preview image: {e}")
            self.show_no_preview("Error displaying preview")
    
    def show_no_preview(self, message="No preview available"):
        """Show no preview message."""
        self.current_preview_image = None
        self.preview_label.clear()
        self.preview_label.setText(message)
        self.preview_label.setStyleSheet("""
            QLabel {
                background-color: #1a1a1a;
                border-radius: 5px;
                color: #ccc;
            }
        """)
    
    def clear_preview(self):
        """Clear preview content."""
        self.show_no_preview("Select a template to see preview")
        self.current_video_path = None
        self.video_button.setVisible(False)
        
        # Clear tags display
        if hasattr(self, 'tags_layout'):
            for i in reversed(range(self.tags_layout.count())):
                child = self.tags_layout.takeAt(i)
                if child.widget():
                    child.widget().deleteLater()
        
        # Clear description display
        if hasattr(self, 'description_content'):
            self.description_content.setText("Select a template to see description")
            self.description_content.setStyleSheet("""
                QLabel {
                    color: #888;
                    font-style: italic;
                    padding: 5px;
                    background-color: #2a2a2a;
                    border-radius: 3px;
                    font-size: 11px;
                }
            """)
    
    def open_video_externally(self):
        """Open video in system default player."""
        if not self.current_video_path:
            return
        
        try:
            if platform.system() == "Windows":
                subprocess.Popen(['start', '', self.current_video_path], shell=True)
            elif platform.system() == "Darwin":
                subprocess.Popen(['open', self.current_video_path])
            else:
                subprocess.Popen(['xdg-open', self.current_video_path])
            debug_print(f"Opened video externally: {self.current_video_path}")
        except Exception as e:
            debug_print(f"Failed to open video externally: {e}")
    
    def frame_all_nodes(self):
        """Frame all nodes in the node graph after loading templates."""
        try:
            all_nodes = nuke.allNodes()
            if all_nodes:
                nuke.selectAll()
                nuke.zoomToFitSelected()
                for node in all_nodes:
                    node.setSelected(False)
            else:
                debug_print("No nodes to frame in the node graph")
        except Exception as e:
            debug_print(f"Warning: Could not frame all nodes: {e}")
    
    def load_selected_template(self):
        """Load the selected template or category as contact sheet."""
        current_item = self.template_tree.currentItem()
        if not current_item:
            return
        
        data = current_item.data(0, Qt.UserRole)
        if not data:
            return
        
        item_type = data.get("type")
        
        if item_type == "template":
            # Load individual template
            nk_path = data["nk_path"]
            template_name = data["name"]
            
            try:
                if self.template_library:
                    self.template_library.import_single_template(nk_path)
                    debug_print(f"Template '{template_name}' loaded successfully")
                    
                    # Frame all nodes in the node graph after loading
                    self.frame_all_nodes()
                    
                    self.close()
                else:
                    debug_print(f"Template library not available - would load: {nk_path}")
            except Exception as e:
                QMessageBox.critical(
                    self, 
                    "Error Loading Template", 
                    f"Failed to load template '{template_name}':\n\n{str(e)}"
                )
        
        elif item_type == "category":
            # Load category as contact sheet
            category_path = data["path"]
            category_name = Path(category_path).name
            
            try:
                if self.template_library:
                    self.template_library.import_category_as_contact_sheet(
                        category_path, 
                        backdrop_label=category_name.upper()
                    )
                    debug_print(f"Category '{category_name}' loaded as contact sheet successfully")
                    
                    # Frame all nodes in the node graph after loading
                    self.frame_all_nodes()
                    
                    self.close()
                else:
                    debug_print(f"Template library not available - would load category: {category_path}")
            except Exception as e:
                QMessageBox.critical(
                    self, 
                    "Error Loading Category", 
                    f"Failed to load category '{category_name}' as contact sheet:\n\n{str(e)}"
                )
    
    def closeEvent(self, event):
        """Clean up temporary files on close."""
        try:
            if hasattr(self, 'temp_dir') and os.path.exists(self.temp_dir):
                shutil.rmtree(self.temp_dir, ignore_errors=True)
                debug_print(f"Cleaned up temporary directory: {self.temp_dir}")
        except Exception as e:
            debug_print(f"Error cleaning up temp files: {e}")
        event.accept()
    
    def load_template_metadata(self, template_data):
        """Load metadata from JSON file for a template."""
        try:
            template_name = template_data["name"]
            category = template_data["category"]
            
            # Construct metadata path
            nk_path = Path(template_data["nk_path"])
            metadata_path = nk_path.with_suffix('.json')
            
            if metadata_path.exists():
                with open(metadata_path, 'r') as f:
                    metadata = json.load(f)
                return metadata
            else:
                debug_print(f"No metadata file found for template: {template_name}")
                return None
                
        except Exception as e:
            debug_print(f"Error loading metadata for template: {e}")
            return None
    
    def build_tag_dictionary(self):
        """Build a dictionary of all tags from all templates for search functionality."""
        self.tag_to_templates = {}
        
        try:
            template_path = self.template_library.template_root
            if not template_path or not Path(template_path).exists():
                return
                
            folder_path = Path(template_path)
            
            # Process all categories
            for category_dir in folder_path.iterdir():
                if not category_dir.is_dir():
                    continue
                
                # Process template folders
                for template_folder in category_dir.iterdir():
                    if template_folder.is_dir():
                        nk_files = list(template_folder.glob("*.nk"))
                        if nk_files:
                            template_data = {
                                "name": template_folder.name,
                                "category": category_dir.name,
                                "nk_path": str(nk_files[0])
                            }
                            
                            metadata = self.load_template_metadata(template_data)
                            if metadata and 'template_info' in metadata and 'tags' in metadata['template_info']:
                                tags = metadata['template_info']['tags']
                                for tag in tags:
                                    if tag not in self.tag_to_templates:
                                        self.tag_to_templates[tag] = []
                                    self.tag_to_templates[tag].append(template_folder.name)
                
                # Process legacy flat .nk files
                for nk_file in category_dir.glob("*.nk"):
                    template_data = {
                        "name": nk_file.stem,
                        "category": category_dir.name,
                        "nk_path": str(nk_file)
                    }
                    
                    metadata = self.load_template_metadata(template_data)
                    if metadata and 'template_info' in metadata and 'tags' in metadata['template_info']:
                        tags = metadata['template_info']['tags']
                        for tag in tags:
                            if tag not in self.tag_to_templates:
                                self.tag_to_templates[tag] = []
                            self.tag_to_templates[tag].append(nk_file.stem)
                            
        except Exception as e:
            debug_print(f"Error building tag dictionary: {e}")
    
    def display_template_tags(self, template_data):
        """Display tags and description for the selected template."""
        # Clear existing tags
        for i in reversed(range(self.tags_layout.count())):
            child = self.tags_layout.takeAt(i)
            if child.widget():
                child.widget().deleteLater()
        
        # Load template metadata
        metadata = self.load_template_metadata(template_data)
        if metadata and 'template_info' in metadata and 'tags' in metadata['template_info']:
            tags = metadata['template_info']['tags']
            
            # Import MetaDataButton from widgets
            from lib.widgets import MetaDataButton
            
            # Create tag buttons
            for tag in tags:
                tag_button = MetaDataButton(text=tag)
                tag_button.clicked.connect(lambda checked=False, t=tag: self.on_tag_clicked(t))
                self.tags_layout.addWidget(tag_button)
        else:
            # Show "No tags" message
            no_tags_label = QLabel("No tags available")
            no_tags_label.setStyleSheet("color: #888; font-style: italic;")
            self.tags_layout.addWidget(no_tags_label)
        
        # Display description
        if metadata and 'template_info' in metadata and 'description' in metadata['template_info']:
            description = metadata['template_info']['description']
            if description and description.strip():
                self.description_content.setText(description.strip())
                self.description_content.setStyleSheet("""
                    QLabel {
                        color: #ccc;
                        font-style: normal;
                        padding: 5px;
                        background-color: #2a2a2a;
                        border-radius: 3px;
                        font-size: 11px;
                    }
                """)
            else:
                self.description_content.setText("No description available")
                self.description_content.setStyleSheet("""
                    QLabel {
                        color: #888;
                        font-style: italic;
                        padding: 5px;
                        background-color: #2a2a2a;
                        border-radius: 3px;
                        font-size: 11px;
                    }
                """)
        else:
            self.description_content.setText("No description available")
            self.description_content.setStyleSheet("""
                QLabel {
                    color: #888;
                    font-style: italic;
                    padding: 5px;
                    background-color: #2a2a2a;
                    border-radius: 3px;
                    font-size: 11px;
                }
            """)
    
    def on_tag_clicked(self, tag):
        """Handle tag button click - replace search field with tag."""
        self.search_box.setText(tag)
        debug_print(f"Set search to tag: {tag}")
        self.filter_templates(tag)
    
    def clear_search(self):
        """Clear the search field."""
        self.search_box.clear()
        debug_print("Search field cleared")
    
    def show_context_menu(self, position):
        """Show context menu for tree widget items."""
        item = self.template_tree.itemAt(position)
        if not item:
            return
        
        data = item.data(0, Qt.UserRole)
        if not data:
            return
        
        # Create context menu
        menu = QMenu(self)
        
        item_type = data.get("type")
        
        if item_type == "category":
            # Category/folder level - show "Explore Here" option
            explore_action = QAction("Explore Here", self)
            explore_action.setIcon(self.folder_icon)
            explore_action.triggered.connect(lambda: self.open_folder_in_explorer(data["path"]))
            menu.addAction(explore_action)
            
        elif item_type == "template":
            # Template/nuke file level - show "Open in new Nuke window" option
            open_nuke_action = QAction("Open in new Nuke window", self)
            open_nuke_action.setIcon(self.nuke_icon)
            open_nuke_action.triggered.connect(lambda: self.open_template_in_new_nuke(data["nk_path"]))
            menu.addAction(open_nuke_action)
            
            # Add separator
            menu.addSeparator()
            
            # Also add "Explore Here" to navigate to the template folder
            template_folder = Path(data["nk_path"]).parent
            explore_action = QAction("Explore Here", self)
            explore_action.setIcon(self.folder_icon)
            explore_action.triggered.connect(lambda: self.open_folder_in_explorer(str(template_folder)))
            menu.addAction(explore_action)
        
        # Show context menu at cursor position
        menu.exec_(self.template_tree.mapToGlobal(position))
    
    def open_folder_in_explorer(self, folder_path):
        """Open the specified folder in the system file explorer."""
        try:
            if not Path(folder_path).exists():
                debug_print(f"Folder does not exist: {folder_path}")
                QMessageBox.warning(self, "Error", f"Folder does not exist:\n{folder_path}")
                return
            
            if platform.system() == "Windows":
                subprocess.Popen(['explorer', folder_path])
                debug_print(f"Opened folder in Explorer: {folder_path}")
            elif platform.system() == "Darwin":
                subprocess.Popen(['open', folder_path])
                debug_print(f"Opened folder in Finder: {folder_path}")
            else:
                subprocess.Popen(['xdg-open', folder_path])
                debug_print(f"Opened folder in file manager: {folder_path}")
                
        except Exception as e:
            debug_print(f"Error opening folder in explorer: {e}")
            QMessageBox.warning(self, "Error", f"Failed to open folder in explorer:\n{str(e)}")
    
    def open_template_in_new_nuke(self, nk_path):
        """Open the template in a new Nuke window using file association."""
        try:
            if not Path(nk_path).exists():
                debug_print(f"Template file does not exist: {nk_path}")
                QMessageBox.warning(self, "Error", f"Template file does not exist:\n{nk_path}")
                return
            
            # Use file association to open .nk file with associated application (Nuke)
            if platform.system() == "Windows":
                # On Windows, use os.startfile for file association
                os.startfile(nk_path)
                debug_print(f"Opened template using file association: {nk_path}")
            elif platform.system() == "Darwin":
                # On macOS, use 'open' command
                subprocess.Popen(['open', nk_path])
                debug_print(f"Opened template using macOS 'open': {nk_path}")
            else:
                # On Linux, use 'xdg-open'
                subprocess.Popen(['xdg-open', nk_path])
                debug_print(f"Opened template using Linux 'xdg-open': {nk_path}")
            
        except Exception as e:
            debug_print(f"Error opening template in new Nuke window: {e}")
            QMessageBox.warning(self, "Error", f"Failed to open template in new Nuke window:\n{str(e)}")
    
    def get_nuke_executable(self):
        """Get the path to the Nuke executable."""
        try:
            # Try to get from environment variable first
            nuke_exe = os.environ.get('NUKE_EXECUTABLE')
            if nuke_exe and Path(nuke_exe).exists():
                return nuke_exe
            
            # Try to determine from current Nuke process
            if hasattr(nuke, 'env') and 'ExecutablePath' in nuke.env:
                nuke_exe = nuke.env['ExecutablePath']
                if Path(nuke_exe).exists():
                    return nuke_exe
            
            # Try common installation paths
            if platform.system() == "Windows":
                common_paths = [
                    r"C:\Program Files\Nuke*\Nuke*.exe",
                    r"C:\Program Files (x86)\Nuke*\Nuke*.exe",
                ]
                
                import glob
                for pattern in common_paths:
                    matches = glob.glob(pattern)
                    if matches:
                        return max(matches)
            
            elif platform.system() == "Darwin":
                common_paths = [
                    "/Applications/Nuke*/Nuke*.app/Contents/MacOS/Nuke*",
                ]
                
                import glob
                for pattern in common_paths:
                    matches = glob.glob(pattern)
                    if matches:
                        return max(matches)
            
            else:
                common_paths = [
                    "/usr/local/Nuke*/Nuke*",
                    "/opt/Nuke*/Nuke*",
                ]
                
                import glob
                for pattern in common_paths:
                    matches = glob.glob(pattern)
                    if matches:
                        return max(matches)
            
            # If nothing found, try 'nuke' command
            try:
                result = subprocess.run(['which', 'nuke'], capture_output=True, text=True)
                if result.returncode == 0:
                    return result.stdout.strip()
            except:
                pass
            
            return None
            
        except Exception as e:
            debug_print(f"Error getting Nuke executable: {e}")
            return None
    
    def resizeEvent(self, event):
        """Handle window resize events to maintain preview aspect ratio."""
        super().resizeEvent(event)
        
        # Trigger the preview widget's resize event if it exists
        if hasattr(self, 'preview_widget') and hasattr(self.preview_widget, 'resizeEvent'):
            # Create a dummy event to trigger the preview widget resize
            dummy_event = event
            self.preview_widget.resizeEvent(dummy_event)


def show_template_loader():
    """Show the simplified template loader."""
    try:
        # Get Nuke's main window for proper parenting
        parent = get_nuke_main_window()
        
        # Create and show window
        window = TemplateLoaderWindow(parent)
        window.show()
        window.raise_()
        window.activateWindow()
        
        debug_print("Template Loader opened")
        return window
        
    except Exception as e:
        debug_print(f"Error showing template loader: {e}")
        return None


# Global reference to prevent garbage collection
_template_loader_window = None

def show_template_loader_global():
    """Show template loader with global reference."""
    global _template_loader_window
    
    try:
        # Close existing window
        if _template_loader_window is not None:
            try:
                _template_loader_window.close()
            except:
                pass
        
        # Create new window
        _template_loader_window = show_template_loader()
        return _template_loader_window
        
    except Exception as e:
        debug_print(f"Error showing template loader: {e}")
        return None


if __name__ == "__main__":
    # For testing outside Nuke
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    
    window = TemplateLoaderWindow()
    window.show()
    app.exec_()
