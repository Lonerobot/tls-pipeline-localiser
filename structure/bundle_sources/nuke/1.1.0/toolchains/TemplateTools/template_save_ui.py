"""
Template Save Dialog

Modern PySide-based dialog for saving templates with metadata support.
Uses the same UI framework as the template loader for consistency.

NOTE: UI fields are pre-filled with test values for development/testing.
Remove these default values before production deployment.

Author: Pipeline Team
Date: July 2025
"""

try:
    import nuke
    # PySide import switch:
    # - Use PySide6 if Nuke version is 16 or above.
    # - Use PySide2 if Nuke version is 11 or higher but below 16.
    # - Use legacy PySide if Nuke version is below 11.
    if hasattr(nuke, 'NUKE_VERSION_MAJOR') and nuke.NUKE_VERSION_MAJOR >= 16:
        from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QGroupBox, 
                                      QLabel, QLineEdit, QPushButton, QTextEdit, 
                                      QComboBox, QSpinBox, QCheckBox, QFormLayout,
                                      QMessageBox, QProgressBar, QFrame, QScrollArea, QWidget)
        from PySide6.QtCore import Qt, QThread, QObject, Signal
        from PySide6.QtGui import QFont, QPixmap, QIcon
        PYSIDE_VERSION = 6
    elif nuke.NUKE_VERSION_MAJOR < 11:
        from PySide.QtGui import (QDialog, QVBoxLayout, QHBoxLayout, QGroupBox, 
                                  QLabel, QLineEdit, QPushButton, QTextEdit, 
                                  QComboBox, QSpinBox, QCheckBox, QFormLayout,
                                  QMessageBox, QProgressBar, QFrame, QScrollArea, QWidget)
        from PySide.QtCore import Qt, QThread, QObject, Signal
        from PySide.QtGui import QFont, QPixmap, QIcon
        PYSIDE_VERSION = 1
    else:
        from PySide2.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QGroupBox, 
                                      QLabel, QLineEdit, QPushButton, QTextEdit, 
                                      QComboBox, QSpinBox, QCheckBox, QFormLayout,
                                      QMessageBox, QProgressBar, QFrame, QScrollArea, QWidget)
        from PySide2.QtCore import Qt, QThread, QObject, Signal
        from PySide2.QtGui import QFont, QPixmap, QIcon
        PYSIDE_VERSION = 2
except ImportError:
    try:
        # Fallback: try using the Qt.py abstraction if available
        from Qt.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QGroupBox, 
                                  QLabel, QLineEdit, QPushButton, QTextEdit, 
                                  QComboBox, QSpinBox, QCheckBox, QFormLayout,
                                  QMessageBox, QProgressBar, QFrame, QScrollArea, QWidget)
        from Qt.QtCore import Qt, QThread, QObject, Signal
        from Qt.QtGui import QFont, QPixmap, QIcon
        PYSIDE_VERSION = 0  # Unknown/abstraction
    except ImportError:
        raise ImportError("No Qt bindings found. Please install PySide2, PySide6, or Qt.py.")

from pathlib import Path
import json
import os
import tempfile
import shutil
import glob
import datetime
import nuke

# Import the custom header widget
from lib.widgets import ToolHeader

def debug_print(message):
    """Print debug messages."""
    print(f"[TemplateSaver] {message}")

class TemplateSaveWorker(QObject):
    """Worker thread for template saving operations."""
    
    progress_updated = Signal(int)
    status_updated = Signal(str)
    save_completed = Signal(bool, str)  # success, message
    hide_dialog = Signal()  # Signal to hide dialog during rendering
    show_dialog = Signal()  # Signal to show dialog after rendering
    
    def __init__(self, template_data, template_library):
        super().__init__()
        self.template_data = template_data
        self.template_library = template_library
    
    def save_template(self):
        """Save the template with progress updates."""
        try:
            self.status_updated.emit("Validating template data...")
            self.progress_updated.emit(10)
            
            # Extract data
            template_name = self.template_data['name']
            category = self.template_data['category']
            tags = self.template_data['tags']
            start_frame = self.template_data['start_frame']
            end_frame = self.template_data['end_frame']
            selected_nodes = self.template_data['selected_nodes']
            write_node = self.template_data['write_node']
            
            # Setup paths using new folder structure
            template_root = Path(self.template_library.template_root)
            category_path = template_root / category
            template_folder = category_path / template_name
            
            # Create directories
            template_folder.mkdir(parents=True, exist_ok=True)
            
            self.status_updated.emit("Setting up output paths...")
            self.progress_updated.emit(20)
            
            # Define output paths (new folder structure)
            nk_path = template_folder / f"{template_name}.nk"
            mp4_path = template_folder / f"{template_name}.mp4"
            assets_dir = template_folder / "assets"
            metadata_path = template_folder / f"{template_name}.json"
            
            # Create assets directory
            assets_dir.mkdir(exist_ok=True)
            
            self.status_updated.emit("Configuring write node for MP4 export...")
            self.progress_updated.emit(30)
            
            # Configure write node for MP4 output
            old_input = write_node.input(0)
            original_file = write_node["file"].value()
            original_colorspace = write_node["colorspace"].value()
            original_view = write_node["view"].value()
            
            # Temporarily add reformat for consistent MP4 output
            reformat = nuke.nodes.Reformat(format="HD_1080", pbb=True)
            reformat.setInput(0, old_input)
            write_node.setInput(0, reformat)
            
            # Configure write node
            try:
                self.template_library.configure_write_node(write_node, str(mp4_path))
            except Exception as e:
                raise Exception(f"Error configuring write node: {e}")
            
            self.status_updated.emit("Rendering MP4 preview...")
            self.progress_updated.emit(40)
            
            # Hide dialog during rendering to avoid UI conflicts
            self.hide_dialog.emit()
            
            # Render MP4
            try:
                nuke.execute(write_node.name(), start_frame, end_frame)
                self.progress_updated.emit(60)
            except Exception as e:
                raise Exception(f"MP4 render failed: {e}")
            finally:
                # Show dialog again after rendering
                self.show_dialog.emit()
                
                # Restore original setup
                write_node.setInput(0, old_input)
                write_node["file"].setValue(original_file)
                write_node["colorspace"].setValue(original_colorspace)
                write_node["view"].setValue(original_view)
                nuke.delete(reformat)
            
            self.status_updated.emit("Copying assets...")
            self.progress_updated.emit(70)
            
            # Copy assets and get mapping
            asset_mapping = self._copy_assets(assets_dir, selected_nodes)
            
            self.status_updated.emit("Removing write node from template...")
            self.progress_updated.emit(75)
            
            # Remove write node from selected nodes before saving template
            # The write node should not be part of the saved template
            nodes_to_save = [node for node in selected_nodes if node != write_node]
            debug_print(f"Excluding write node '{write_node.name()}' from template save")
            debug_print(f"Saving {len(nodes_to_save)} nodes (excluding write node)")
            
            self.status_updated.emit("Saving template nodes...")
            self.progress_updated.emit(80)
            
            # Save the template nodes with updated paths (excluding write node)
            self._save_template_nodes(nk_path, nodes_to_save, asset_mapping)
            
            self.status_updated.emit("Generating metadata...")
            self.progress_updated.emit(90)
            
            # Generate and save metadata (excluding write node)
            metadata = self._generate_metadata(template_name, tags, nodes_to_save, start_frame, end_frame, self.template_data['description'])
            self._save_metadata(metadata_path, metadata)
            
            self.status_updated.emit("Template saved successfully!")
            self.progress_updated.emit(100)
            
            self.save_completed.emit(True, f"Template '{template_name}' saved successfully!")
            
        except Exception as e:
            self.save_completed.emit(False, f"Error saving template: {str(e)}")
    
    def _copy_assets(self, assets_dir, selected_nodes):
        """Copy all assets from Read nodes to the template asset directory."""
        read_nodes = [node for node in selected_nodes if node.Class() == 'Read']
        asset_mapping = {}  # Track original path -> new filename mapping
        
        for read_node in read_nodes:
            try:
                orig_value = read_node['file'].value()
                
                # Handle sequence patterns
                pattern = orig_value.replace('%04d','*').replace('%08d','*').replace('####','*')
                
                if '*' in pattern:
                    # Copy all files matching the sequence pattern
                    copied_files = []
                    for file_path in glob.glob(pattern):
                        if Path(file_path).exists():
                            dest_path = assets_dir / Path(file_path).name
                            shutil.copy2(file_path, dest_path)
                            copied_files.append(Path(file_path).name)
                    
                    if copied_files:
                        # For sequences, reconstruct the pattern using the original format
                        first_file = sorted(copied_files)[0]
                        if '%04d' in orig_value:
                            # Find the frame number in the first file and replace with %04d
                            import re
                            frame_match = re.search(r'(\d{4})', first_file)
                            if frame_match:
                                new_pattern = first_file.replace(frame_match.group(1), '%04d')
                            else:
                                new_pattern = first_file
                        elif '%08d' in orig_value:
                            import re
                            frame_match = re.search(r'(\d{8})', first_file)
                            if frame_match:
                                new_pattern = first_file.replace(frame_match.group(1), '%08d')
                            else:
                                new_pattern = first_file
                        elif '####' in orig_value:
                            import re
                            frame_match = re.search(r'(\d{4})', first_file)
                            if frame_match:
                                new_pattern = first_file.replace(frame_match.group(1), '####')
                            else:
                                new_pattern = first_file
                        else:
                            new_pattern = first_file
                        
                        asset_mapping[orig_value] = new_pattern
                        debug_print(f"Copied sequence: {len(copied_files)} files -> assets/{new_pattern}")
                    
                else:
                    # Copy single file
                    evaluated_path = read_node['file'].evaluate()
                    if Path(evaluated_path).exists():
                        dest_path = assets_dir / Path(evaluated_path).name
                        shutil.copy2(evaluated_path, dest_path)
                        asset_mapping[orig_value] = Path(evaluated_path).name
                        debug_print(f"Copied single file: {evaluated_path} -> assets/{Path(evaluated_path).name}")
                        
            except Exception as e:
                debug_print(f"Warning: Could not copy assets for {read_node.name()}: {e}")
        
        return asset_mapping
    
    def _save_template_nodes(self, nk_path, selected_nodes, asset_mapping=None):
        """Save the selected nodes as a .nk file."""
        try:
            # Store original Read node paths for restoration
            original_read_paths = {}
            
            # Get the template root and construct the full path to assets
            template_root = Path(self.template_library.template_root)
            template_name = self.template_data['name']
            category = self.template_data['category']
            template_folder = template_root / category / template_name
            assets_folder = template_folder / "assets"
            
            # Update Read node paths to point to assets folder using full path from config
            for node in selected_nodes:
                if node.Class() == 'Read':
                    original_path = node['file'].value()
                    original_read_paths[node.name()] = original_path
                    
                    # Use asset mapping if available, otherwise use filename
                    if asset_mapping and original_path in asset_mapping:
                        filename = asset_mapping[original_path]
                        # Use full path from template_root config
                        new_path = str(template_root / category / template_name / "assets" / filename).replace("\\", "/")
                    elif original_path:
                        # Fallback: use just the filename
                        filename = Path(original_path).name
                        # Use full path from template_root config
                        new_path = str(template_root / category / template_name / "assets" / filename).replace("\\", "/")
                    else:
                        new_path = original_path
                    
                    node['file'].setValue(new_path)
                    debug_print(f"Updated Read node {node.name()}: {original_path} -> {new_path}")
            
            # Clear selection and select only the nodes we want to save
            for n in nuke.allNodes():
                n['selected'].setValue(False)
            for n in selected_nodes:
                n['selected'].setValue(True)
            
            # Save the template
            nuke.nodeCopy(str(nk_path))
            
            # Restore original Read node paths
            for node in selected_nodes:
                if node.Class() == 'Read' and node.name() in original_read_paths:
                    node['file'].setValue(original_read_paths[node.name()])
                    debug_print(f"Restored Read node {node.name()} to original path")
            
        except Exception as e:
            # Make sure to restore paths even if saving fails
            if 'original_read_paths' in locals():
                for node in selected_nodes:
                    if node.Class() == 'Read' and node.name() in original_read_paths:
                        node['file'].setValue(original_read_paths[node.name()])
            raise Exception(f"Error saving template nodes: {e}")
    
    def _generate_metadata(self, template_name, tags, selected_nodes, start_frame, end_frame, description=""):
        """Generate comprehensive metadata for the template."""
        # Get script information with error handling
        try:
            script_info = {
                'first_frame': int(nuke.root()['first_frame'].value()),
                'last_frame': int(nuke.root()['last_frame'].value()),
                'format': nuke.root()['format'].value().name(),
                'fps': nuke.root()['fps'].value(),
                'proxy_type': nuke.root()['proxy_type'].value(),
                'colorspace': nuke.root()['colorManagement'].value(),
                'working_space': nuke.root()['workingSpaceLUT'].value(),
                'output_transform': nuke.root()['monitorLut'].value()
            }
        except Exception as e:
            debug_print(f"Warning: Could not get complete script info: {e}")
            script_info = {
                'first_frame': int(nuke.root()['first_frame'].value()),
                'last_frame': int(nuke.root()['last_frame'].value()),
                'format': 'Unknown',
                'fps': 25.0,
                'proxy_type': 'Unknown',
                'colorspace': 'Unknown',
                'working_space': 'Unknown',
                'output_transform': 'Unknown'
            }
        
        # Analyze nodes
        node_info = {
            'total_nodes': len(selected_nodes),
            'node_types': {},
            'read_nodes': [],
            'write_nodes': [],
            'has_camera': False,
            'has_3d': False
        }
        
        for node in selected_nodes:
            node_class = node.Class()
            node_info['node_types'][node_class] = node_info['node_types'].get(node_class, 0) + 1
            
            if node_class == 'Read':
                read_info = {
                    'name': node.name(),
                    'file': node['file'].value(),
                    'colorspace': node['colorspace'].value() if node.knob('colorspace') else 'Unknown',
                    'first': int(node['first'].value()) if node.knob('first') else None,
                    'last': int(node['last'].value()) if node.knob('last') else None
                }
                node_info['read_nodes'].append(read_info)
            
            elif node_class == 'Write':
                write_info = {
                    'name': node.name(),
                    'file': node['file'].value(),
                    'colorspace': node['colorspace'].value() if node.knob('colorspace') else 'Unknown'
                }
                node_info['write_nodes'].append(write_info)
            
            elif node_class in ['Camera', 'Camera2']:
                node_info['has_camera'] = True
            
            elif node_class in ['Card', 'Sphere', 'Cube', 'Cylinder']:
                node_info['has_3d'] = True
        
        # Build complete metadata
        try:
            nuke_version = nuke.NUKE_VERSION_STRING
        except AttributeError:
            nuke_version = "Unknown"
        
        metadata = {
            'template_info': {
                'name': template_name,
                'tags': tags,
                'description': description,
                'created_date': datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                'created_by': os.getenv('USERNAME', 'Unknown'),
                'nuke_version': nuke_version,
                'render_range': {
                    'start': start_frame,
                    'end': end_frame
                }
            },
            'script_info': script_info,
            'node_info': node_info,
            'version': '1.0'
        }
        
        return metadata
    
    def _save_metadata(self, metadata_path, metadata):
        """Save metadata to JSON file."""
        try:
            with open(metadata_path, 'w') as f:
                json.dump(metadata, f, indent=2)
        except Exception as e:
            debug_print(f"Warning: Could not save metadata: {e}")


class TemplateSaveDialog(QDialog):
    """Modern PySide-based dialog for saving templates."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Set proper window flags to ensure correct stacking order
        # Qt.Dialog ensures it's a proper dialog window
        # Qt.WindowCloseButtonHint adds the X button
        # Not setting Qt.WindowStaysOnTopHint to avoid conflicts with modal dialogs
        self.setWindowFlags(Qt.Dialog | Qt.WindowCloseButtonHint)
        
        # Get selected nodes and validate BEFORE setting up UI
        self.selected_nodes = nuke.selectedNodes()
        self.write_node = None
        
        if not self._validate_selection():
            # Close the dialog immediately if validation fails
            self.close()
            return
        
        # Import template library
        try:
            from template_library import TemplateLibrary
            self.template_library = TemplateLibrary()
        except ImportError:
            self.template_library = None
            QMessageBox.critical(self, "Error", "Could not load template library!")
            self.close()
            return
        
        self.setWindowTitle(" ")
        self.setMinimumSize(500, 700)
        self.resize(500, 700)
        self.setAttribute(Qt.WA_DeleteOnClose)
        
        self.setup_ui()
        self.load_existing_categories()
    
    def _validate_selection(self):
        """Validate that the selection is suitable for template saving."""
        if not self.selected_nodes:
            QMessageBox.warning(self, "No Selection", 
                              "Please select at least a Write node and Read nodes.")
            return False
        
        # Find write node
        write_nodes = [node for node in self.selected_nodes if node.Class() == "Write"]
        if not write_nodes:
            QMessageBox.warning(self, "No Write Node", 
                              "Please select a Write node to export.")
            return False
        
        self.write_node = write_nodes[0]
        return True
    
    def setup_ui(self):
        """Setup the user interface."""
        main_layout = QVBoxLayout(self)
        
        # Header widget (reusing from loader)
        header_widget = ToolHeader(name='template_save_header', text='Save Template')
        main_layout.addWidget(header_widget)
        
        # Scroll area for main content
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.NoFrame)  # Remove scroll area frame
        scroll_widget = QFrame()
        scroll_layout = QVBoxLayout(scroll_widget)
        scroll_layout.setContentsMargins(0, 0, 0, 0)  # Remove extra margins
        
        # Template Info Group
        template_info_group = self.create_template_info_group()
        scroll_layout.addWidget(template_info_group)
        
        # Render Settings Group
        render_settings_group = self.create_render_settings_group()
        scroll_layout.addWidget(render_settings_group)
        
        # Node Analysis Group
        node_analysis_group = self.create_node_analysis_group()
        scroll_layout.addWidget(node_analysis_group)
        
        # Progress Group (initially hidden)
        self.progress_group = self.create_progress_group()
        self.progress_group.hide()
        scroll_layout.addWidget(self.progress_group)
        
        scroll_area.setWidget(scroll_widget)
        main_layout.addWidget(scroll_area)
        
        # Save button (full width like loader)
        self.save_button = QPushButton("Save Template")
        self.save_button.setMinimumHeight(50)  # Make button taller like loader
        self.save_button.setStyleSheet("""
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
            QPushButton:pressed {
                background-color: #2968a3;
            }
            QPushButton:disabled {
                background-color: #666666;
                color: #999999;
            }
        """)
        self.save_button.clicked.connect(self.save_template)
        main_layout.addWidget(self.save_button)
    
    def create_template_info_group(self):
        """Create the template information group."""
        group = QGroupBox("Template Information")
        layout = QFormLayout(group)
        
        # Get test values if in testing mode
        test_values = get_test_values()
        
        # Template name
        self.template_name_edit = QLineEdit()
        self.template_name_edit.setPlaceholderText("Enter template name...")
        self.template_name_edit.setText(test_values['template_name'])
        layout.addRow("Template Name:", self.template_name_edit)
        
        # Category
        self.category_combo = QComboBox()
        self.category_combo.setEditable(True)
        self.category_combo.setPlaceholderText("Select or create category...")
        layout.addRow("Category:", self.category_combo)
        
        # New category creation
        new_category_layout = QHBoxLayout()
        self.new_category_check = QCheckBox("Create new category:")
        self.new_category_edit = QLineEdit()
        self.new_category_edit.setPlaceholderText("Enter new category name...")
        self.new_category_edit.setEnabled(False)  # Initially disabled
        
        # Connect checkbox to enable/disable text field
        self.new_category_check.toggled.connect(self.on_new_category_toggled)
        
        new_category_layout.addWidget(self.new_category_check)
        new_category_layout.addWidget(self.new_category_edit)
        
        layout.addRow("", new_category_layout)
        
        # Tags
        self.tags_edit = QLineEdit()
        self.tags_edit.setPlaceholderText("Enter tags separated by commas (e.g., compositing, keying, cleanup)")
        self.tags_edit.setText(test_values['tags'])
        layout.addRow("Tags:", self.tags_edit)
        
        # Tag buttons flow panel
        self.create_tag_buttons_panel(layout)
        
        # Description
        self.description_edit = QTextEdit()
        self.description_edit.setPlaceholderText("Optional description of the template...")
        self.description_edit.setMaximumHeight(100)
        self.description_edit.setPlainText(test_values['description'])
        layout.addRow("Description:", self.description_edit)
        
        return group
    
    def create_render_settings_group(self):
        """Create the render settings group."""
        group = QGroupBox("Render Settings")
        layout = QFormLayout(group)
        
        # Frame range
        frame_layout = QHBoxLayout()
        
        self.start_frame_spin = QSpinBox()
        self.start_frame_spin.setRange(-999999, 999999)
        self.start_frame_spin.setValue(int(nuke.root()["first_frame"].value()))
        frame_layout.addWidget(self.start_frame_spin)
        
        frame_layout.addWidget(QLabel("to"))
        
        self.end_frame_spin = QSpinBox()
        self.end_frame_spin.setRange(-999999, 999999)
        self.end_frame_spin.setValue(int(nuke.root()["last_frame"].value()))
        frame_layout.addWidget(self.end_frame_spin)
        
        layout.addRow("Frame Range:", frame_layout)
        
        # Options
        self.copy_assets_check = QCheckBox("Copy assets to template folder")
        self.copy_assets_check.setChecked(True)
        layout.addRow(self.copy_assets_check)
        
        return group
    
    def create_node_analysis_group(self):
        """Create the node analysis group with compact horizontal layout."""
        group = QGroupBox("Node Analysis")
        layout = QVBoxLayout(group)
        
        # Analyze selected nodes
        analysis_text = self.analyze_selected_nodes()
        
        self.analysis_label = QLabel(analysis_text)
        self.analysis_label.setWordWrap(True)
        self.analysis_label.setStyleSheet("""
            QLabel {
                background-color: #2b2b2b;
                color: #ff7f00;
                padding: 8px 12px;
                border-radius: 5px;
                font-family: monospace;
                font-size: 11px;
                border: 1px solid #4a4a4a;
            }
        """)
        
        # Set size policy to prevent vertical expansion - use version-aware imports
        if PYSIDE_VERSION == 6:
            from PySide6.QtWidgets import QSizePolicy
        elif PYSIDE_VERSION == 2:
            from PySide2.QtWidgets import QSizePolicy
        elif PYSIDE_VERSION == 1:
            from PySide.QtGui import QSizePolicy
        else:
            from Qt.QtWidgets import QSizePolicy
        self.analysis_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        group.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        
        layout.addWidget(self.analysis_label)
        
        return group
    
    def create_progress_group(self):
        """Create the progress group."""
        group = QGroupBox("Save Progress")
        layout = QVBoxLayout(group)
        
        self.progress_bar = QProgressBar()
        layout.addWidget(self.progress_bar)
        
        self.status_label = QLabel("Ready to save...")
        layout.addWidget(self.status_label)
        
        return group
    
    def create_tag_buttons_panel(self, layout):
        """Create a flow panel with predefined tag buttons."""
        # Create a group box for better organization
        tag_buttons_group = QGroupBox("Quick Tags")
        tag_buttons_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 1px solid #cccccc;
                border-radius: 3px;
                margin: 5px 0px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }
        """)
        
        # Create a container for the tag buttons
        tag_buttons_container = QWidget()
        
        # Import FlowLayout and MetaDataButton
        from lib.widgets import FlowLayout, MetaDataButton
        
        # Create flow layout for tag buttons
        tag_flow_layout = FlowLayout(tag_buttons_container, margin=5, spacing=5)
        tag_buttons_container.setLayout(tag_flow_layout)
        
        # Set the tags container to expand horizontally and limit height - use version-aware imports
        if PYSIDE_VERSION == 6:
            from PySide6.QtWidgets import QSizePolicy
        elif PYSIDE_VERSION == 2:
            from PySide2.QtWidgets import QSizePolicy
        elif PYSIDE_VERSION == 1:
            from PySide.QtGui import QSizePolicy
        else:
            from Qt.QtWidgets import QSizePolicy
        tag_buttons_container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        tag_buttons_container.setMaximumHeight(50)
        
        # Define predefined tags based on the ones defined in widgets.py TAG_COLORS
        predefined_tags = {
            "Compositing": ["key"],
            "Cleanup": ["roto"],
            "Color": ["color", "grading", "look-dev"],
            "3D": ["3d", "camera"],
            "Effects": ["fx", "particles"]
        }
        
        # Create buttons for all predefined tags
        for category, tags in predefined_tags.items():
            for tag in tags:
                tag_button = MetaDataButton(text=tag)
                # Use default parameter to capture the tag value properly
                tag_button.clicked.connect(lambda checked=False, t=tag: self.on_predefined_tag_clicked(t))
                tag_flow_layout.addWidget(tag_button)
        
        # Add the container to the group box
        group_layout = QVBoxLayout()
        group_layout.addWidget(tag_buttons_container)
        tag_buttons_group.setLayout(group_layout)
        
        # Set size policy on the group box to prevent vertical expansion
        tag_buttons_group.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        
        # Add the group box to the form layout with proper indentation
        layout.addRow("", tag_buttons_group)
    
    def on_predefined_tag_clicked(self, tag):
        """Handle predefined tag button click - add tag to the tags field if not already present."""
        current_tags = self.tags_edit.text().strip()
        
        # Parse current tags
        if current_tags:
            tags_list = [t.strip() for t in current_tags.split(",") if t.strip()]
        else:
            tags_list = []
        
        # Check if tag is already in the list
        if tag not in tags_list:
            # Add the tag
            tags_list.append(tag)
            # Update the tags field
            self.tags_edit.setText(", ".join(tags_list))
            debug_print(f"Added tag: {tag}")
        else:
            debug_print(f"Tag already exists: {tag}")
    
    def on_new_category_toggled(self, checked):
        """Handle new category checkbox toggle."""
        self.new_category_edit.setEnabled(checked)
        if checked:
            self.new_category_edit.setStyleSheet("")
            self.new_category_edit.setFocus()
        else:
            self.new_category_edit.setStyleSheet("color: #888888;")
            self.new_category_edit.clear()
    
    def analyze_selected_nodes(self):
        """Analyze the selected nodes and return a summary in a compact table format."""
        if not self.selected_nodes:
            return "No nodes selected"
        
        node_types = {}
        read_nodes = []
        write_nodes = []
        
        for node in self.selected_nodes:
            node_class = node.Class()
            node_types[node_class] = node_types.get(node_class, 0) + 1
            
            if node_class == 'Read':
                read_nodes.append(node.name())
            elif node_class == 'Write':
                write_nodes.append(node.name())
        
        analysis = []
        
        # Calculate nodes that will be saved (excluding write nodes)
        nodes_to_save = len(self.selected_nodes) - len(write_nodes)
        
        # Summary line with clarification about write nodes
        if write_nodes:
            analysis.append(f"Selected: {len(self.selected_nodes)} nodes → Saving: {nodes_to_save} nodes (Write nodes excluded)")
        else:
            analysis.append(f"Total: {len(self.selected_nodes)} nodes")
        
        # Node types in a compact format
        if node_types:
            type_parts = []
            for node_type, count in sorted(node_types.items()):
                if node_type == 'Write':
                    type_parts.append(f"{node_type}({count}) [excluded]")
                else:
                    type_parts.append(f"{node_type}({count})")
            analysis.append("Types: " + ", ".join(type_parts))
        
        # Read nodes in a compact format
        if read_nodes:
            if len(read_nodes) <= 3:
                analysis.append("Read: " + ", ".join(read_nodes))
            else:
                analysis.append(f"Read: {', '.join(read_nodes[:3])}, +{len(read_nodes)-3} more")
        
        # Write nodes in a compact format with exclusion note
        if write_nodes:
            if len(write_nodes) <= 3:
                analysis.append("Write: " + ", ".join(write_nodes) + " [for preview only]")
            else:
                analysis.append(f"Write: {', '.join(write_nodes[:3])}, +{len(write_nodes)-3} more [for preview only]")
        
        return " | ".join(analysis)
    
    def load_existing_categories(self):
        """Load existing categories into the combo box."""
        if not self.template_library:
            return
        
        try:
            categories = self.template_library.get_template_folders()
            category_names = [name for name, path in categories]
            
            self.category_combo.addItems(category_names)
            
            # Add default categories if none exist
            if not category_names:
                default_categories = ["Compositing", "Keying", "Cleanup", "3D", "General"]
                self.category_combo.addItems(default_categories)
                category_names = default_categories
            
            # Set category based on testing mode
            test_values = get_test_values()
            if test_values['category'] and test_values['category'] in category_names:
                self.category_combo.setCurrentText(test_values['category'])
            elif category_names:
                self.category_combo.setCurrentIndex(0)
                
        except Exception as e:
            debug_print(f"Error loading categories: {e}")
            # Fallback for testing
            default_categories = ["Compositing", "Keying", "Cleanup", "3D", "General"]
            self.category_combo.addItems(default_categories)
            test_values = get_test_values()
            if test_values['category']:
                self.category_combo.setCurrentText(test_values['category'])
            else:
                self.category_combo.setCurrentText("Compositing")
    
    def save_template(self):
        """Save the template with validation."""
        # Validate inputs
        template_name = self.template_name_edit.text().strip()
        if not template_name:
            QMessageBox.warning(self, "Missing Name", "Please enter a template name.")
            return
        
        # Clean template name
        template_name = template_name.replace(" ", "_").replace("/", "_").replace("\\", "_")
        
        # Determine category - use new category if checkbox is checked
        if self.new_category_check.isChecked():
            category = self.new_category_edit.text().strip()
            if not category:
                QMessageBox.warning(self, "Missing New Category", "Please enter a new category name.")
                return
        else:
            category = self.category_combo.currentText().strip()
            if not category:
                QMessageBox.warning(self, "Missing Category", "Please select or enter a category.")
                return
        
        # Parse tags
        tags_text = self.tags_edit.text().strip()
        tags = [tag.strip() for tag in tags_text.split(",") if tag.strip()] if tags_text else []
        
        # Prepare template data
        template_data = {
            'name': template_name,
            'category': category,
            'tags': tags,
            'description': self.description_edit.toPlainText().strip(),
            'start_frame': self.start_frame_spin.value(),
            'end_frame': self.end_frame_spin.value(),
            'selected_nodes': self.selected_nodes,
            'write_node': self.write_node,
            'copy_assets': self.copy_assets_check.isChecked()
        }
        
        # Show progress and disable controls
        self.progress_group.show()
        self.save_button.setEnabled(False)
        
        # Create worker thread
        self.worker = TemplateSaveWorker(template_data, self.template_library)
        self.worker.progress_updated.connect(self.progress_bar.setValue)
        self.worker.status_updated.connect(self.status_label.setText)
        self.worker.save_completed.connect(self.on_save_completed)
        self.worker.hide_dialog.connect(self.hide_during_render)
        self.worker.show_dialog.connect(self.show_after_render)
        
        # Start saving
        self.worker.save_template()
    
    def hide_during_render(self):
        """Hide the dialog during rendering to avoid UI conflicts."""
        self.hide()
        debug_print("Dialog hidden during rendering")
    
    def show_after_render(self):
        """Show the dialog after rendering is complete."""
        self.show()
        self.raise_()
        self.activateWindow()
        debug_print("Dialog shown after rendering")
    
    def on_save_completed(self, success, message):
        """Handle save completion."""
        self.save_button.setEnabled(True)
        
        if success:
            QMessageBox.information(self, "Success", message)
            self.accept()
        else:
            QMessageBox.critical(self, "Error", message)
            self.progress_group.hide()


def get_nuke_main_window():
    """Get the main Qt window of Nuke."""
    if PYSIDE_VERSION == 6:
        from PySide6.QtWidgets import QApplication
    elif PYSIDE_VERSION == 2:
        from PySide2.QtWidgets import QApplication
    elif PYSIDE_VERSION == 1:
        from PySide.QtGui import QApplication
    else:
        from Qt.QtWidgets import QApplication
    
    for widget in QApplication.topLevelWidgets():
        if widget.metaObject().className() == "Foundry::UI::DockMainWindow":
            return widget
    return None


def show_template_save_dialog():
    """Show the template save dialog."""
    try:
        # Get Nuke's main window for proper parenting
        parent = get_nuke_main_window()
        
        dialog = TemplateSaveDialog(parent)
        
        # Check if dialog was properly initialized (not closed during validation)
        if dialog.isVisible() or hasattr(dialog, 'template_library'):
            return dialog.exec_()
        else:
            # Dialog was closed during validation, don't show it
            return None
            
    except Exception as e:
        nuke.message(f"Error opening template save dialog: {e}")
        debug_print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return None


# Development/Testing Configuration
# Set to False for production deployment
TESTING_MODE = False

def get_test_values():
    """Get test values for UI fields when in testing mode."""
    if TESTING_MODE:
        timestamp = datetime.datetime.now().strftime("%H%M%S")
        return {
            'template_name': f"TestTemplate_{timestamp}",
            'tags': "test, compositing, pipeline",
            'description': "This is a test template created during pipeline development.",
            'category': "Compositing"
        }
    else:
        return {
            'template_name': "",
            'tags': "",
            'description': "",
            'category': ""
        }

# For testing
if __name__ == "__main__":
    show_template_save_dialog()
