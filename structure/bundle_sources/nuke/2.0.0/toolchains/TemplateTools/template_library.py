"""
Template Library System for Nuke

A comprehensive system for saving and loading Nuke templates with associated assets.
Uses the toolchain configuration to determine template storage location.

Author: Pipeline Team
Date: July 2025
"""

import nuke
import os
import shutil
import glob
from pathlib import Path


class TemplateLibrary:
    """Main class for template library operations."""
    
    # Class-level variable to store custom template root
    _custom_template_root = None
    
    def __init__(self):
        """Initialize the template library with dynamic path resolution."""
        self.template_root = self._get_template_root()
    
    @classmethod
    def set_template_root(cls, template_root):
        """
        Set a custom template root path.
        
        Args:
            template_root (str): Path to the template root directory
        """
        cls._custom_template_root = template_root
    
    @classmethod
    def get_configured_template_root(cls):
        """Get the configured template root if set."""
        return cls._custom_template_root
    
    def _get_template_root(self):
        """Get the template root path from toolchain configuration."""
        import json
        import platform
        
        try:
            # First priority: class-level custom configuration
            if self._custom_template_root and Path(self._custom_template_root).exists():
                return self._custom_template_root
            
            # Second priority: environment variable (custom override)
            config_path = os.environ.get('NUKE_TEMPLATE_ROOT')
            if config_path and Path(config_path).exists():
                return config_path
            
            # Third priority: get from toolchain configuration
            nuke_path = os.environ.get('TLA_COMP_CORE')
            if nuke_path:
                config_path = Path(nuke_path) / "toolchains.json"
                if config_path.exists():
                    with open(config_path, 'r') as f:
                        config = json.load(f)
                        template_tools_config = config.get("toolchains", {}).get("TemplateTools", {})
                        template_root_config = template_tools_config.get("config", {}).get("template_root", {})
                        current_platform = "windows" if platform.system() == "Windows" else "mac"
                        external_path = template_root_config.get(current_platform)
                        
                        if external_path and Path(external_path).exists():
                            return external_path
                        elif external_path:
                            # Create the directory if it doesn't exist
                            Path(external_path).mkdir(parents=True, exist_ok=True)
                            return external_path
            
            # If no config found, raise an informative error
            error_msg = (
                f"Could not determine template root directory from toolchain configuration.\n\n"
                "Please ensure:\n"
                "1. TLA_COMP_CORE environment variable is set (core/init.py sets it)\n"
                "2. toolchains.json exists in the core directory\n"
                "3. TemplateTools config contains template_root path for your platform\n"
                "4. Or set a custom path: TemplateLibrary.set_template_root('/path/to/templates')\n"
                "5. Or set NUKE_TEMPLATE_ROOT environment variable"
            )
            raise RuntimeError(error_msg)
            
        except Exception as e:
            # Re-raise with additional context
            error_msg = (
                f"Error reading template configuration: {e}\n\n"
                "Please check your toolchain configuration or set a custom template root."
            )
            raise RuntimeError(error_msg)
    
    def get_template_folders(self):
        """Scan template root and return a list of (folder_name, full_path)."""
        if not Path(self.template_root).exists():
            return []
        
        folders = []
        try:
            template_root_path = Path(self.template_root)
            for name in template_root_path.iterdir():
                if name.is_dir():
                    folders.append((name.name, str(name)))
        except OSError as e:
            nuke.message(f"Error reading template directories: {e}")
            
        return folders
    
    def get_destinations(self):
        """Get available destination folders for saving templates."""
        template_root_path = Path(self.template_root)
        return [(name.name, str(name)) 
                for name in template_root_path.iterdir()
                if name.is_dir()]
    
    def configure_write_node(self, write_node, mp4_path):
        """Configure a Write node for MP4 output with optimal settings."""
        # Use Path.as_posix() to ensure forward slashes for Nuke
        write_node["file"].setValue(Path(mp4_path).as_posix())
        write_node["file_type"].setValue("mov")
        write_node["mov64_format"].setValue("mp4 (MP4 (MPEG-4 Part 14))")
        write_node["mov64_codec"].setValue("h264")
        write_node["mov_h264_codec_profile"].setValue("High 4:2:0 8-bit")
        write_node["mov64_pixel_format"].setValue(0)
        write_node["mov64_quality"].setValue("Custom")
        write_node["mov64_fast_start"].setValue(True)
        write_node["mov64_write_timecode"].setValue(True)
        write_node["mov64_gop_size"].setValue(12)
        write_node["mov64_b_frames"].setValue(0)
        write_node["mov64_bitrate"].setValue(28000)
        write_node["mov64_bitrate_tolerance"].setValue(0)
        write_node["mov64_quality_min"].setValue(1)
        write_node["mov64_quality_max"].setValue(3)
        write_node["checkHashOnRead"].setValue(False)
        write_node["create_directories"].setValue(True)
        
        # Set colorspace based on color management - safer approach
        try:
            cm = nuke.root()["colorManagement"].value()
            available_colorspaces = write_node["colorspace"].values()
            available_views = write_node["view"].values()
            
            print(f"Color management: {cm}")
            print(f"Available colorspaces: {available_colorspaces}")
            print(f"Available views: {available_views}")
            
            if cm == "OCIO":
                # OCIO color management is enabled
                if "Output - sRGB" in available_colorspaces:
                    write_node["colorspace"].setValue("Output - sRGB")
                elif "sRGB" in available_colorspaces:
                    write_node["colorspace"].setValue("sRGB")
                else:
                    # Use the first available colorspace as fallback
                    write_node["colorspace"].setValue(available_colorspaces[0])
                    
                if "sRGB" in available_views:
                    write_node["view"].setValue("sRGB")
                else:
                    write_node["view"].setValue(available_views[0])
            else:
                # Legacy color management - use sRGB or linear
                if "sRGB" in available_colorspaces:
                    write_node["colorspace"].setValue("sRGB")
                elif "linear" in available_colorspaces:
                    write_node["colorspace"].setValue("linear")
                else:
                    # Use the first available colorspace as fallback
                    write_node["colorspace"].setValue(available_colorspaces[0])
                
                # Set view to default for legacy color management
                if "default" in available_views:
                    write_node["view"].setValue("default")
                else:
                    write_node["view"].setValue(available_views[0])
                    
            print(f"Set colorspace to: {write_node['colorspace'].value()}")
            print(f"Set view to: {write_node['view'].value()}")
            
        except Exception as e:
            # Fallback to safe defaults if colorspace setting fails
            print(f"Warning: Could not set colorspace, using defaults: {e}")
            try:
                write_node["colorspace"].setValue("sRGB")
                write_node["view"].setValue("default")
            except:
                pass  # Let Nuke use its internal defaults
    
    def export_toolset_and_mp4(self):
        """Export selected nodes as a template with MP4 preview and metadata."""
        try:
            # Import and show the modern save dialog
            from template_save_ui import show_template_save_dialog
            show_template_save_dialog()
        except ImportError:
            # Fallback to old method if new dialog not available
            self._export_toolset_and_mp4_legacy()
        except Exception as e:
            nuke.message(f"Error opening save dialog: {e}")
    
    def _export_toolset_and_mp4_legacy(self):
        """Legacy export method using Nuke panels (fallback only)."""
        existing_destinations = self.get_destinations()
        if not existing_destinations:
            # Create a default category if none exist
            default_category = Path(self.template_root) / "General"
            default_category.mkdir(parents=True, exist_ok=True)
            existing_destinations = [("General", str(default_category))]
        
        existing_names = [name for name, path in existing_destinations]

        selected_nodes = nuke.selectedNodes()
        if not selected_nodes:
            nuke.message("Please select at least a Write node and Read nodes.")
            return

        write_node = next((node for node in selected_nodes if node.Class() == "Write"), None)
        if not write_node:
            nuke.message("Please select a Write node to export.")
            return

        # Create export dialog
        p = nuke.Panel("Export Template")
        p.addSingleLineInput("Template Name", "")
        p.addEnumerationPulldown("Category", " ".join(existing_names))
        p.addSingleLineInput("Start Frame", str(int(nuke.root()["first_frame"].value())))
        p.addSingleLineInput("End Frame", str(int(nuke.root()["last_frame"].value())))
        
        if not p.show(): 
            return

        # Get user inputs
        template_name = p.value("Template Name").strip().replace(" ", "_").capitalize()
        if not template_name:
            return
            
        category = p.value("Category")
        start_frame = int(p.value("Start Frame"))
        end_frame = int(p.value("End Frame"))

        # Use new folder structure
        template_root = Path(self.template_root)
        category_path = template_root / category
        template_folder = category_path / template_name
        
        # Create template folder
        template_folder.mkdir(parents=True, exist_ok=True)
        
        # Define output paths (new structure)
        nk_path = template_folder / f"{template_name}.nk"
        mp4_path = template_folder / f"{template_name}.mp4"
        assets_dir = template_folder / "assets"

        # Create assets directory
        assets_dir.mkdir(exist_ok=True)

        # Temporarily add reformat for consistent MP4 output
        old_input = write_node.input(0)
        reformat = nuke.nodes.Reformat(format="HD_1080", pbb=True)
        reformat.setInput(0, old_input)
        write_node.setInput(0, reformat)

        # Configure write node for MP4 output
        original_file = write_node["file"].value()
        self.configure_write_node(write_node, str(mp4_path))

        try:
            # Render the MP4 preview
            nuke.execute(write_node.name(), start_frame, end_frame)
        except Exception as e:
            nuke.message(f"Render failed: {e}")
            return
        finally:
            # Restore original setup
            write_node.setInput(0, old_input)
            write_node["file"].setValue(original_file)
            nuke.delete(reformat)

        # Copy assets to template directory and update Read node paths
        asset_mapping = self._copy_read_node_assets_and_update_paths(str(assets_dir), selected_nodes, template_root, category, template_name)

        # Save the toolset
        try:
            # Clear selection and select only the nodes we want to save
            for n in nuke.allNodes():
                n['selected'].setValue(False)
            for n in selected_nodes:
                n['selected'].setValue(True)
            
            nuke.nodeCopy(str(nk_path))
        except Exception as e:
            nuke.message(f"Error saving template: {e}")
            return
        finally:
            # Restore original Read node paths
            if asset_mapping:
                self._restore_read_node_paths(asset_mapping)

        nuke.message(f"Template '{template_name}' saved successfully!\\n\\nLocation: {template_folder}")
    
    def _copy_read_node_assets_and_update_paths(self, asset_dir, selected_nodes, template_root, category, template_name):
        """Copy assets from Read nodes and update their paths, returning mapping for restoration."""
        asset_mapping = {}
        original_read_paths = {}
        
        # Only process Read nodes that are in the selected nodes
        read_nodes = [node for node in selected_nodes if node.Class() == 'Read']
        
        for read_node in read_nodes:
            try:
                original_path = read_node['file'].value()
                original_read_paths[read_node.name()] = original_path
                
                if not original_path:
                    continue
                
                # Handle sequence patterns
                pattern = original_path.replace('%04d','*').replace('%08d','*').replace('####','*')
                
                if '*' in pattern:
                    # Copy all files matching the sequence pattern
                    asset_dir_path = Path(asset_dir)
                    copied_files = []
                    for file_path in glob.glob(pattern):
                        if Path(file_path).exists():
                            dest_path = asset_dir_path / Path(file_path).name
                            shutil.copy2(file_path, dest_path)
                            copied_files.append(Path(file_path).name)
                    
                    if copied_files:
                        # Generate the pattern for the assets folder
                        first_file = copied_files[0]
                        # Extract the pattern from the first file
                        if '%04d' in original_path:
                            new_pattern = first_file.replace(first_file.split('.')[-2], '%04d')
                        elif '%08d' in original_path:
                            new_pattern = first_file.replace(first_file.split('.')[-2], '%08d')
                        elif '####' in original_path:
                            new_pattern = first_file.replace(first_file.split('.')[-2], '####')
                        else:
                            new_pattern = first_file
                        
                        asset_mapping[original_path] = new_pattern
                        
                        # Update Read node path to use full path from config
                        new_path = (template_root / category / template_name / "assets" / new_pattern).as_posix()
                        read_node['file'].setValue(new_path)
                        
                else:
                    # Copy single file
                    evaluated_path = read_node['file'].evaluate()
                    if Path(evaluated_path).exists():
                        asset_dir_path = Path(asset_dir)
                        filename = Path(evaluated_path).name
                        shutil.copy2(evaluated_path, asset_dir_path / filename)
                        
                        asset_mapping[original_path] = filename
                        
                        # Update Read node path to use full path from config  
                        new_path = (template_root / category / template_name / "assets" / filename).as_posix()
                        read_node['file'].setValue(new_path)
                        
            except Exception as e:
                print(f"Warning: Could not copy assets for {read_node.name()}: {e}")
        
        return {'original_paths': original_read_paths, 'asset_mapping': asset_mapping}
    
    def _restore_read_node_paths(self, asset_mapping):
        """Restore original Read node paths after saving."""
        if not asset_mapping or 'original_paths' not in asset_mapping:
            return
            
        for node_name, original_path in asset_mapping['original_paths'].items():
            try:
                node = nuke.toNode(node_name)
                if node and node.Class() == 'Read':
                    node['file'].setValue(original_path)
            except Exception as e:
                print(f"Warning: Could not restore path for {node_name}: {e}")

    def _copy_read_node_assets(self, asset_dir):
        """Copy all assets from Read nodes to the template asset directory."""
        read_nodes = [node for node in nuke.allNodes('Read')]
        
        for read_node in read_nodes:
            try:
                orig_value = read_node['file'].value()
                
                # Handle sequence patterns
                pattern = orig_value.replace('%04d','*').replace('%08d','*').replace('####','*')
                
                if '*' in pattern:
                    # Copy all files matching the sequence pattern
                    asset_dir_path = Path(asset_dir)
                    for file_path in glob.glob(pattern):
                        if Path(file_path).exists():
                            shutil.copy2(file_path, asset_dir_path / Path(file_path).name)
                else:
                    # Copy single file
                    evaluated_path = read_node['file'].evaluate()
                    if Path(evaluated_path).exists():
                        asset_dir_path = Path(asset_dir)
                        shutil.copy2(evaluated_path, asset_dir_path / Path(evaluated_path).name)
                        
            except Exception as e:
                print(f"Warning: Could not copy assets for {read_node.name()}: {e}")
    
    def import_single_template(self, nk_file_path):
        """Import a single .nk template file into the current script."""
        try:
            # Import the .nk file using nodePaste
            nuke.nodePaste(nk_file_path)
            
            template_name = Path(nk_file_path).stem
            print(f"Successfully imported template: {template_name}")
            
        except Exception as e:
            template_name = Path(nk_file_path).stem
            # nuke.message(f"Error importing template '{template_name}': {e}")
    
    def import_templates_to_contact_sheet(self, template_path, category_name):
        """Import all .nk template files from a category folder into the current script."""
        try:
            # Find all .nk files in the template directory
            nk_files = []
            template_path_obj = Path(template_path)
            for file in template_path_obj.iterdir():
                if file.suffix.lower() == '.nk':
                    nk_files.append(str(file))
            
            if not nk_files:
                nuke.message(f"No .nk template files found in {category_name}")
                return
            
            # Import all .nk files into the current script
            self._import_nk_templates(nk_files, category_name)
            
        except Exception as e:
            nuke.message(f"Error loading templates: {e}")
    
    def _import_nk_templates(self, nk_files, category_name):
        """Import all .nk template files into the current script."""
        imported_count = 0
        
        for nk_path in nk_files:
            try:
                # Import the .nk file (paste into current script)
                nuke.nodePaste(nk_path)
                imported_count += 1
                
            except Exception as e:
                print(f"Warning: Could not import {Path(nk_path).name}: {e}")
        
        if imported_count > 0:
            pass  # Successfully imported templates - no message needed
            # nuke.message(f"Successfully imported {imported_count} template(s) from {category_name}")
        else:
            nuke.message(f"No templates could be imported from {category_name}")
    
    def import_category_as_contact_sheet(self, category_path, backdrop_label=None):
        """
        Import all MP4 templates in a category as a contact sheet.
        
        Args:
            category_path (str or Path): Path to the category folder
            backdrop_label (str): Label for the backdrop node
        """
        category_path = Path(category_path)
        
        if not category_path.is_dir():
            nuke.message(f"Invalid folder selected: {category_path}")
            return

        # Search for MP4 files in the category folder and subfolders
        mp4_files = []
        
        # Look for MP4s directly in category folder (legacy structure)
        mp4_files.extend(list(category_path.glob("*.mp4")))
        
        # Look for MP4s in template subfolders (new structure)
        for template_folder in category_path.iterdir():
            if template_folder.is_dir():
                mp4_files.extend(list(template_folder.glob("*.mp4")))
        
        if not mp4_files:
            # nuke.message(f"No MP4 files found in the selected folder: {category_path}")
            return

        # Use category name as backdrop label if not provided
        if backdrop_label is None:
            backdrop_label = category_path.name.upper()

        read_nodes = []
        reformat_nodes = []
        text_nodes = []

        xpos = 0
        ypos = 0
        spacing = 500  # More margin between nodes

        all_x_positions = []
        all_y_positions = []

        for mp4_path in sorted(mp4_files):
            # Determine the template name and corresponding .nk file
            if mp4_path.parent == category_path:
                # Legacy structure - MP4 directly in category
                template_name = mp4_path.stem
                nk_path = mp4_path.with_suffix('.nk')
            else:
                # New structure - MP4 in template subfolder
                template_name = mp4_path.parent.name
                nk_path = mp4_path.parent / f"{template_name}.nk"
            
            # Create Read node
            read_node = nuke.createNode('Read', inpanel=False)
            read_node['file'].fromUserText(Path(mp4_path).as_posix())
            read_node['reload'].execute()
            read_node.setName(template_name)
            read_node.setXpos(xpos)
            read_node.setYpos(ypos)
            read_node['after'].setValue('loop')

            all_x_positions.append(xpos)
            all_y_positions.append(ypos)

            # Create Sticky Note above the Read Node
            sticky = nuke.createNode('StickyNote', inpanel=False)
            sticky.setXpos(xpos - 150)
            sticky.setYpos(ypos - 100)
            sticky['label'].setValue(template_name.upper())
            sticky['note_font_size'].setValue(35)
            sticky['note_font'].setValue('Arial')
            sticky['tile_color'].setValue(0xef7780ff)

            # Create Reformat node
            reformat_node = nuke.createNode('Reformat', inpanel=False)
            reformat_node.setInput(0, read_node)
            reformat_node['format'].setValue("HD_720")
            reformat_node['resize'].setValue("width")
            reformat_node.setXpos(xpos)
            reformat_node.setYpos(ypos + 100)

            # Create NoOp Node after Reformat with load functionality
            no_op_node = nuke.createNode('NoOp', inpanel=False)
            no_op_node.setInput(0, reformat_node)
            no_op_node.setName('Load_ToolSet')
            no_op_node['tile_color'].setValue(0x3cff74ff)
            no_op_node.setXpos(xpos)
            no_op_node.setYpos(ypos + 159)

            # Add Python Script Button to NoOp for loading the template
            no_op_node.addKnob(nuke.Tab_Knob('load', 'load'))
            button = nuke.PyScript_Knob('LoadToolset', 'Load Toolset')
            button.setFlag(nuke.STARTLINE)
            
            # Calculate the offset outside the backdrop area
            load_offset_x = max(all_x_positions) + 600 if all_x_positions else 600
            load_offset_y = max(all_y_positions) + 600 if all_y_positions else 600

            # Create the load script based on file structure
            if nk_path.exists():
                # Use as_posix() to ensure forward slashes for cross-platform compatibility
                script_path_str = nk_path.as_posix()
                button.setValue(
                    f"from pathlib import Path\n"
                    f"script_path = Path('{script_path_str}')\n"
                    f"if script_path.exists():\n"
                    f"    for n in nuke.allNodes():\n"
                    f"        n.setSelected(False)\n"
                    f"    n = nuke.nodePaste(str(script_path))\n"
                    f"    if n:\n"
                    f"        for node in nuke.selectedNodes():\n"
                    f"            node.setXpos(node.xpos() + {load_offset_x})\n"
                    f"            node.setYpos(node.ypos() + {load_offset_y})\n"
                    f"else:\n"
                    f"    nuke.message(f'Toolset not found: {{script_path}}')"
                )
            else:
                button.setValue(f"nuke.message('Template file not found: {nk_path}')")
            
            no_op_node.addKnob(button)

            # Create Text node
            text_node = nuke.createNode('Text2', inpanel=False)
            text_node.setInput(0, no_op_node)
            text_node['box'].setValue([0, 0, 0, 720])
            text_node['font_size'].setValue(60)
            text_node['font'].setValue('Arial', 'Black')
            text_node['message'].setValue(template_name.upper())
            text_node['color'].setValue([1, 1, 1, 1])
            text_node['opacity'].setValue(1)
            text_node.setXpos(xpos)
            text_node.setYpos(ypos + 200)

            read_nodes.append(read_node)
            reformat_nodes.append(reformat_node)
            text_nodes.append(text_node)

            xpos += spacing

        # Calculate backdrop dimensions with more margin
        margin_x = 240
        margin_y = 180

        all_nodes = read_nodes + reformat_nodes + text_nodes
        min_x = min(node.xpos() for node in all_nodes) - margin_x
        max_x = max(node.xpos() for node in all_nodes) + margin_x 
        min_y = min(node.ypos() for node in all_nodes) - margin_y
        max_y = max(node.ypos() for node in all_nodes) + margin_y 

        # Create backdrop
        backdrop = nuke.createNode("BackdropNode")
        backdrop['xpos'].setValue(min_x)
        backdrop['bdwidth'].setValue(max_x - min_x)
        backdrop['ypos'].setValue(min_y)
        backdrop['bdheight'].setValue(max_y - min_y)
        backdrop['tile_color'].setValue(0x48ff75ff)
        backdrop['note_font'].setValue('Verdana Bold')
        backdrop['note_font_size'].setValue(42)
        backdrop['appearance'].setValue('Border')
        backdrop['label'].setValue(backdrop_label)

        # Deselect all nodes before creating contact sheet
        for node in all_nodes:
            node.setSelected(False)

        # Create contact sheet
        contact_sheet = nuke.createNode('ContactSheet', inpanel=False)
        contact_sheet.setName('ContactSheet')
        contact_sheet['center'].setValue(True)
        contact_sheet['roworder'].setValue('TopBottom')
        contact_sheet['startframe'].setValue(1)
        contact_sheet['endframe'].setValue(10)
        contact_sheet['tile_color'].setValue(0xe955ffff)

        # Add custom resolution divider knob if it doesn't exist
        if not contact_sheet.knob('Resolution_DevidedBy'):
            contact_sheet.addKnob(nuke.Int_Knob('Resolution_DevidedBy', 'Resolution DevidedBy'))
            contact_sheet['Resolution_DevidedBy'].setValue(1)

        # Set up contact sheet expressions
        contact_sheet['width'].setExpression('input.width * columns / Resolution_DevidedBy')
        contact_sheet['height'].setExpression('input.height * rows / Resolution_DevidedBy')
        contact_sheet['rows'].setExpression('(ceil(sqrt(inputs()) + 0.5))')
        contact_sheet['columns'].setExpression('(ceil(inputs() / rows))')

        # Connect all text nodes to contact sheet
        for i, text_node in enumerate(text_nodes):
            contact_sheet.setInput(i, text_node)

        # Position contact sheet
        avg_x = sum(node.xpos() for node in text_nodes) // len(text_nodes) if text_nodes else 0
        contact_sheet.setXpos(avg_x)
        contact_sheet.setYpos(ypos + 600)

        all_nodes = nuke.allNodes()
        if all_nodes:
            nuke.selectAll()
            nuke.zoomToFitSelected()
            for node in all_nodes:
                node.setSelected(False)

