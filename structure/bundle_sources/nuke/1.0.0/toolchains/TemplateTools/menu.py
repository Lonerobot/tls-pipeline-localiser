"""
TemplateTools Menu Integration

Standard menu.py file for the TemplateTools toolchain.
Provides template library functionality with save/load operations.
Uses platform-specific external template directories from toolchain configuration.

Author: Pipeline Team  
Date: July 2025
"""

import nuke
import os
import json
import sys
import platform
from pathlib import Path

# Add the toolchain directory to Python path for imports
toolchain_dir = Path(__file__).parent
if str(toolchain_dir) not in sys.path:
    sys.path.insert(0, str(toolchain_dir))

# Now import the template library
import template_library
from template_library import TemplateLibrary

# Check if we should reload modules for development
def should_reload_modules():
    """Check if module reloading is enabled in config."""
    try:
        nuke_path = os.environ.get('TLA_COMP_CORE')
        if nuke_path:
            config_path = Path(nuke_path) / "config.json"
            if config_path.exists():
                import json
                with open(config_path, 'r') as f:
                    config = json.load(f)
                return config.get('development', {}).get('reload_modules', False)
    except:
        pass
    return False

# Reload the template_library module if configured to do so
if should_reload_modules():
    try:
        import importlib
        importlib.reload(template_library)
        from template_library import TemplateLibrary
        print("TemplateTools: Reloaded template_library module")
    except Exception as e:
        print(f"TemplateTools: Failed to reload template_library: {e}")

def open_template_loader_ui():
    """Open the simplified Template Loader UI window."""
    try:
        import template_loader_ui
        # Reload the module if configured to do so
        if should_reload_modules():
            import importlib
            importlib.reload(template_loader_ui)
        
        # Use the simplified template loader
        window = template_loader_ui.show_template_loader_global()
        return window
    except Exception as e:
        nuke.message(f"Error opening Template Loader UI: {str(e)}")
        print(f"TemplateTools: Error opening Template Loader UI: {e}")
        import traceback
        traceback.print_exc()

def open_template_loader_simple_ui():
    """Open the ultra-simplified Template Loader UI window."""
    try:
        import template_loader_simple_ui
        # Reload the module if configured to do so
        if should_reload_modules():
            import importlib
            importlib.reload(template_loader_simple_ui)
        
        # Use the simple template loader
        window = template_loader_simple_ui.show_simple_template_loader_global()
        return window
    except Exception as e:
        nuke.message(f"Error opening Simple Template Loader UI: {str(e)}")
        print(f"TemplateTools: Error opening Simple Template Loader UI: {e}")
        import traceback
        traceback.print_exc()

def load_toolchain_config():
    """Load configuration from toolchains.json using pipeline environment variables."""
    try:
        # TLA_COMP_CORE points at the pipeline core folder, set by core/init.py
        nuke_path = os.environ.get('TLA_COMP_CORE')
        if not nuke_path:
            print("TLA_COMP_CORE environment variable not set")
            return {}, {}
        
        # toolchains.json is in the core folder
        config_path = Path(nuke_path) / "toolchains.json"
        
        if config_path.exists():
            with open(config_path, 'r') as f:
                config = json.load(f)
                template_tools_config = config.get("toolchains", {}).get("TemplateTools", {})
                toolchain_info = {
                    "display_name": template_tools_config.get("display_name", "Template Library"),
                    "menu_icon": template_tools_config.get("menu_icon", "template_icon.png")
                }
                return template_tools_config.get("config", {}), toolchain_info
        else:
            print(f"Toolchains config file not found: {config_path}")
    except Exception as e:
        print(f"Could not load toolchain config: {e}")
    
    return {}, {"display_name": "Template Library", "menu_icon": "template_icon.png"}


def get_template_directories():
    """Get template directory from toolchain configuration."""
    # Get platform-specific external template directory from config
    config, _ = load_toolchain_config()  # Get config only, ignore toolchain_info
    template_root_config = config.get("template_root", {})
    
    if isinstance(template_root_config, dict):
        # Determine platform
        current_platform = "windows" if platform.system() == "Windows" else "mac"
        external_template_path = template_root_config.get(current_platform)
        
        if external_template_path and Path(external_template_path).exists():
            return [external_template_path]
        elif external_template_path:
            # Create the directory if it doesn't exist
            try:
                Path(external_template_path).mkdir(parents=True, exist_ok=True)
                return [external_template_path]
            except Exception as e:
                print(f"Warning: Could not create template directory {external_template_path}: {e}")
        else:
            print(f"Warning: No template directory configured for platform: {current_platform}")
    
    return []


def create_template_menu():
    """Create the Template Library menu in Nuke's menu bar."""
    # Load toolchain configuration for menu name and icon
    config, toolchain_info = load_toolchain_config()
    
    MENU_NAME = toolchain_info["display_name"]
    SUBICON_PATH = f"icons/{toolchain_info['menu_icon']}"

    menu_bar = nuke.menu("Nuke")
    custom_menu = menu_bar.addMenu(MENU_NAME)
    
    # Get template directory from configuration
    template_directories = get_template_directories()
    
    # Initialize the template library system
    template_lib = TemplateLibrary()
    
    # Set the template directory as the root for saving and loading
    if template_directories:
        template_lib.set_template_root(template_directories[0])

       # Add Template Loader UI command
    custom_menu.addCommand("Load Template...", lambda: open_template_loader_ui(), icon=SUBICON_PATH)
    
    # Add Simple Template Loader UI command
    custom_menu.addCommand("Load Template (simple)", lambda: open_template_loader_simple_ui(), icon=SUBICON_PATH)
         
       # # Add separator
    custom_menu.addSeparator() 
    # Add Save command
    custom_menu.addCommand("Save Template", template_lib.export_toolset_and_mp4, icon=SUBICON_PATH)
    

   

# Create the menu when this module is imported
create_template_menu()
