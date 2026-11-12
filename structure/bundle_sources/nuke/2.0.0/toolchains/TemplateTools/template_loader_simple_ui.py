"""
Simple Template Loader UI

Ultra-simplified Qt-based template browser with only category dropdown and load button.
Contact sheet loading mode only - no individual template loading.

Author: Pipeline Team
Date: August 2025
"""

import sys
import os
import json
import platform
import traceback
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
            QPushButton, QLabel, QComboBox, QDialog, QMessageBox, QGroupBox, QMenu, QAction
        )
        from PySide6.QtCore import Qt, QSize
        from PySide6.QtGui import QFont, QIcon
        PYSIDE_VERSION = 6
    elif nuke.NUKE_VERSION_MAJOR < 11:
        from PySide.QtGui import (
            QApplication, QWidget, QVBoxLayout, QHBoxLayout,
            QPushButton, QLabel, QComboBox, QDialog, QMessageBox, QGroupBox, QMenu, QAction
        )
        from PySide.QtCore import Qt, QSize
        from PySide.QtGui import QFont, QIcon
        PYSIDE_VERSION = 1
    else:
        from PySide2.QtWidgets import (
            QApplication, QWidget, QVBoxLayout, QHBoxLayout,
            QPushButton, QLabel, QComboBox, QDialog, QMessageBox, QGroupBox, QMenu, QAction
        )
        from PySide2.QtCore import Qt, QSize
        from PySide2.QtGui import QFont, QIcon
        PYSIDE_VERSION = 2
    QT_AVAILABLE = True
except ImportError:
    try:
        # Fallback: try using the Qt.py abstraction if available
        from Qt import QtWidgets, QtCore, QtGui
        from Qt.QtWidgets import (
            QApplication, QWidget, QVBoxLayout, QHBoxLayout,
            QPushButton, QLabel, QComboBox, QDialog, QMessageBox, QGroupBox, QMenu, QAction
        )
        from Qt.QtCore import Qt, QSize
        from Qt.QtGui import QFont, QIcon
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
        sys.stderr.write(f"[SimpleTemplateLoader] {msg_str}\n")
        sys.stderr.flush()
    except Exception:
        pass


def get_nuke_main_window():
    """Get the main Qt window of Nuke."""
    for widget in QApplication.topLevelWidgets():
        if widget.metaObject().className() == "Foundry::UI::DockMainWindow":
            return widget
    return None


class CustomDropdown(QPushButton):
    """Custom dropdown widget that looks like a combobox but with full control over appearance."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.items = []
        self.current_index = -1
        self.folder_icon = None
        
        # Load folder icon
        self.load_folder_icon()
        
        # Set up the button appearance
        self.setText("Select a Category...")
        self.setMinimumHeight(24)
        self.setStyleSheet("""
            QPushButton {
                font-size: 10x;
                padding: 6px;
                text-align: left;
                background-color: #3a3a3a;
                color: white;
                border: 1px solid #555;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #4a4a4a;
                border: 1px solid #666;
            }
            QPushButton:pressed {
                background-color: #2a2a2a;
            }
            QPushButton::menu-indicator {
                image: none;
                width: 0px;
            }
        """)
        
        # Add dropdown arrow manually
        self.update_button_text()
    
    def load_folder_icon(self):
        """Load folder icon from the pipeline icons."""
        try:
            nuke_path = os.environ.get('TLA_COMP_CORE')
            if nuke_path:
                icons_dir = Path(nuke_path) / "icons"
                folder_icon_path = icons_dir / "folder.png"
                if folder_icon_path.exists():
                    self.folder_icon = QIcon(str(folder_icon_path))
                    debug_print(f"Loaded folder icon from: {folder_icon_path}")
        except Exception as e:
            debug_print(f"Could not load folder icon: {e}")
    
    def add_item(self, text, data=None):
        """Add an item to the dropdown."""
        self.items.append({"text": text, "data": data})
    
    def clear(self):
        """Clear all items."""
        self.items = []
        self.current_index = -1
        self.update_button_text()
    
    def update_button_text(self):
        """Update the button text with current selection and dropdown arrow."""
        if self.current_index >= 0 and self.current_index < len(self.items):
            text = self.items[self.current_index]["text"]
        else:
            text = "-- Select a Category --"
        
        # Add dropdown arrow
        self.setText(f"{text}  ▼")
    
    def set_current_index(self, index):
        """Set the current selected index."""
        if 0 <= index < len(self.items):
            self.current_index = index
            self.update_button_text()
    
    def current_data(self):
        """Get the data for the current selection."""
        if self.current_index >= 0 and self.current_index < len(self.items):
            return self.items[self.current_index]["data"]
        return None
    
    def mousePressEvent(self, event):
        """Handle mouse press to show dropdown menu."""
        if event.button() == Qt.LeftButton:
            self.show_dropdown()
        super().mousePressEvent(event)
    
    def show_dropdown(self):
        """Show the dropdown menu."""
        if not self.items:
            return
        
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #3a3a3a;
                color: white;
                border: 1px solid #555;
                padding: 2px;
            }
            QMenu::item {
                padding: 4px 25px 4px 25px;
                border: none;
                background-color: transparent;
            }
            QMenu::item:selected {
                background-color: #4a90e2;
            }
            QMenu::item:disabled {
                color: #888;
            }
        """)
        
        for i, item in enumerate(self.items):
            action = QAction(item["text"], self)
            
            # Add folder icon for category items (skip the first "Select Category" item)
            if i > 0 and self.folder_icon and item["data"] is not None:
                action.setIcon(self.folder_icon)
            
            # Connect to selection handler - use a proper closure to capture the index
            def make_handler(index):
                return lambda: self.on_item_selected(index)
            
            action.triggered.connect(make_handler(i))
            
            # Disable the "Select Category" item
            if i == 0:
                action.setEnabled(False)
            
            menu.addAction(action)
        
        # Show menu below the button
        menu.exec_(self.mapToGlobal(self.rect().bottomLeft()))
    
    def on_item_selected(self, index):
        """Handle item selection."""
        if 0 <= index < len(self.items):
            old_index = self.current_index
            self.current_index = index
            self.update_button_text()
            
            # Emit a signal-like behavior (call connected functions)
            if hasattr(self, '_selection_callback') and self._selection_callback:
                self._selection_callback()
    
    def connect_selection_changed(self, callback):
        """Connect a callback function to selection changes."""
        self._selection_callback = callback


class SimpleTemplateLoaderWindow(QDialog):
    """Ultra-simplified template loader with category dropdown and load button only."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Set proper window flags to ensure correct stacking order
        self.setWindowFlags(Qt.Dialog | Qt.WindowCloseButtonHint)
        
        try:
            from template_library import TemplateLibrary
            self.template_library = TemplateLibrary()
        except ImportError:
            self.template_library = None
        
        self.categories = []  # Store category data
        
        self.setWindowTitle(" ")
        self.setMinimumSize(330, 140)
        self.setMaximumSize(330, 140)  # Fixed size to match layout
        self.resize(330, 140)
        self.setAttribute(Qt.WA_DeleteOnClose)
        
        self.setup_ui()
        self.load_categories()
    
    def setup_ui(self):
        """Setup the ultra-simplified user interface."""
        main_layout = QVBoxLayout(self)
        
        # Header (fixed size)
        header_widget = self.create_header_widget()
        main_layout.addWidget(header_widget)
        
        # Category selection panel
        category_panel = self.create_category_panel()
        main_layout.addWidget(category_panel)
        
        # Load button (fixed size)
        load_button = self.create_load_button()
        main_layout.addWidget(load_button)
    
    def create_category_panel(self):
        """Create the category selection panel."""
        # Custom category dropdown with folder icons (no frame for cleaner look)
        self.category_dropdown = CustomDropdown()
        self.category_dropdown.connect_selection_changed(self.on_category_changed)
        
        return self.category_dropdown
    
    def create_header_widget(self):
        """Create styled header widget."""
        return ToolHeader(name='template_header', text='Template Loader')
    
    def create_load_button(self):
        """Create the load templates button."""
        self.load_button = QPushButton("Load Templates")
        self.load_button.clicked.connect(self.load_selected_category)
        self.load_button.setEnabled(False)
        self.load_button.setMinimumHeight(32)
        self.load_button.setStyleSheet("""
            QPushButton {
                font-size: 12px;
                font-weight: bold;
                padding: 4px;
                background-color: #4a90e2;
                color: white;
                border: none;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #357abd;
            }
            QPushButton:disabled {
                background-color: #666666;
                color: #999999;
            }
        """)
        return self.load_button
    
    def load_categories(self):
        """Load template categories into the dropdown."""
        self.category_dropdown.clear()
        self.categories = []
        
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
                            
                            if isinstance(template_root_config, dict):
                                # Determine platform
                                current_platform = "windows" if platform.system() == "Windows" else "mac"
                                template_path = template_root_config.get(current_platform)
                                debug_print(f"Found template path for {current_platform}: {template_path}")
                            
            except Exception as e:
                debug_print(f"Could not load template directory from config: {e}")
            
            if not template_path or not Path(template_path).exists():
                self.category_dropdown.add_item("No Template Directory Configured", None)
                debug_print("No template directory found in toolchain configuration")
                return
            
            folder_path = Path(template_path)
            
            # Add a default "Select Category" item
            self.category_dropdown.add_item("-- Select a Category --", None)
            self.categories.append(None)
            
            # Process categories
            category_folders = [d for d in folder_path.iterdir() if d.is_dir()]
            category_folders.sort(key=lambda x: x.name.lower())
            
            for category_dir in category_folders:
                # Count templates in this category
                template_count = 0
                
                # Count folder-based templates
                for template_folder in category_dir.iterdir():
                    if template_folder.is_dir():
                        nk_files_in_folder = list(template_folder.glob("*.nk"))
                        if nk_files_in_folder:
                            template_count += 1
                
                # Count legacy flat .nk files
                nk_files = list(category_dir.glob("*.nk"))
                template_count += len(nk_files)
                
                if template_count > 0:
                    # Parse display name for better readability
                    display_name = self.parse_display_name(category_dir.name)
                    combo_text = f"{display_name} ({template_count} templates)"
                    
                    category_data = {
                        "name": category_dir.name,
                        "display_name": display_name,
                        "path": str(category_dir),
                        "template_count": template_count
                    }
                    
                    self.category_dropdown.add_item(combo_text, category_data)
                    self.categories.append(category_data)
                    debug_print(f"Added category: {display_name} with {template_count} templates")
                else:
                    debug_print(f"Skipped empty category: {category_dir.name}")
            
            debug_print(f"Loaded {len(self.categories)-1} categories")  # -1 for the "Select Category" item
                
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to load template categories: {str(e)}")
            debug_print(f"Error loading categories: {e}")
    
    def parse_display_name(self, name):
        """Parse display name to make it more readable (same as toolchains.py)"""
        # First replace underscores with spaces
        display_name = name.replace('_', ' ')
        
        # Then split camelCase/PascalCase by inserting spaces before capitals
        import re
        display_name = re.sub(r'(?<=[a-z])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])', ' ', display_name)
        
        return display_name
    
    def on_category_changed(self):
        """Handle category selection change."""
        current_data = self.category_dropdown.current_data()
        
        if current_data is None:
            # "Select Category" item or invalid selection
            self.load_button.setEnabled(False)
        else:
            # Valid category selected
            self.load_button.setEnabled(True)
            debug_print(f"Selected category: {current_data['display_name']} ({current_data['template_count']} templates)")
    
    def load_selected_category(self):
        """Load the selected category as a contact sheet."""
        current_data = self.category_dropdown.current_data()
        
        if current_data is None:
            QMessageBox.warning(self, "No Selection", "Please select a template category first.")
            return
        
        category_path = Path(current_data["path"])
        
        try:
            if not self.template_library:
                QMessageBox.critical(self, "Error", "Template library not available.")
                return
            
            debug_print(f"Loading contact sheet for category: {current_data['display_name']}")
            
            # Load the contact sheet using the template library
            # Use import_category_as_contact_sheet which expects a category path
            success = self.template_library.import_category_as_contact_sheet(category_path, current_data['display_name'])
            
            # The method doesn't return a success value, so we assume it worked if no exception was raised
            debug_print(f"Successfully loaded contact sheet for {current_data['display_name']}")
            self.close()
                
        except Exception as e:
            error_msg = f"Error loading category '{current_data['display_name']}': {str(e)}"
            QMessageBox.critical(self, "Error", error_msg)
            debug_print(error_msg)
            import traceback
            traceback.print_exc()


def show_simple_template_loader():
    """Show the simple template loader window."""
    try:
        # Get Nuke's main window as parent for proper integration
        parent = get_nuke_main_window()
        
        # Create and show the window
        window = SimpleTemplateLoaderWindow(parent)
        window.show()
        window.raise_()
        window.activateWindow()
        
        return window
        
    except Exception as e:
        error_msg = f"Failed to open Simple Template Loader: {str(e)}"
        print(error_msg)
        
        try:
            if hasattr(nuke, 'message'):
                nuke.message(error_msg)
        except:
            pass
        
        import traceback
        traceback.print_exc()
        return None


# Global reference to keep window alive
simple_template_loader_window = None

def show_simple_template_loader_global():
    """Show the simple template loader window with global reference."""
    global simple_template_loader_window
    
    # Close existing window if open
    if simple_template_loader_window is not None:
        try:
            simple_template_loader_window.close()
        except:
            pass
        simple_template_loader_window = None
    
    # Create new window
    simple_template_loader_window = show_simple_template_loader()
    return simple_template_loader_window


if __name__ == "__main__":
    # For testing outside of Nuke
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    
    window = SimpleTemplateLoaderWindow()
    window.show()
    
    if not QApplication.instance():
        app.exec_()
