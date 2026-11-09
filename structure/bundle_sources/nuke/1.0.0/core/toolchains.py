"""
Simple toolchain loader for Nuke
Loads toolchains based on toolchains.json configuration
Pipeline paths should already be set by init.py
"""

import json
import nuke
import os
import re
from pathlib import Path

# Import pipeline logging utilities
try:
    from utils.PipelineLogger import get_logger, log_performance
    LOGGER_AVAILABLE = True
except ImportError:
    LOGGER_AVAILABLE = False

# Global debug flag (will be set from config)
DEBUG_MODE = False


def _parse_display_name(name):
    """Parse display name to make it more readable"""
    # First replace underscores with spaces
    display_name = name.replace('_', ' ')
    
    # Then split camelCase/PascalCase by inserting spaces before capitals
    # This regex finds capital letters that are either:
    # - Preceded by a lowercase letter (camelCase)
    # - Preceded by a capital letter and followed by a lowercase letter (for acronyms like "XMLHttpRequest")
    display_name = re.sub(r'(?<=[a-z])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])', ' ', display_name)
    
    return display_name


def load_toolchains():
    """Load enabled toolchains from configuration"""
    import time
    start_time = time.time()
    
    # Declare global variables first
    global DEBUG_MODE
    
    # Get pipeline paths from environment variables (should be set by init.py)
    nuke_path = Path(os.environ.get('TLA_COMP_CORE') or Path(__file__).resolve().parent)
    pipeline_root = Path(os.environ.get('TLA_COMP_PIPELINE_ROOT') or nuke_path.parent)
    toolchains_path = Path(os.environ.get('TLA_COMP_TOOLCHAINS') or pipeline_root / 'toolchains')
    
    # Config files are in the core folder
    config_file = nuke_path / 'toolchains.json'
    main_config_file = nuke_path / 'config.json'
    
    # Load main configuration to check debug mode FIRST
    if main_config_file.exists():
        with main_config_file.open('r') as f:
            main_config = json.load(f)
            DEBUG_MODE = main_config.get('development', {}).get('debug_mode', False)
    
    # Now initialize logger based on debug mode
    logger = None
    if LOGGER_AVAILABLE and DEBUG_MODE:
        logger = get_logger("toolchains")
        logger.info("===== STARTING TOOLCHAIN LOADING =====")
        
        # Configure logger for debug mode
        import logging
        from utils.PipelineLogger import set_log_level
        set_log_level(logging.DEBUG)
        logger.debug("Debug mode enabled - verbose logging active")
    
    # Initialize reporter
    reporter = None
    try:
        from utils.PipelineReporter import create_reporter
        reporter = create_reporter(DEBUG_MODE)
    except ImportError:
        pass
    
    def debug_log(message):
        """Helper function for debug logging"""
        if DEBUG_MODE:
            if logger:
                logger.debug(message)
            else:
                print(f"[DEBUG] {message}")
    
    debug_log(f"Core path: {nuke_path}")
    debug_log(f"TLA_COMP_PIPELINE_ROOT: {pipeline_root}")
    debug_log(f"TLA_COMP_TOOLCHAINS: {toolchains_path}")
    debug_log(f"Toolchains file: {config_file}")
    debug_log(f"Main config file: {main_config_file}")
    debug_log(f"Debug mode: {DEBUG_MODE}")
    
    # Add core icons path first so folder icons are available
    core_icons_path = nuke_path / 'icons'
    if core_icons_path.exists():
        nuke.pluginAddPath(str(core_icons_path))
        debug_log(f"Added core icons path: {core_icons_path}")
    
    # Load main configuration for menu commands and icons
    menu_commands = {}
    default_icons = {}
    category_icons = {}
    content_paths_config = {}
    if main_config_file.exists():
        with main_config_file.open('r') as f:
            main_config = json.load(f)
            menu_commands = main_config.get('menu_commands', {})
            content_paths_config = main_config.get('content_paths', {})
            
            # Load icons from dedicated icons section
            icons_config = main_config.get('icons', {})
            default_icons = icons_config.get('defaults', {})
            category_icons = icons_config.get('categories', {})
    
    if not config_file.exists():
        error_msg = f"Toolchains config not found: {config_file}"
        if logger:
            logger.error(error_msg)
        else:
            print(f"[ERROR] {error_msg}")
        return
    
    # Load toolchains configuration
    with config_file.open('r') as f:
        config = json.load(f)
    
    toolchains = config.get('toolchains', {})
    
    # Sort toolchains by priority (lower numbers load first)
    global_settings = config.get('global_settings', {})
    load_order = global_settings.get('load_order', 'priority')
    
    if load_order == 'priority':
        # Sort by priority (ascending - lower numbers first)
        sorted_toolchains = sorted(
            toolchains.items(), 
            key=lambda x: x[1].get('priority', 999)
        )
        debug_log("Loading toolchains in priority order:")
        for name, settings in sorted_toolchains:
            priority = settings.get('priority', 999)
            enabled = settings.get('enabled', False)
            debug_log(f"{name}: priority {priority}, enabled: {enabled}")
    else:
        # Use original order from config file
        sorted_toolchains = toolchains.items()
        debug_log("Loading toolchains in config file order")
    
    # Process each toolchain in sorted order
    for name, settings in sorted_toolchains:
        toolchain_start_time = time.time()
        
        # Always add disabled toolchains to reporter for complete overview
        version = settings.get('version', '1.0.0')
        build_menu = settings.get('build_menu', False)
        build_toolbar = settings.get('build_toolbar', False)
        enabled = settings.get('enabled', False)
        
        if not enabled:
            # Add disabled toolchain to reporter
            if reporter:
                reporter.add_toolchain(name, version, False, 0.0, build_menu, build_toolbar)
            continue
            
        if DEBUG_MODE:
            if logger:
                logger.info(f"Loading toolchain: {name}")
            else:
                print(f"Loading toolchain: {name}")
        
        # Build absolute path to toolchain using TLA_COMP_TOOLCHAINS
        folder_path = settings.get('folder_path', '')
        debug_log(f"Raw folder_path from config: {folder_path}")
        
        if Path(folder_path).is_absolute():
            # Absolute path
            toolchain_path = Path(folder_path)
            debug_log(f"Using absolute path: {toolchain_path}")
        else:
            # Relative path - combine with TLA_COMP_TOOLCHAINS
            toolchain_path = toolchains_path / folder_path
            debug_log(f"Combined with toolchains root: {toolchain_path}")
        
        debug_log(f"Final toolchain_path: {toolchain_path}")
            
        # Add version if it exists
        version_path = toolchain_path / version
        
        if version_path.exists():
            toolchain_path = version_path
        
        if not toolchain_path.exists():
            error_msg = f"Toolchain path not found: {toolchain_path}"
            if DEBUG_MODE:
                if logger:
                    logger.warning(error_msg)
                else:
                    print(f"[WARNING] {error_msg}")
            
            # Add failed toolchain to reporter
            if reporter:
                reporter.add_toolchain(name, version, False, 0.0, build_menu, build_toolbar)
            continue
            
        # Add the main toolchain path to plugin path so init.py/menu.py can run
        nuke.pluginAddPath(str(toolchain_path))
        if DEBUG_MODE:
            if logger:
                logger.info(f"  Added main toolchain path: {toolchain_path}")
            else:
                print(f"  Added main toolchain path: {toolchain_path}")
        debug_log(f"Final toolchain path as string: {str(toolchain_path)}")
            


        # Load toolchain components FIRST to ensure icons are available
        _load_toolchain_components(toolchain_path, name, settings, debug_log, main_config)
        
        # Build menus if requested
        if settings.get('build_menu', False):
            _build_menu(toolchain_path, name, settings, menu_commands, default_icons, category_icons, debug_log, main_config)
            
        if settings.get('build_toolbar', False):
            _build_toolbar(toolchain_path, name, settings, menu_commands, default_icons, category_icons, debug_log, main_config)
        
        # Calculate load time and add to reporter
        load_time = time.time() - toolchain_start_time
        if reporter:
            reporter.add_toolchain(name, version, True, load_time, build_menu, build_toolbar)

    
    # Print summary report
    if reporter:
        reporter.print_toolchains_summary()
    
    # Log performance metrics
    total_time = time.time() - start_time
    if LOGGER_AVAILABLE and DEBUG_MODE and logger:
        log_performance("toolchain_loading", total_time, {"toolchains_loaded": len([t for t in toolchains.values() if t.get('enabled', False)])})
        logger.info("===== TOOLCHAIN LOADING COMPLETE =====")
    
    # Complete the pipeline initialization report
    if reporter:
        reporter.print_completion_footer()




def _load_toolchain_components(toolchain_path, name, settings, debug_log, config=None):
    """Load gizmos, scripts, etc. from toolchain"""
    
    debug_log(f"Loading components for {name}")
    
    # Add icons path FIRST so they're available for menu/toolbar creation
    icons_path = toolchain_path / 'icons'
    if icons_path.exists():
        nuke.pluginAddPath(str(icons_path))
        debug_log(f"Added icons path: {icons_path}")
    
    # Get content types from config or use defaults
    if config:
        content_paths_config = config.get('content_paths', {})
    else:
        content_paths_config = {}
    
    default_content_paths = {
        'gizmos': {'folder': 'gizmos', 'extensions': ['.gizmo']},
        'scripts': {'folder': 'scripts', 'extensions': ['.py']},
        'python': {'folder': 'python', 'extensions': ['.py']},
        'toolsets': {'folder': 'toolsets', 'extensions': ['.nk']}
    }
    
    # Merge with defaults
    for content_type, default_config in default_content_paths.items():
        if content_type not in content_paths_config:
            content_paths_config[content_type] = default_config
    
    # Add plugin paths for each content type
    for content_type, type_config in content_paths_config.items():
        folder_name = type_config.get('folder', content_type)
        content_path = toolchain_path / folder_name
        
        if content_path.exists():
            _add_plugin_paths_recursive(content_path, content_type, debug_log)


def _add_plugin_paths_recursive(base_path, path_type, debug_log):
    """Recursively add plugin paths for a directory"""
    
    nuke.pluginAddPath(str(base_path))
    debug_log(f"Added {path_type} path: {base_path}")
    
    # Also add subdirectories
    for dir_path in base_path.rglob('*'):
        if dir_path.is_dir():
            nuke.pluginAddPath(str(dir_path))
            debug_log(f"Added {path_type} subpath: {dir_path}")


def _build_menu(toolchain_path, name, settings, menu_commands, default_icons, category_icons, debug_log, config):
    """Build category-based menu for toolchain in main menubar"""
    
    display_name = settings.get('display_name', name)
    menu_icon = settings.get('menu_icon', '')
    
    debug_log(f"Building category-based menu for {display_name}")
    
    # Create main toolchain menu in menubar
    menubar = nuke.menu('Nuke')
    if menu_icon:
        toolchain_menu = menubar.addMenu(display_name, icon=menu_icon)
        debug_log(f"Added menu '{display_name}' with icon: {menu_icon}")
    else:
        toolchain_menu = menubar.addMenu(display_name)
        debug_log(f"Added menu '{display_name}' without icon")
    
    # Build category-based menus
    _build_category_menus(toolchain_menu, toolchain_path, menu_commands, default_icons, category_icons, debug_log, config)
    
    debug_log(f"Built category-based menu: {display_name}")


def _build_toolbar(toolchain_path, name, settings, menu_commands, default_icons, category_icons, debug_log, config):
    """Build category-based toolbar for toolchain in Nodes toolbar area"""
    
    display_name = settings.get('display_name', name)
    menu_icon = settings.get('menu_icon', '')
    
    debug_log(f"Building category-based toolbar for {display_name}")
    
    # Create toolbar in Nodes area
    toolbar = nuke.menu('Nodes')
    
    if menu_icon:
        try:
            toolchain_toolbar = toolbar.addMenu(display_name, icon=menu_icon)
            debug_log(f"Successfully added toolbar menu '{display_name}' with icon: {menu_icon}")
        except Exception as e:
            debug_log(f"Failed to add icon {menu_icon}, adding without icon. Error: {e}")
            toolchain_toolbar = toolbar.addMenu(display_name)
    else:
        debug_log(f"No icon specified for {display_name}, adding toolbar menu without icon")
        toolchain_toolbar = toolbar.addMenu(display_name)
    
    # Build category-based toolbar menus
    _build_category_menus(toolchain_toolbar, toolchain_path, menu_commands, default_icons, category_icons, debug_log, config)
    
    debug_log(f"Built category-based toolbar: {display_name}")


def _build_category_menus(parent_menu, toolchain_path, menu_commands, default_icons, category_icons, debug_log, config):
    """Build category-based submenus with content organized by category folders, or fallback to content-type organization"""
    
    debug_log("Building category-based menus...")
    
    # Get content types from config
    content_paths_config = config.get('content_paths', {
        'gizmos': {'folder': 'gizmos', 'extensions': ['.gizmo']},
        'scripts': {'folder': 'scripts', 'extensions': ['.py']},
        'python': {'folder': 'python', 'extensions': ['.py']},
        'toolsets': {'folder': 'toolsets', 'extensions': ['.nk']}
    })
    
    # Collect all available categories from all content types
    categories = set()
    content_paths = {}
    
    # Build content paths from config
    for content_type, type_config in content_paths_config.items():
        folder_name = type_config.get('folder', content_type)
        content_paths[content_type] = toolchain_path / folder_name
    
    # Only look in whitelisted content type folders
    for content_type, base_path in content_paths.items():
        if base_path.exists():
            debug_log(f"Checking {content_type} folder: {base_path}")
            for item in base_path.iterdir():
                if item.is_dir():
                    folder_name = item.name
                    
                    # Check if this folder contains the relevant file types based on config
                    has_content = False
                    type_config = content_paths_config.get(content_type, {})
                    extensions = type_config.get('extensions', [])
                    
                    found_files = []
                    for ext in extensions:
                        pattern = f'*{ext}'
                        found_files.extend(list(item.rglob(pattern)))
                    
                    has_content = len(found_files) > 0
                    if has_content:
                        debug_log(f"Found category '{folder_name}' with {len(found_files)} files ({extensions})")
                    
                    if has_content:
                        categories.add(folder_name)
                    else:
                        debug_log(f"Skipping empty folder: {folder_name}")
    
    debug_log(f"Found categories: {sorted(categories)}")
    
    # If no categories found, fall back to content-type organization
    if not categories:
        debug_log("No category subfolders found, using content-type fallback organization")
        _build_content_type_fallback(parent_menu, toolchain_path, menu_commands, default_icons, debug_log, config)
        return
    
    # Create menus for each category
    for category in sorted(categories):
        # First try to get specific category icon, fallback to default folder icon
        category_icon = category_icons.get(category)
        if not category_icon:
            category_icon = default_icons.get('folder', 'folder.png')
            debug_log(f"No specific icon for category '{category}', using fallback: {category_icon}")
        
        category_menu = parent_menu.addMenu(category, icon=category_icon)
        debug_log(f"Created category menu: {category} with icon: {category_icon}")
        
        # Track if we've added any content to determine separator placement
        content_added = False
        
        # Get content types from config
        content_paths_config = config.get('content_paths', {
            'gizmos': {'folder': 'gizmos', 'extensions': ['.gizmo']},
            'scripts': {'folder': 'scripts', 'extensions': ['.py']},
            'python': {'folder': 'python', 'extensions': ['.py']},
            'toolsets': {'folder': 'toolsets', 'extensions': ['.nk']}
        })
        
        # Process each content type for this category
        for content_type, type_config in content_paths_config.items():
            folder_name = type_config.get('folder', content_type)
            content_type_path = toolchain_path / folder_name / category
            
            if content_type_path.exists():
                debug_log(f"Adding {content_type} from: {content_type_path}")
                
                # Add separator if we already have content
                if content_added:
                    category_menu.addSeparator()
                    debug_log(f"Added separator before {content_type} in {category}")
                
                # Add the appropriate items based on content type
                if content_type == 'gizmos':
                    extensions = type_config.get('extensions', ['.gizmo'])
                    _add_gizmo_items(category_menu, content_type_path, menu_commands, default_icons, debug_log, extensions)
                elif content_type in ['scripts', 'python']:
                    extensions = type_config.get('extensions', ['.py'])
                    _add_script_items(category_menu, content_type_path, menu_commands, default_icons, debug_log, extensions)
                elif content_type == 'toolsets':
                    extensions = type_config.get('extensions', ['.nk'])
                    _add_toolset_items(category_menu, content_type_path, menu_commands, default_icons, debug_log, extensions)
                
                content_added = True
        
        if not content_added:
            debug_log(f"No content found for category: {category}")
    
    debug_log("Category-based menu building complete")


def _build_content_type_fallback(parent_menu, toolchain_path, menu_commands, default_icons, debug_log, config):
    """Fallback to organize content by type (scripts, gizmos, toolsets) when no category folders exist"""
    
    debug_log("Building content-type fallback menu organization...")
    
    # Get content types from config
    content_paths_config = config.get('content_paths', {
        'gizmos': {'folder': 'gizmos', 'extensions': ['.gizmo']},
        'scripts': {'folder': 'scripts', 'extensions': ['.py']},
        'python': {'folder': 'python', 'extensions': ['.py']},
        'toolsets': {'folder': 'toolsets', 'extensions': ['.nk']}
    })
    
    content_paths = {}
    # Build content paths from config
    for content_type, type_config in content_paths_config.items():
        folder_name = type_config.get('folder', content_type)
        content_paths[content_type] = toolchain_path / folder_name
    
    content_added = False
    
    # Process each content type based on config
    for content_type, content_path in content_paths.items():
        if content_path.exists():
            debug_log(f"Checking {content_type} in: {content_path}")
            
            # Get extensions for this content type
            type_config = content_paths_config.get(content_type, {})
            extensions = type_config.get('extensions', [])
            
            # Find all files with the appropriate extensions
            found_files = []
            for ext in extensions:
                pattern = f'*{ext}'
                found_files.extend(list(content_path.rglob(pattern)))
            
            if found_files:
                debug_log(f"Found {len(found_files)} {extensions} files, adding {content_type} section")
                
                # Add separator if we already have content
                if content_added:
                    parent_menu.addSeparator()
                    debug_log(f"Added separator before {content_type}")
                
                # Add the appropriate items based on content type
                if content_type == 'gizmos':
                    _add_gizmo_items(parent_menu, content_path, menu_commands, default_icons, debug_log, extensions)
                elif content_type in ['scripts', 'python']:
                    _add_script_items(parent_menu, content_path, menu_commands, default_icons, debug_log, extensions)
                elif content_type == 'toolsets':
                    _add_toolset_items(parent_menu, content_path, menu_commands, default_icons, debug_log, extensions)
                
                content_added = True
            else:
                debug_log(f"No {extensions} files found in {content_path}")
    
    if not content_added:
        debug_log("No content found for fallback organization")
    else:
        debug_log(f"Successfully built fallback menu with content")
    
    debug_log("Content-type fallback menu building complete")


def _add_script_items(menu, scripts_path, menu_commands, default_icons, debug_log, extensions=['.py']):
    """Add Python scripts as menu items, creating submenus for folders"""
    
    if not scripts_path.exists():
        return
    
    script_command = menu_commands.get('script_command', 'exec(open(r\'{}\').read())')
    script_icon = default_icons.get('script', 'OpenScript.png')
    python_icon = default_icons.get('python', 'python.png')
    folder_icon = default_icons.get('folder', 'folder.png')
        
    for item in sorted(scripts_path.iterdir()):
        if item.is_dir():
            # Check if this folder contains any files with the configured extensions
            valid_files = []
            for ext in extensions:
                pattern = f'*{ext}'
                valid_files.extend(list(item.rglob(pattern)))
            # Filter out files that start with '_' (like __pycache__)
            valid_files = [f for f in valid_files if not f.name.startswith('_')]
            if valid_files:
                # Create submenu for folder with icon only if it contains valid files
                submenu = menu.addMenu(item.name, icon=folder_icon)
                debug_log(f"Added folder {item.name} with icon: {folder_icon} ({len(valid_files)} files)")
                _add_script_items(submenu, item, menu_commands, default_icons, debug_log, extensions)
            else:
                debug_log(f"Skipped empty folder: {item.name} (no {extensions} files)")
            
        elif item.suffix in extensions and not item.name.startswith('_'):
            script_name = item.stem
            display_name = _parse_display_name(script_name)
            
            # Choose icon based on content type
            icon_to_use = python_icon if item.suffix == '.py' else script_icon
            
            # Create menu item using configured command with icon
            if 'nuke.load' in script_command:
                # Convert to forward slashes for Nuke
                item_str = str(item).replace('\\', '/')
                base_command = f'nuke.load(r"{item_str}")'
                # Add simple logging to the command (avoid quote conflicts)
                full_command = f'print("[EXECUTE] SCRIPT: {script_name}"); {base_command}; print("[SUCCESS] SCRIPT: {script_name} executed")'
                menu.addCommand(display_name, full_command, icon=icon_to_use)
                debug_log(f"[MENU] Added script: '{display_name}' -> Command: '{base_command}' -> Icon: '{icon_to_use}'")
            else:
                # Use the configured command with proper formatting
                item_str = str(item).replace('\\', '/')
                base_command = script_command.format(item_str)
                # Add simple logging to the command (avoid quote conflicts)
                full_command = f'print("[EXECUTE] SCRIPT: {script_name}"); {base_command}; print("[SUCCESS] SCRIPT: {script_name} executed")'
                menu.addCommand(display_name, full_command, icon=icon_to_use)
                debug_log(f"[MENU] Added script: '{display_name}' -> Command: '{base_command}' -> Icon: '{icon_to_use}'")


def _add_toolset_items(menu, toolsets_path, menu_commands, default_icons, debug_log, extensions=['.nk']):
    """Add toolsets as menu items, creating submenus for folders"""
    
    if not toolsets_path.exists():
        return
    
    toolset_command = menu_commands.get('toolset_command', 'nuke.loadToolset')
    toolset_icon = default_icons.get('toolset', 'toolset.png')
    folder_icon = default_icons.get('folder', 'folder.png')
        
    for item in sorted(toolsets_path.iterdir()):
        if item.is_dir():
            # Check if this folder contains any files with the configured extensions
            valid_files = []
            for ext in extensions:
                pattern = f'*{ext}'
                valid_files.extend(list(item.rglob(pattern)))
            if valid_files:
                # Create submenu for folder with icon only if it contains valid files
                submenu = menu.addMenu(item.name, icon=folder_icon)
                debug_log(f"Added folder {item.name} with icon: {folder_icon} ({len(valid_files)} toolsets)")
                _add_toolset_items(submenu, item, menu_commands, default_icons, debug_log, extensions)
            else:
                debug_log(f"Skipped empty folder: {item.name} (no {extensions} files)")
            
        elif item.suffix in extensions:
            toolset_name = item.stem
            display_name = _parse_display_name(toolset_name)
            
            # Create menu item using configured command with icon
            if 'nuke.nodePaste' in toolset_command:
                # Convert to forward slashes for Nuke
                item_str = str(item).replace('\\', '/')
                base_command = f"nuke.nodePaste(r'{item_str}')"
                # Add simple logging to the command (avoid quote conflicts)
                full_command = f'print("[EXECUTE] TOOLSET: {toolset_name}"); {base_command}; print("[SUCCESS] TOOLSET: {toolset_name} executed")'
                menu.addCommand(display_name, full_command, icon=toolset_icon)
                debug_log(f"[MENU] Added toolset: '{display_name}' -> Command: '{base_command}' -> Icon: '{toolset_icon}'")
            elif 'nuke.loadToolset' in toolset_command:
                # Convert to forward slashes for Nuke
                item_str = str(item).replace('\\', '/')
                base_command = f"nuke.loadToolset(r'{item_str}')"
                # Add simple logging to the command (avoid quote conflicts)
                full_command = f'print("[EXECUTE] TOOLSET: {toolset_name}"); {base_command}; print("[SUCCESS] TOOLSET: {toolset_name} executed")'
                menu.addCommand(display_name, full_command, icon=toolset_icon)
                debug_log(f"[MENU] Added toolset: '{display_name}' -> Command: '{base_command}' -> Icon: '{toolset_icon}'")
            else:
                # Use the configured command with proper formatting
                item_str = str(item).replace('\\', '/')
                base_command = toolset_command.format(item_str)
                # Add simple logging to the command (avoid quote conflicts)
                full_command = f'print("[EXECUTE] TOOLSET: {toolset_name}"); {base_command}; print("[SUCCESS] TOOLSET: {toolset_name} executed")'
                menu.addCommand(display_name, full_command, icon=toolset_icon)
                debug_log(f"[MENU] Added toolset: '{display_name}' -> Command: '{base_command}' -> Icon: '{toolset_icon}'")


def _add_gizmo_items(menu, gizmos_path, menu_commands, default_icons, debug_log, extensions=['.gizmo']):
    """Add gizmos as menu items, creating submenus for folders"""
    
    if not gizmos_path.exists():
        return
    
    gizmo_command = menu_commands.get('gizmo_command', 'nuke.createNode')
    gizmo_icon = default_icons.get('gizmo', 'gizmo.png')
    folder_icon = default_icons.get('folder', 'folder.png')
        
    for item in sorted(gizmos_path.iterdir()):
        if item.is_dir():
            # Check if this folder contains any files with the configured extensions
            valid_files = []
            for ext in extensions:
                pattern = f'*{ext}'
                valid_files.extend(list(item.rglob(pattern)))
            if valid_files:
                # Create submenu for folder with icon only if it contains valid files
                submenu = menu.addMenu(item.name, icon=folder_icon)
                debug_log(f"Added folder {item.name} with icon: {folder_icon} ({len(valid_files)} gizmos)")
                _add_gizmo_items(submenu, item, menu_commands, default_icons, debug_log, extensions)
            else:
                debug_log(f"Skipped empty folder: {item.name} (no {extensions} files)")
            
        elif item.suffix in extensions:
            gizmo_name = item.stem
            display_name = _parse_display_name(gizmo_name)
            
            # Create menu item using configured command with icon
            # Use the file path approach like in nukeToolsLibrary.py example
            if 'nuke.createNode' in gizmo_command:
                # Convert to forward slashes for Nuke
                item_str = str(item).replace('\\', '/')
                base_command = f'nuke.createNode(r"{item_str}")'
                # Add simple logging to the command (avoid quote conflicts)
                full_command = f'print("[EXECUTE] GIZMO: {gizmo_name}"); {base_command}; print("[SUCCESS] GIZMO: {gizmo_name} executed")'
                menu.addCommand(display_name, full_command, icon=gizmo_icon)
                debug_log(f"[MENU] Added gizmo: '{display_name}' -> Command: '{base_command}' -> Icon: '{gizmo_icon}'")
            else:
                # Use the configured command with proper formatting (using file path)
                item_str = str(item).replace('\\', '/')
                base_command = gizmo_command.format(item_str)
                # Add simple logging to the command (avoid quote conflicts)
                full_command = f'print("[EXECUTE] GIZMO: {gizmo_name}"); {base_command}; print("[SUCCESS] GIZMO: {gizmo_name} executed")'
                menu.addCommand(display_name, full_command, icon=gizmo_icon)
                debug_log(f"[MENU] Added gizmo: '{display_name}' -> Command: '{base_command}' -> Icon: '{gizmo_icon}'")


