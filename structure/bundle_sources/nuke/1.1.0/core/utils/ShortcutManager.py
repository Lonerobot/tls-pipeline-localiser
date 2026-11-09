"""
Nuke Shortcuts Manager

A comprehensive class for registering and managing custom keyboard shortcuts in Nuke.
Loads shortcuts from shortcuts.json configuration file for flexible management.
All utility functions are imported from organized modules in python/shortcuts/

Author: Pipeline Team
Date: July 2025
"""

import nuke
import nukescripts
import json
import os
from pathlib import Path
from typing import Callable, Optional, Dict, List, Union
from .PipelineLogger import get_logger


class ShortcutManager:
    """
    A class to handle registration and management of custom keyboard shortcuts in Nuke.
    
    Loads shortcuts from shortcuts.json configuration file and provides a clean interface 
    for registering shortcuts with proper validation, error handling, and logging.
    
    All utility functions are now imported from organized modules in python/shortcuts/
    """
    
    def __init__(self, logger_name: str = "ShortcutManager", config_file: str = None):
        """
        Initialize the ShortcutManager.
        
        Args:
            logger_name (str): Name for the logger instance
            config_file (str): Path to shortcuts.json config file (auto-detected if None)
        """
        self.logger = get_logger(logger_name)
        self.registered_shortcuts: Dict[str, Dict] = {}
        self.config_file = config_file or self._find_config_file()
        self.config = {}
        self.main_config = {}  # Store main config.json for global settings
        self.utility_functions = {}
        self.debug_mode = self._get_debug_mode()
        
        # Load main configuration first to check if shortcuts are enabled
        self._load_main_config()
        
        # Import utility functions from organized modules
        self._load_utility_functions()
        
        # Load shortcuts configuration if shortcuts are enabled
        if self._are_shortcuts_enabled() and self.config_file and Path(self.config_file).exists():
            self.load_config()
        elif not self._are_shortcuts_enabled():
            self.logger.info("Shortcuts disabled in main configuration - skipping shortcuts.json")
        else:
            self.logger.warning(f"Shortcuts config file not found: {self.config_file}")
        
        if self.debug_mode:
            self.logger.info("ShortcutManager initialized")
    
    def _find_config_file(self) -> str:
        """Find the shortcuts.json config file automatically."""
        # Look in the same directory as this file's parent (core config directory)
        current_dir = Path(__file__).parent.parent
        config_path = current_dir / "shortcuts.json"
        return str(config_path)
    
    def _load_main_config(self):
        """Load the main config.json file to check global settings."""
        try:
            config_path = Path(__file__).parent.parent / "config.json"
            if config_path.exists():
                with open(config_path, 'r') as f:
                    self.main_config = json.load(f)
                if self.debug_mode:
                    self.logger.info(f"Loaded main config from: {config_path}")
            else:
                self.logger.warning(f"Main config file not found: {config_path}")
        except Exception as e:
            self.logger.error(f"Failed to load main config: {e}")
    
    def _are_shortcuts_enabled(self) -> bool:
        """Check if shortcuts are enabled in the main configuration."""
        shortcuts_config = self.main_config.get('shortcuts', {})
        return shortcuts_config.get('enabled', True)  # Default to enabled
    
    def _load_utility_functions(self):
        """Load utility functions from organized modules in python/shortcuts/"""
        try:
            # Add the python directory to sys.path so we can import shortcuts directly
            import sys
            core_path = str(Path(__file__).parent.parent)  # Go from utils/ back to core/
            python_path = str(Path(core_path) / "python")
            
            if python_path not in sys.path:
                sys.path.insert(0, python_path)
            
            if self.debug_mode:
                self.logger.info(f"Added python path to sys.path: {python_path}")
                self.logger.info(f"Looking for shortcuts module at: {python_path}/shortcuts")
                
                # Check if the path exists
                shortcuts_path = Path(python_path) / "shortcuts"
                if shortcuts_path.exists():
                    self.logger.info(f"shortcuts directory exists: {shortcuts_path}")
                    init_file = shortcuts_path / "__init__.py"
                    if init_file.exists():
                        self.logger.info(f"__init__.py file exists: {init_file}")
                    else:
                        self.logger.warning(f"__init__.py file missing: {init_file}")
                else:
                    self.logger.error(f"shortcuts directory does not exist: {shortcuts_path}")
            
            # Import all utility functions from the shortcuts package
            from shortcuts import (
                # Basic utilities
                select_all_nodes, deselect_all_nodes, frame_selected, frame_all,
                duplicate_selected, list_available_nodes, PasteFromClipboard2,
                
                # Node creation
                create_custom_grade_setup, create_read_write_setup,
                create_keying_setup, create_comp_setup,
                
                # Workflow setups
                create_gizmo_with_backdrop, load_custom_gizmo_from_path,
                create_render_setup, create_dailies_setup,
                
                # Viewer utilities
                toggle_overlay, reset_viewer, fit_viewer,
                toggle_viewer_channels, toggle_viewer_gain, center_viewer
            )
            
            # Store utility functions for reference
            self.utility_functions = {
                # Basic utilities
                'select_all_nodes': select_all_nodes,
                'deselect_all_nodes': deselect_all_nodes,
                'frame_selected': frame_selected,
                'frame_all': frame_all,
                'duplicate_selected': duplicate_selected,
                'list_available_nodes': list_available_nodes,
                'PasteFromClipboard2' : PasteFromClipboard2,
                
                # Node creation
                'create_custom_grade_setup': create_custom_grade_setup,
                'create_read_write_setup': create_read_write_setup,
                'create_keying_setup': create_keying_setup,
                'create_comp_setup': create_comp_setup,
                
                # Workflow setups
                'create_gizmo_with_backdrop': create_gizmo_with_backdrop,
                'load_custom_gizmo_from_path': load_custom_gizmo_from_path,
                'create_render_setup': create_render_setup,
                'create_dailies_setup': create_dailies_setup,
                
                # Viewer utilities
                'toggle_overlay': toggle_overlay,
                'reset_viewer': reset_viewer,
                'fit_viewer': fit_viewer,
                'toggle_viewer_channels': toggle_viewer_channels,
                'toggle_viewer_gain': toggle_viewer_gain,
                'center_viewer': center_viewer
            }
            
            if self.debug_mode:
                self.logger.info(f"Loaded {len(self.utility_functions)} utility functions from shortcuts modules")
            
        except Exception as e:
            self.logger.error(f"Failed to load utility functions from shortcuts modules: {e}")
            if self.debug_mode:
                self.logger.info("ShortcutManager will continue with empty utility functions dictionary")
            self.utility_functions = {}

    def load_config(self) -> bool:
        """
        Load shortcuts configuration from JSON file.
        
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            with open(self.config_file, 'r') as f:
                self.config = json.load(f)
            
            if self.debug_mode:
                self.logger.info(f"Loaded shortcuts config from: {self.config_file}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to load shortcuts config: {e}")
            return False
    
    def register_shortcuts_from_config(self) -> Dict[str, int]:
        """
        Register all shortcuts defined in the configuration file.
        
        Returns:
            Dict[str, int]: Statistics of registration results
        """
        if not self.config:
            self.logger.warning("No configuration loaded")
            return {'total': 0, 'successful': 0, 'failed': 0}
        
        stats = {'total': 0, 'successful': 0, 'failed': 0}
        
        # Check if shortcuts are enabled in main config.json
        if not self._are_shortcuts_enabled():
            self.logger.info("Shortcuts globally disabled in main configuration")
            return stats
        
        # Check if shortcuts are enabled in shortcuts.json settings 
        settings = self.config.get('settings', {})
        if not settings.get('enabled', True):
            self.logger.info("Shortcuts disabled in shortcuts.json settings")
            return stats
        
        shortcuts = self.config.get('shortcuts', {})
        overwrite = settings.get('overwrite_existing', False)
        
        # Filter out comment entries for counting
        actual_shortcuts = {k: v for k, v in shortcuts.items() if not k.startswith('_comment')}
        
        # Collect successful registrations for summary
        successful_shortcuts = []
        failed_shortcuts = []
        
        # Process each shortcut
        for shortcut_key, config in shortcuts.items():
            if shortcut_key.startswith('_comment'):
                continue  # Skip comment entries entirely
                
            stats['total'] += 1
            
            if self._register_shortcut_from_config(shortcut_key, config, overwrite):
                stats['successful'] += 1
                if not self.debug_mode:
                    successful_shortcuts.append(shortcut_key)
            else:
                stats['failed'] += 1
                if not self.debug_mode:
                    failed_shortcuts.append(shortcut_key)
        
        # Log summary based on debug mode
        if self.debug_mode:
            self.logger.info(f"Shortcut registration complete: {stats['successful']}/{stats['total']} successful")
        else:
            # Create a nice table for non-debug mode
            if successful_shortcuts:
                self._log_shortcuts_table(shortcuts, successful_shortcuts)
            
            if failed_shortcuts:
                self.logger.warning(f"Failed to register {len(failed_shortcuts)} shortcuts: {', '.join(failed_shortcuts)}")
        
        return stats
    
    def _register_shortcut_from_config(self, shortcut_key: str, config: Dict, overwrite: bool) -> bool:
        """Register a single shortcut from configuration."""
        try:
            # Skip comment entries - they're just for organization in JSON
            if shortcut_key.startswith('_comment'):
                return True  # Return True to not count as failed
            
            action = config.get('action')
            description = config.get('description', '')
            
            # Determine the function to bind based on action type
            function = None
            
            if action == 'create_node':
                # Node creation shortcut
                node_type = config.get('node_type')
                if node_type:
                    function = self._create_node_function(node_type)
                else:
                    self.logger.warning(f"No node_type specified for shortcut: {shortcut_key}")
                    return False
            
            elif action == 'utility':
                # Utility function shortcut
                function_name = config.get('function')
                if function_name in self.utility_functions:
                    function = self.utility_functions[function_name]
                else:
                    self.logger.warning(f"Unknown utility function: {function_name}")
                    return False
            
            elif action == 'script':
                # Script execution shortcut
                script_path = config.get('script_path')
                if script_path:
                    function = self._create_script_function(script_path)
                else:
                    self.logger.warning(f"No script_path specified for shortcut: {shortcut_key}")
                    return False
            
            else:
                self.logger.warning(f"Unknown action type: {action}")
                return False
            
            if function:
                return self.register_shortcut(
                    shortcut=shortcut_key,
                    function=function,
                    description=description,
                    context="DAG",  # Default to DAG context for simplicity
                    overwrite=overwrite
                )
            
            return False
            
        except Exception as e:
            self.logger.error(f"Error registering shortcut {shortcut_key}: {e}")
            return False
    
    def _create_node_function(self, node_class: str) -> Callable:
        """Create a function for node creation with proper naming and error handling."""
        def create_specific_node():
            try:
                # Try to create the node
                node = nuke.createNode(node_class)
                if self.debug_mode:
                    self.logger.info(f"Created {node_class} node: {node.name()}")
                return node
                
            except Exception as e:
                error_str = str(e)
                
                # Provide helpful error messages based on the type of error
                if "Unknown command" in error_str:
                    error_msg = f"Node type '{node_class}' not found. This could mean:\n"
                    error_msg += f"• The gizmo/plugin is not installed\n"
                    error_msg += f"• The gizmo name is misspelled\n"
                    error_msg += f"• The gizmo is not in Nuke's plugin path\n"
                    error_msg += f"• The gizmo file failed to load\n\n"
                    error_msg += f"Available alternatives: Grade, ColorCorrect, Blur, Defocus"
                    
                    self.logger.error(f"Node type '{node_class}' not available: {error_str}")
                    
                    # Suggest alternatives for common gizmos
                    alternatives = self._suggest_node_alternatives(node_class)
                    if alternatives:
                        error_msg += f"\n\nSuggested alternatives: {', '.join(alternatives)}"
                        
                else:
                    error_msg = f"Failed to create {node_class} node: {error_str}"
                    self.logger.error(error_msg)
                
                nuke.message(error_msg)
                return None
        
        # Give the function a descriptive name based on the node type
        function_name = f"create_{node_class.lower()}_node"
        create_specific_node.__name__ = function_name
        create_specific_node.__doc__ = f"Create a {node_class} node"
        
        return create_specific_node
    
    def _suggest_node_alternatives(self, node_class: str) -> list:
        """Suggest alternative node types for common gizmos."""
        suggestions = {
            'mycustomgizmo': ['Grade', 'ColorCorrect'],
            'magicdefocus': ['Defocus', 'Blur'],
            'customgrade': ['Grade', 'ColorCorrect', 'Saturation'],
            'customblur': ['Blur', 'Defocus'],
            'custommatte': ['Keyer', 'Primatte'],
            'customkeyer': ['Keyer', 'IBKColour', 'IBKGizmo'],
            'customtracker': ['Tracker4', 'CornerPin2D'],
            'customroto': ['Roto', 'RotoPaint'],
        }
        
        node_lower = node_class.lower()
        return suggestions.get(node_lower, [])
    
    def _create_script_function(self, script_path: str) -> Callable:
        """Create a function for script execution with proper naming."""
        def execute_specific_script():
            try:
                # Convert relative path to absolute if needed
                if not Path(script_path).is_absolute():
                    base_dir = Path(self.config_file).parent if self.config_file else Path.cwd()
                    full_path = base_dir / script_path
                else:
                    full_path = Path(script_path)
                
                if full_path.exists():
                    if self.debug_mode:
                        self.logger.debug(f"Executing script: {full_path}")
                    exec(open(str(full_path)).read())
                else:
                    error_msg = f"Script not found: {full_path}"
                    self.logger.error(error_msg)
                    nuke.message(error_msg)
            except Exception as e:
                error_msg = f"Failed to execute script: {str(e)}"
                self.logger.error(error_msg)
                nuke.message(error_msg)
        
        # Give the function a descriptive name based on the script
        script_name = Path(script_path).stem
        function_name = f"execute_{script_name}_script"
        execute_specific_script.__name__ = function_name
        execute_specific_script.__doc__ = f"Execute script: {script_path}"
        
        return execute_specific_script
    
    def register_shortcut(
        self, 
        shortcut: str, 
        function: Callable, 
        description: str = "",
        context: str = "DAG",
        overwrite: bool = False
    ) -> bool:
        """
        Register a custom keyboard shortcut without creating visible menu items.
        
        Uses the @ prefix method in existing menus (as recommended by Foundry community)
        to create truly hidden shortcuts that don't create new visible menu entries.
        
        Args:
            shortcut (str): The keyboard shortcut (e.g., "Ctrl+Shift+X", "F5", "Alt+D")
            function (Callable): The function to execute when shortcut is pressed
            description (str): Description of what the shortcut does
            context (str): The context where shortcut is active ("DAG", "Viewer", "Properties", etc.)
            overwrite (bool): Whether to overwrite existing shortcuts
            
        Returns:
            bool: True if registration successful, False otherwise
        """
        try:
            # Validate inputs
            if not self._validate_shortcut(shortcut):
                self.logger.error(f"Invalid shortcut format: {shortcut}")
                return False
            
            if not callable(function):
                self.logger.error(f"Function must be callable: {function}")
                return False
            
            # Check if shortcut already exists
            if shortcut in self.registered_shortcuts and not overwrite:
                self.logger.warning(f"Shortcut '{shortcut}' already exists. Use overwrite=True to replace.")
                return False
            
            # Register the shortcut with Nuke using existing menu to avoid creating visible menus
            # Add to existing menus with @ prefix to truly hide shortcuts
            if context.upper() == "DAG":
                # Add to existing Edit menu with hidden command
                nuke.menu('Nuke').menu("Edit").addCommand(
                    f"@{description or function.__name__}",  # Hidden command in existing menu
                    function,
                    shortcut
                )
            elif context.upper() == "VIEWER":
                # Add to existing Viewer menu with hidden command  
                nuke.menu('Viewer').menu("Viewer").addCommand(
                    f"@{description or function.__name__}",  # Hidden command in existing menu
                    function,
                    shortcut
                )
            else:
                # Default to DAG context - add to Edit menu
                nuke.menu('Nuke').menu("Edit").addCommand(
                    f"@{description or function.__name__}",  # Hidden command in existing menu
                    function,
                    shortcut
                )
            
            # Store registration info
            self.registered_shortcuts[shortcut] = {
                'function': function,
                'description': description,
                'context': context,
                'function_name': function.__name__
            }
            
            if self.debug_mode:
                self.logger.info(f"Successfully registered shortcut '{shortcut}' for {function.__name__}")
            
            return True
            
        except Exception as e:
            error_details = f"Failed to register shortcut '{shortcut}': {str(e)}"
            if "already assigned" in str(e).lower() or "already exists" in str(e).lower():
                error_details += f" (Key conflict - consider using overwrite_existing=True)"
            self.logger.error(error_details)
            return False
    
    def register_multiple_shortcuts(self, shortcuts_dict: Dict[str, Dict]) -> List[str]:
        """
        Register multiple shortcuts at once.
        
        Args:
            shortcuts_dict (Dict): Dictionary where keys are shortcuts and values contain
                                 'function', 'description', 'context', 'overwrite'
        
        Returns:
            List[str]: List of successfully registered shortcuts
        """
        successful = []
        
        for shortcut, config in shortcuts_dict.items():
            if self.register_shortcut(
                shortcut=shortcut,
                function=config.get('function'),
                description=config.get('description', ''),
                context=config.get('context', 'DAG'),
                overwrite=config.get('overwrite', False)
            ):
                successful.append(shortcut)
        
        self.logger.info(f"Registered {len(successful)}/{len(shortcuts_dict)} shortcuts successfully")
        return successful
    
    def unregister_shortcut(self, shortcut: str) -> bool:
        """
        Unregister a previously registered shortcut.
        
        Args:
            shortcut (str): The shortcut to unregister
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            if shortcut not in self.registered_shortcuts:
                self.logger.warning(f"Shortcut '{shortcut}' not found in registered shortcuts")
                return False
            
            # Note: Nuke doesn't provide a direct way to remove shortcuts
            # This removes it from our tracking
            del self.registered_shortcuts[shortcut]
            self.logger.info(f"Unregistered shortcut '{shortcut}'")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to unregister shortcut '{shortcut}': {str(e)}")
            return False
    
    def list_shortcuts(self) -> Dict[str, Dict]:
        """
        Get a list of all registered shortcuts.
        
        Returns:
            Dict: Dictionary of registered shortcuts and their details
        """
        return self.registered_shortcuts.copy()
    
    def print_shortcuts(self) -> None:
        """Print all registered shortcuts in a formatted way."""
        if not self.registered_shortcuts:
            self.logger.info("No custom shortcuts registered.")
            return
        
        self.logger.info("=== Registered Custom Shortcuts ===")
        for shortcut, details in self.registered_shortcuts.items():
            self.logger.info(f"  {shortcut:<20} -> {details['function_name']}")
            if details['description']:
                self.logger.info(f"  {'':<20}    {details['description']}")
            self.logger.info(f"  {'':<20}    Context: {details['context']}")
        self.logger.info("")
    
    def _validate_shortcut(self, shortcut: str) -> bool:
        """
        Validate shortcut format.
        
        Args:
            shortcut (str): The shortcut string to validate
            
        Returns:
            bool: True if valid, False otherwise
        """
        if not isinstance(shortcut, str) or not shortcut.strip():
            return False
        
        # Basic validation - could be expanded
        valid_modifiers = ['Ctrl', 'Alt', 'Shift', 'Meta', 'Cmd']
        valid_keys = [
            # Function keys
            'F1', 'F2', 'F3', 'F4', 'F5', 'F6', 'F7', 'F8', 'F9', 'F10', 'F11', 'F12',
            # Special keys
            'Tab', 'Space', 'Return', 'Enter', 'Backspace', 'Delete', 'Insert',
            'Home', 'End', 'PageUp', 'PageDown', 'Up', 'Down', 'Left', 'Right',
            'Escape', 'Plus', 'Minus', 'Equal'
        ]
        
        # Add alphabet and numbers
        valid_keys.extend([chr(i) for i in range(ord('A'), ord('Z') + 1)])
        valid_keys.extend([str(i) for i in range(10)])
        
        # Simple validation - check if it contains valid components
        parts = shortcut.split('+')
        if len(parts) == 0:
            return False
        
        # Last part should be the key
        key = parts[-1]
        if key not in valid_keys:
            return False
        
        # Other parts should be modifiers
        for modifier in parts[:-1]:
            if modifier not in valid_modifiers:
                return False
        
        return True
    
    def create_node_shortcut(self, node_class: str, shortcut: str, description: str = "") -> bool:
        """
        Create a shortcut for creating a specific node type.
        
        Args:
            node_class (str): The Nuke node class name (e.g., "Blur", "Grade", "Merge2")
            shortcut (str): The keyboard shortcut
            description (str): Optional description
            
        Returns:
            bool: True if successful, False otherwise
        """
        def create_node():
            try:
                node = nuke.createNode(node_class)
                return node
            except Exception as e:
                nuke.message(f"Failed to create {node_class} node: {str(e)}")
                return None
        
        desc = description or f"Create {node_class} node"
        return self.register_shortcut(shortcut, create_node, desc)
    
    def create_script_shortcut(self, script_path: str, shortcut: str, description: str = "") -> bool:
        """
        Create a shortcut for executing a Python script.
        
        Args:
            script_path (str): Path to the Python script
            shortcut (str): The keyboard shortcut
            description (str): Optional description
            
        Returns:
            bool: True if successful, False otherwise
        """
        def execute_script():
            try:
                exec(open(script_path).read())
            except Exception as e:
                nuke.message(f"Failed to execute script: {str(e)}")
        
        desc = description or f"Execute {script_path}"
        return self.register_shortcut(shortcut, execute_script, desc)
    
    def _get_debug_mode(self) -> bool:
        """Get debug mode setting from main config."""
        try:
            config_path = Path(__file__).parent.parent / "config.json"
            if config_path.exists():
                with open(config_path, 'r') as f:
                    main_config = json.load(f)
                return main_config.get('development', {}).get('debug_mode', False)
        except Exception:
            pass
        return False
    
    def _log_shortcuts_table(self, shortcuts_config: Dict, successful_shortcuts: List[str]) -> None:
        """Log shortcuts in a clean table format for non-debug mode."""
        # Group shortcuts by category based on comments
        categories = {}
        current_category = "General"
        
        for key, config in shortcuts_config.items():
            if key.startswith('_comment_'):
                # Extract category name from comment
                category_name = key.replace('_comment_', '').replace('_', ' ').title()
                current_category = category_name
                categories[current_category] = []
            elif key in successful_shortcuts and isinstance(config, dict):
                description = config.get('description', key)
                categories.setdefault(current_category, []).append((key, description))
        
        # Build the entire table as a single string
        table_lines = []
        table_lines.append("Registered Keyboard Shortcuts:")
        table_lines.append("=" * 65)
        
        for category, shortcuts_list in categories.items():
            if shortcuts_list:  # Only show categories with shortcuts
                table_lines.append(f"\n{category}:")
                table_lines.append("-" * len(category))
                
                for shortcut, description in shortcuts_list:
                    # Format shortcut key and description in columns (increased spacing for longer shortcuts)
                    shortcut_col = f"{shortcut:<20}"
                    desc_col = description[:40] + "..." if len(description) > 40 else description
                    table_lines.append(f"  {shortcut_col} {desc_col}")
        
        table_lines.append("\n" + "=" * 65)
        table_lines.append(f"Total: {len(successful_shortcuts)} shortcuts registered")
        
        # Log the entire table as a single message
        full_table = "\n".join(table_lines)
        self.logger.info(full_table)


# Global instance for easy access
shortcut_manager = ShortcutManager()


# Convenience functions for quick access
def register_shortcut(shortcut: str, function: Callable, description: str = "", context: str = "DAG") -> bool:
    """Quick function to register a shortcut using the global manager."""
    return shortcut_manager.register_shortcut(shortcut, function, description, context)


def load_shortcuts_from_config() -> Dict[str, int]:
    """Load and register all shortcuts from the configuration file."""
    return shortcut_manager.register_shortcuts_from_config()


def reload_shortcuts_config() -> bool:
    """Reload the shortcuts configuration file."""
    return shortcut_manager.load_config()


def list_shortcuts() -> None:
    """Quick function to print all registered shortcuts."""
    shortcut_manager.print_shortcuts()


def get_shortcuts_config() -> Dict:
    """Get the current shortcuts configuration."""
    return shortcut_manager.config


def get_shortcuts_stats() -> Dict[str, int]:
    """Get statistics about registered shortcuts."""
    total = len(shortcut_manager.registered_shortcuts)
    by_context = {}
    
    for details in shortcut_manager.registered_shortcuts.values():
        context = details.get('context', 'Unknown')
        by_context[context] = by_context.get(context, 0) + 1
    
    return {
        'total_registered': total,
        'by_context': by_context,
        'config_file': shortcut_manager.config_file
    }


# Shortcuts will be loaded manually from menu.py when UI is ready


if __name__ == "__main__":
    # Example usage - load shortcuts from config
    logger = get_logger("ShortcutManager.main")
    logger.info("Loading shortcuts from configuration...")
    stats = load_shortcuts_from_config()
    logger.info(f"Registration stats: {stats}")
    logger.info("Registered shortcuts:")
    list_shortcuts()
    logger.info(f"Shortcuts stats: {get_shortcuts_stats()}")
