"""
MenuBuilder.py - Modern Python 3 menu building utilities for Nuke

This module provides a flexible, configurable way to build Nuke menus and toolbars
from toolchain configurations with proper Nuke plugin path management.
"""

import os
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Union, Any

try:
    import nuke
except ImportError:
    # Allow module to be imported outside of Nuke for testing
    nuke = None

logger = logging.getLogger(__name__)


class MenuBuilder:
    """
    A modern, configurable menu builder for Nuke that dynamically creates
    menus and toolbars based on toolchain configurations.
    
    This version properly integrates with Nuke's plugin system by:
    1. Adding toolchain paths to nuke.addPluginPath()
    2. Dynamically discovering standard directories (gizmos, scripts, toolsets, icons)
    3. Creating menus/toolbars based on toolchain configuration
    """
    
    # Standard toolchain directory structure
    STANDARD_DIRS = {
        'gizmos': {
            'extensions': ['.gizmo'],
            'command': 'nuke.createNode',
            'icon_fallback': 'gizmo'
        },
        'scripts': {
            'extensions': ['.py'],
            'command': 'nuke.load',
            'icon_fallback': 'script'
        },
        'toolsets': {
            'extensions': ['.nk'],
            'command': 'nuke.nodePaste', 
            'icon_fallback': 'toolset'
        },
        'icons': {
            'extensions': ['.png', '.jpg', '.jpeg', '.svg', '.ico'],
            'command': None,  # Icons are not executable
            'icon_fallback': None
        }
    }
    
    def __init__(self, config_path: Union[str, Path], toolchains_path: Union[str, Path]):
        """
        Initialize the MenuBuilder with configuration paths.
        
        Args:
            config_path: Path to the main config.json file
            toolchains_path: Path to the toolchains.json file
        """
        self.config_path = Path(config_path)
        self.toolchains_path = Path(toolchains_path)
        self.config = self._load_config()
        self.toolchains_config = self._load_toolchains_config()
        self.default_icons = self.config.get("menu_commands", {}).get("default_icons", {})
        
        # Set up commands from config with fallbacks
        menu_commands = self.config.get("menu_commands", {})
        self.commands = {
            'gizmos': menu_commands.get('gizmo_command', 'nuke.createNode'),
            'scripts': menu_commands.get('script_command', 'nuke.load'),
            'toolsets': menu_commands.get('toolset_command', 'nuke.nodePaste')
        }
        
        if nuke:
            self.menubar = nuke.menu("Nuke")
            self.toolbar = nuke.toolbar("Nodes")
        else:
            self.menubar = None
            self.toolbar = None
    
    def _load_config(self) -> Dict[str, Any]:
        """Load the main configuration file."""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logger.error(f"Failed to load config from {self.config_path}: {e}")
            return {}
    
    def _load_toolchains_config(self) -> Dict[str, Any]:
        """Load the toolchains configuration file."""
        try:
            with open(self.toolchains_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logger.error(f"Failed to load toolchains from {self.toolchains_path}: {e}")
            return {}
    
    def build_toolchain_menus(self) -> None:
        """Build all enabled toolchain menus based on configuration."""
        if not (self.menubar and self.toolbar):
            logger.error("Nuke menu objects not available")
            return
        
        toolchains = self.toolchains_config.get("toolchains", {})
        
        if not toolchains:
            logger.warning("No toolchains found in configuration")
            return
        
        # Sort toolchains by priority
        sorted_toolchains = sorted(
            [(name, config) for name, config in toolchains.items()],
            key=lambda x: x[1].get("priority", 999)
        )
        
        enabled_count = 0
        disabled_count = 0
        
        for toolchain_name, toolchain_config in sorted_toolchains:
            if not toolchain_config.get("enabled", False):
                disabled_count += 1
                display_name = toolchain_config.get("display_name", toolchain_name)
                version = toolchain_config.get("version", "unknown")
                logger.info(f"Toolchain '{display_name}' (v{version}) found but DISABLED - skipping")
                continue
            
            enabled_count += 1
            self._register_toolchain(toolchain_name, toolchain_config)
        
        # Log summary
        total_count = enabled_count + disabled_count
        logger.info(f"Toolchain registration complete: {enabled_count}/{total_count} toolchains enabled")
        
        if disabled_count > 0:
            logger.info(f"Note: {disabled_count} toolchain(s) found but disabled in configuration")
    
    def _register_toolchain(self, name: str, config: Dict[str, Any]) -> None:
        """
        Register a single toolchain with Nuke's plugin system and create menus.
        
        Args:
            name: Name of the toolchain
            config: Toolchain configuration dictionary
        """
        display_name = config.get("display_name", name)
        folder_path = config.get("folder_path", "")
        version = config.get("version", "unknown")
        
        if not folder_path:
            logger.warning(f"No folder_path specified for toolchain: {name}")
            return
        
        # Append version to folder path to get the full versioned path
        versioned_folder_path = f"{folder_path}/{version}"
        
        # Resolve relative path from the config directory
        config_dir = self.toolchains_path.parent
        base_path = (config_dir / versioned_folder_path).resolve()
        
        if not base_path.exists():
            logger.error(f"Toolchain path does not exist: {base_path}")
            return
        
        logger.info(f"Registering toolchain '{display_name}' (v{version}) from {base_path}")
        
        # Add to Nuke's plugin path - this is crucial for proper Nuke integration
        if nuke:
            nuke.addPluginPath(str(base_path))
            logger.debug(f"Added to Nuke plugin path: {base_path}")
        
        # Discover and register content
        discovered_content = self._discover_toolchain_content(base_path)
        
        if not any(discovered_content.values()):
            logger.warning(f"No standard content directories found in {base_path}")
            return
        
        # Create menus/toolbars based on configuration
        if config.get("build_menu", False):
            self._create_toolchain_menu(name, config, base_path, discovered_content, self.menubar)
        
        if config.get("build_toolbar", False):
            self._create_toolchain_menu(name, config, base_path, discovered_content, self.toolbar)
        
        logger.info(f"Successfully registered toolchain '{display_name}'")
    
    def _discover_toolchain_content(self, base_path: Path) -> Dict[str, List[Path]]:
        """
        Dynamically discover standard directories in a toolchain.
        Recursively scans all subdirectories for content files.
        
        Args:
            base_path: Base path of the toolchain
            
        Returns:
            Dict mapping directory names to lists of content files
        """
        discovered = {}
        
        for dir_name, dir_info in self.STANDARD_DIRS.items():
            dir_path = base_path / dir_name
            discovered[dir_name] = []
            
            if not dir_path.exists():
                logger.debug(f"Directory not found: {dir_path}")
                continue
            
            # Find all files with matching extensions recursively
            extensions = dir_info['extensions']
            files = []
            
            for ext in extensions:
                # Use rglob to find files recursively in all subdirectories
                pattern_files = list(dir_path.rglob(f"*{ext}"))
                files.extend(pattern_files)
                logger.debug(f"Found {len(pattern_files)} files with extension {ext} in {dir_path}")
            
            # Sort files by their full path for consistent ordering
            discovered[dir_name] = sorted(files, key=lambda p: str(p))
            
            if files:
                logger.info(f"Found {len(files)} {dir_name} files in {dir_path} (including subdirectories)")
                # Log a few examples for debugging
                for i, file_path in enumerate(files[:3]):
                    rel_path = file_path.relative_to(base_path)
                    logger.debug(f"  Example {i+1}: {rel_path}")
                if len(files) > 3:
                    logger.debug(f"  ... and {len(files) - 3} more files")
        
        return discovered
    
    def _create_toolchain_menu(self, 
                              name: str, 
                              config: Dict[str, Any], 
                              base_path: Path,
                              content: Dict[str, List[Path]], 
                              parent_menu: Any) -> None:
        """
        Create menu structure for a toolchain.
        
        Args:
            name: Toolchain name
            config: Toolchain configuration
            base_path: Base path of toolchain
            content: Discovered content dictionary
            parent_menu: Parent menu object (menubar or toolbar)
        """
        display_name = config.get("display_name", name)
        
        # Get main menu icon
        menu_icon = self._get_toolchain_icon(config, base_path)
        
        # Create main menu
        main_menu = parent_menu.addMenu(f"&{display_name}", icon=menu_icon)
        
        # Add submenus for each content type that has files
        for dir_name in ['gizmos', 'scripts', 'toolsets']:  # Skip icons
            files = content.get(dir_name, [])
            if not files:
                continue
                
            dir_info = self.STANDARD_DIRS[dir_name]
            command = self.commands.get(dir_name, dir_info['command'])
            
            # Create submenu
            submenu_icon = self._get_default_icon(dir_info['icon_fallback'])
            submenu_name = dir_name.replace('_', ' ').title()
            submenu = main_menu.addMenu(submenu_name, icon=submenu_icon)
            
            # Add files to submenu
            self._populate_menu_with_files(submenu, files, base_path, command, dir_name)
    
    def _populate_menu_with_files(self, 
                                 menu: Any, 
                                 files: List[Path], 
                                 base_path: Path,
                                 command: str, 
                                 content_type: str) -> None:
        """
        Populate a menu with files, creating subdirectories as needed.
        Recursively creates nested menus for subdirectory structures.
        
        Args:
            menu: Menu object to populate
            files: List of file paths
            base_path: Base path for the toolchain
            command: Command to execute for files
            content_type: Type of content (gizmos, scripts, toolsets)
        """
        if not files:
            logger.debug(f"No files to populate for {content_type}")
            return
            
        # Group files by their relative directory structure
        dir_menus = {}
        content_dir = base_path / content_type
        
        logger.debug(f"Populating menu with {len(files)} {content_type} files")
        
        for file_path in files:
            try:
                # Get relative path from the content type directory
                rel_path = file_path.relative_to(content_dir)
                parent_dir = rel_path.parent
                
                # Determine target menu
                if parent_dir == Path('.'):
                    # File is directly in the content directory
                    target_menu = menu
                    logger.debug(f"Adding {rel_path.name} to root menu")
                else:
                    # File is in a subdirectory - create nested menus
                    target_menu = self._get_or_create_nested_menu(menu, parent_dir, dir_menus, content_dir)
                    logger.debug(f"Adding {rel_path.name} to submenu: {parent_dir}")
                
                # Add the file as a menu item
                file_name = file_path.stem  # Remove extension
                icon_path = self._find_file_icon(file_path, base_path)
                
                # Create appropriate command based on content type
                if content_type == 'gizmos':
                    # For gizmos, we need just the node name (filename without extension)
                    command_string = f'{command}("{file_name}")'
                elif content_type == 'scripts':
                    # For scripts, use full path with forward slashes for cross-platform compatibility
                    script_path = str(file_path).replace('\\', '/')
                    command_string = f'exec(open(r"{script_path}").read())'
                elif content_type == 'toolsets':
                    # For toolsets, use nuke.nodePaste with file path
                    toolset_path = str(file_path).replace('\\', '/')
                    command_string = f'{command}(file=r"{toolset_path}")'
                else:
                    # Default fallback
                    command_string = f'{command}("{file_path}")'
                
                # Add menu item
                target_menu.addCommand(file_name, command_string, icon=icon_path)
                logger.debug(f"Added menu command: {file_name} -> {command_string}")
                
            except Exception as e:
                logger.error(f"Error adding menu item for {file_path}: {e}")
                import traceback
                logger.debug(traceback.format_exc())
    
    def _get_or_create_nested_menu(self, 
                                  parent_menu: Any, 
                                  rel_path: Path, 
                                  dir_menus: Dict[str, Any],
                                  content_dir: Path) -> Any:
        """
        Get or create nested menu structure for subdirectories.
        
        Args:
            parent_menu: Parent menu object
            rel_path: Relative path for the nested structure
            dir_menus: Cache of already created directory menus
            content_dir: Base content directory for logging
            
        Returns:
            Menu object for the target directory
        """
        path_str = str(rel_path)
        
        if path_str in dir_menus:
            return dir_menus[path_str]
        
        # Create nested structure step by step
        current_menu = parent_menu
        path_parts = rel_path.parts
        
        for i, part in enumerate(path_parts):
            # Build partial path for this level
            partial_path = str(Path(*path_parts[:i+1]))
            
            if partial_path not in dir_menus:
                # Create new submenu for this directory level
                folder_icon = self._get_default_icon('folder')
                submenu = current_menu.addMenu(part, icon=folder_icon)
                dir_menus[partial_path] = submenu
                logger.debug(f"Created submenu: {partial_path} in {content_dir}")
            
            current_menu = dir_menus[partial_path]
        
        return current_menu
    
    def _get_toolchain_icon(self, config: Dict[str, Any], base_path: Path) -> str:
        """Get icon for the main toolchain menu."""
        menu_icon = config.get("menu_icon", "")
        
        if menu_icon:
            # Check if it's an absolute path
            if Path(menu_icon).is_absolute() and Path(menu_icon).exists():
                return menu_icon
                
            # Check in toolchain icons directory
            icon_path = base_path / "icons" / menu_icon
            if icon_path.exists():
                return str(icon_path)
                
            # Check in toolchain root
            icon_path = base_path / menu_icon
            if icon_path.exists():
                return str(icon_path)
        
        # Fall back to default
        return self._get_default_icon('folder')
    
    def _find_file_icon(self, file_path: Path, base_path: Path) -> str:
        """Find an icon for a specific file."""
        file_stem = file_path.stem
        
        # Check for icon with same name in icons directory
        icons_dir = base_path / "icons"
        if icons_dir.exists():
            for ext in ['.png', '.jpg', '.jpeg', '.svg', '.ico']:
                icon_path = icons_dir / f"{file_stem}{ext}"
                if icon_path.exists():
                    return str(icon_path)
        
        # Check for icon in same directory as file
        for ext in ['.png', '.jpg', '.jpeg', '.svg', '.ico']:
            icon_path = file_path.parent / f"{file_stem}{ext}"
            if icon_path.exists():
                return str(icon_path)
        
        # Determine default icon based on file type
        file_ext = file_path.suffix.lower()
        if file_ext == '.gizmo':
            return self._get_default_icon('gizmo')
        elif file_ext == '.py':
            return self._get_default_icon('script')
        elif file_ext == '.nk':
            return self._get_default_icon('toolset')
        else:
            return ""
    
    def _get_default_icon(self, icon_type: str) -> str:
        """Get default icon path for a given type."""
        icon_name = self.default_icons.get(icon_type, "")
        if not icon_name:
            return ""
        
        # If relative path, make it absolute relative to config
        if not Path(icon_name).is_absolute():
            return str(self.config_path.parent / icon_name)
        
        return icon_name

def initialize_menus(config_dir: Union[str, Path]) -> MenuBuilder:
    """
    Initialize and build all menus from configuration.
    
    Args:
        config_dir: Directory containing config.json and toolchains.json
        
    Returns:
        MenuBuilder instance
    """
    config_dir = Path(config_dir)
    config_path = config_dir / "config.json"
    toolchains_path = config_dir / "toolchains.json"
    
    builder = MenuBuilder(config_path, toolchains_path)
    builder.build_toolchain_menus()
    
    return builder
