"""
Pipeline Configuration Manager

A comprehensive configuration system that combines JSON-based settings with Python
dynamic configuration capabilities. Provides environment variable expansion,
validation, and easy access to configuration values.

Author: Pipeline Team
Date: July 2025
"""

import json
import os
import sys
from pathlib import Path
from typing import Dict, Any, List, Optional, Union
from utils.PipelineLogger import get_logger


class ConfigManager:
    """
    Manages pipeline configuration with JSON files and Python overrides.
    
    Provides a flexible configuration system that supports:
    - JSON-based configuration files
    - Environment variable expansion
    - Python-based overrides and dynamic values
    - Configuration validation
    - Default value handling
    """
    
    def __init__(self, config_file: str = "config.json"):
        """
        Initialize the configuration manager.
        
        Args:
            config_file (str): Path to the JSON configuration file
        """
        self.logger = get_logger("Config")
        self.config_file = Path(__file__).parent / config_file
        self.config_data = {}
        self.user_overrides = {}
        self._load_configuration()
    
    def _load_configuration(self) -> None:
        """Load configuration from JSON file with error handling."""
        try:
            if self.config_file.exists():
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    self.config_data = json.load(f)
                self.logger.info(f"Configuration loaded from {self.config_file}")
            else:
                self.logger.warning(f"Configuration file not found: {self.config_file}")
                self.config_data = self._get_default_config()
                
            # Expand environment variables
            self._expand_environment_variables()
            
        except json.JSONDecodeError as e:
            self.logger.error(f"Invalid JSON in config file: {e}")
            self.config_data = self._get_default_config()
        except Exception as e:
            self.logger.error(f"Failed to load configuration: {e}")
            self.config_data = self._get_default_config()
    
    def _get_default_config(self) -> Dict[str, Any]:
        """Get default configuration if file is missing or invalid."""
        return {
            "grid_settings": {
                "enabled": True,
                "width": 110,
                "height": 24,
                "snap_threshold": 90,
                "overlay_color": 1145324799
            },
            "plugin_paths": {
                "enabled": True,
                "paths": ["./gizmos", "./plugins"]
            },
            "logging": {
                "console_level": "INFO",
                "file_level": "DEBUG"
            }
        }
    
    def _expand_environment_variables(self) -> None:
        """Recursively expand environment variables in configuration values."""
        def expand_value(value):
            if isinstance(value, str):
                # Handle ${VAR} and $VAR syntax
                import re
                pattern = r'\$\{([^}]+)\}|\$([A-Za-z_][A-Za-z0-9_]*)'
                
                def replace_env(match):
                    var_name = match.group(1) or match.group(2)
                    return os.environ.get(var_name, match.group(0))
                
                return re.sub(pattern, replace_env, value)
            elif isinstance(value, dict):
                return {k: expand_value(v) for k, v in value.items()}
            elif isinstance(value, list):
                return [expand_value(item) for item in value]
            else:
                return value
        
        self.config_data = expand_value(self.config_data)
    
    def get(self, key_path: str, default: Any = None) -> Any:
        """
        Get a configuration value using dot notation.
        
        Args:
            key_path (str): Dot-separated path to the config value (e.g., 'grid_settings.width')
            default (Any): Default value if key is not found
            
        Returns:
            Any: Configuration value or default
        """
        # Check user overrides first
        if key_path in self.user_overrides:
            return self.user_overrides[key_path]
        
        # Navigate through the config data
        keys = key_path.split('.')
        value = self.config_data
        
        try:
            for key in keys:
                value = value[key]
            return value
        except (KeyError, TypeError):
            self.logger.debug(f"Configuration key '{key_path}' not found, using default: {default}")
            return default
    
    def set_override(self, key_path: str, value: Any) -> None:
        """
        Set a runtime override for a configuration value.
        
        Args:
            key_path (str): Dot-separated path to the config value
            value (Any): Value to override with
        """
        self.user_overrides[key_path] = value
        self.logger.debug(f"Set override: {key_path} = {value}")
    
    def get_grid_settings(self) -> Dict[str, Any]:
        """Get grid settings with Python-based dynamic defaults."""
        base_settings = self.get('grid_settings', {})
        
        # Allow Python-based dynamic overrides
        if hasattr(self, '_grid_overrides'):
            base_settings.update(self._grid_overrides())
        
        return base_settings
    
    def get_plugin_paths(self) -> List[str]:
        """Get plugin paths with validation and expansion."""
        if not self.get('plugin_paths.enabled', True):
            return []
        
        paths = self.get('plugin_paths.paths', [])
        validated_paths = []
        
        for path in paths:
            expanded_path = Path(path).expanduser()
            if expanded_path.exists():
                validated_paths.append(str(expanded_path))
                self.logger.debug(f"Added plugin path: {expanded_path}")
            else:
                self.logger.warning(f"Plugin path does not exist: {expanded_path}")
        
        return validated_paths
    
    def get_gizmo_paths(self) -> List[str]:
        """Get gizmo paths with validation."""
        if not self.get('gizmo_paths.enabled', True):
            return []
        
        paths = self.get('gizmo_paths.paths', [])
        validated_paths = []
        
        for path in paths:
            expanded_path = Path(path).expanduser()
            if expanded_path.exists():
                validated_paths.append(str(expanded_path))
                self.logger.debug(f"Added gizmo path: {expanded_path}")
            else:
                self.logger.warning(f"Gizmo path does not exist: {expanded_path}")
        
        return validated_paths
    
    def get_logging_config(self) -> Dict[str, Any]:
        """Get logging configuration."""
        return self.get('logging', {})
    
    def validate_configuration(self) -> bool:
        """
        Validate the configuration for common issues.
        
        Returns:
            bool: True if configuration is valid
        """
        issues = []
        
        # Check required sections
        required_sections = ['grid_settings', 'plugin_paths', 'logging']
        for section in required_sections:
            if not self.get(section):
                issues.append(f"Missing required section: {section}")
        
        # Validate grid settings
        grid = self.get('grid_settings', {})
        if grid.get('width', 0) <= 0:
            issues.append("Grid width must be positive")
        if grid.get('height', 0) <= 0:
            issues.append("Grid height must be positive")
        
        # Log issues
        for issue in issues:
            self.logger.error(f"Configuration validation error: {issue}")
        
        return len(issues) == 0
    
    def reload(self) -> None:
        """Reload configuration from file."""
        self.logger.info("Reloading configuration")
        self.user_overrides.clear()
        self._load_configuration()
    
    def get_config_summary(self) -> str:
        """Get a formatted summary of the current configuration."""
        summary = []
        summary.append("=== Pipeline Configuration Summary ===")
        summary.append(f"Config File: {self.config_file}")
        summary.append(f"Grid Settings: {self.get('grid_settings.enabled', False)}")
        summary.append(f"Plugin Paths: {len(self.get_plugin_paths())} paths")
        summary.append(f"Gizmo Paths: {len(self.get_gizmo_paths())} paths")
        summary.append(f"Extra Env Vars: {len(self.get_extra_env_vars())} variables")
        summary.append(f"Logging Level: {self.get('logging.console_level', 'INFO')}")
        summary.append(f"User Overrides: {len(self.user_overrides)}")
        
        return "\n".join(summary)
    
    def get_extra_env_vars(self) -> Dict[str, str]:
        """Get extra environment variables from configuration."""
        return self.get('environment.extra_env_vars', {})
    
    def apply_extra_env_vars(self) -> None:
        """Apply extra environment variables to the current environment."""
        extra_vars = self.get_extra_env_vars()
        
        for var_name, var_value in extra_vars.items():
            # Expand any environment variables in the value
            expanded_value = self._expand_single_env_var(var_value)
            
            # Set the environment variable
            os.environ[var_name] = expanded_value
            self.logger.debug(f"Set environment variable: {var_name} = {expanded_value}")
    
    def _expand_single_env_var(self, value: str) -> str:
        """Expand environment variables in a single string value."""
        if not isinstance(value, str):
            return str(value)
        
        import re
        pattern = r'\$\{([^}]+)\}|\$([A-Za-z_][A-Za-z0-9_]*)'
        
        def replace_env(match):
            var_name = match.group(1) or match.group(2)
            return os.environ.get(var_name, match.group(0))
        
        return re.sub(pattern, replace_env, value)
    
    # Python-based dynamic configuration methods
    def _grid_overrides(self) -> Dict[str, Any]:
        """Example of Python-based dynamic grid settings."""
        overrides = {}
        
        # Dynamic grid size based on screen resolution (example)
        try:
            import nuke
            # This could be expanded to detect screen size and adjust grid accordingly
            if hasattr(nuke, 'screenWidth') and nuke.screenWidth() > 2560:
                overrides['width'] = 150  # Larger grid for high-res displays
        except:
            pass
        
        return overrides
    
    def get_toolchains_config(self) -> Dict[str, Any]:
        """Get toolchains configuration."""
        return self.get('toolchains', {})
    
    def is_toolchain_enabled(self, toolchain_name: str) -> bool:
        """Check if a specific toolchain is enabled."""
        return self.get(f'toolchains.{toolchain_name}.enabled', False)
    
    def get_toolchain_status(self, toolchain_name: str) -> Dict[str, Any]:
        """
        Get detailed status information for a toolchain.
        
        Args:
            toolchain_name (str): Name of the toolchain to check
            
        Returns:
            Dict containing status information with keys:
            - exists: bool - Whether the toolchain configuration exists
            - enabled: bool - Whether the toolchain is enabled
            - config: dict - The toolchain configuration (if exists)
            - status: str - Human readable status description
        """
        toolchains = self.get_toolchains_config()
        
        if toolchain_name not in toolchains:
            return {
                'exists': False,
                'enabled': False,
                'config': {},
                'status': f"Toolchain '{toolchain_name}' not found in configuration"
            }
        
        toolchain_config = toolchains[toolchain_name]
        is_enabled = toolchain_config.get('enabled', False)
        
        status_msg = f"Toolchain '{toolchain_name}' found"
        if is_enabled:
            status_msg += " and is ENABLED"
        else:
            status_msg += " but is DISABLED"
            
        return {
            'exists': True,
            'enabled': is_enabled,
            'config': toolchain_config,
            'status': status_msg
        }
    
    def get_all_toolchains_status(self) -> Dict[str, Dict[str, Any]]:
        """
        Get status for all configured toolchains.
        
        Returns:
            Dict mapping toolchain names to their status information
        """
        toolchains = self.get_toolchains_config()
        status_report = {}
        
        for name, config in toolchains.items():
            status_report[name] = self.get_toolchain_status(name)
            
        return status_report
    
    def get_toolchains_summary(self) -> str:
        """
        Get a formatted summary of all toolchains and their status.
        
        Returns:
            Formatted string with toolchain status information
        """
        all_status = self.get_all_toolchains_status()
        
        if not all_status:
            return "No toolchains configured"
        
        summary = ["=== Toolchains Status Summary ==="]
        
        # Group by status
        enabled_count = 0
        disabled_count = 0
        
        for name, status in all_status.items():
            config = status['config']
            display_name = config.get('display_name', name)
            version = config.get('version', 'unknown')
            enabled_icon = "✅" if status['enabled'] else "❌"
            
            summary.append(f"{enabled_icon} {display_name} (v{version}) - {name}")
            
            if status['enabled']:
                enabled_count += 1
                # Show menu/toolbar info for enabled toolchains
                build_menu = config.get('build_menu', False)
                build_toolbar = config.get('build_toolbar', False)
                menu_info = []
                if build_menu:
                    menu_info.append("Menu")
                if build_toolbar:
                    menu_info.append("Toolbar")
                if menu_info:
                    summary.append(f"    └─ Builds: {', '.join(menu_info)}")
            else:
                disabled_count += 1
                summary.append(f"    └─ Status: DISABLED")
        
        summary.append("")
        summary.append(f"Total: {len(all_status)} toolchains ({enabled_count} enabled, {disabled_count} disabled)")
        
        return "\n".join(summary)
    
    def validate_toolchains(self) -> Dict[str, List[str]]:
        """
        Validate all toolchains and return issues found.
        
        Returns:
            Dict with 'errors' and 'warnings' lists
        """
        issues = {'errors': [], 'warnings': []}
        toolchains = self.get_toolchains_config()
        
        for name, config in toolchains.items():
            # Check required fields
            required_fields = ['display_name', 'folder_path', 'enabled']
            for field in required_fields:
                if field not in config:
                    issues['errors'].append(f"Toolchain '{name}' missing required field: {field}")
            
            # Check folder path exists if enabled
            if config.get('enabled', False):
                folder_path = config.get('folder_path', '')
                if folder_path:
                    # Convert relative path to absolute
                    abs_path = Path(self.config_file.parent / folder_path)
                    if not abs_path.exists():
                        issues['warnings'].append(f"Toolchain '{name}' folder path does not exist: {abs_path}")
                else:
                    issues['errors'].append(f"Enabled toolchain '{name}' has no folder_path specified")
            
            # Check menu structure if present
            menu_structure = config.get('menu_structure', {})
            for struct_name, struct_config in menu_structure.items():
                if not isinstance(struct_config, dict):
                    issues['errors'].append(f"Toolchain '{name}' has invalid menu_structure for {struct_name}")
                    continue
                    
                if struct_config.get('enabled', False):
                    path = struct_config.get('path', '')
                    if not path:
                        issues['warnings'].append(f"Toolchain '{name}' menu structure '{struct_name}' is enabled but has no path")
        
        return issues


# Global configuration manager instance
config_manager = ConfigManager()


# Convenience functions for easy access
def get_config(key_path: str, default: Any = None) -> Any:
    """Get configuration value using dot notation."""
    return config_manager.get(key_path, default)


def set_config_override(key_path: str, value: Any) -> None:
    """Set a runtime configuration override."""
    config_manager.set_override(key_path, value)


def get_grid_settings() -> Dict[str, Any]:
    """Get grid settings."""
    return config_manager.get_grid_settings()


def get_plugin_paths() -> List[str]:
    """Get validated plugin paths."""
    return config_manager.get_plugin_paths()


def get_gizmo_paths() -> List[str]:
    """Get validated gizmo paths."""
    return config_manager.get_gizmo_paths()


def get_extra_env_vars() -> Dict[str, str]:
    """Get extra environment variables from configuration."""
    return config_manager.get_extra_env_vars()


def apply_extra_env_vars() -> None:
    """Apply extra environment variables to the current environment."""
    config_manager.apply_extra_env_vars()


def validate_config() -> bool:
    """Validate current configuration."""
    return config_manager.validate_configuration()


def reload_config() -> None:
    """Reload configuration from file."""
    config_manager.reload()


def get_toolchains_config() -> Dict[str, Any]:
    """Get toolchains configuration."""
    return config_manager.get_toolchains_config()


def is_toolchain_enabled(toolchain_name: str) -> bool:
    """Check if a specific toolchain is enabled."""
    return config_manager.is_toolchain_enabled(toolchain_name)


def get_toolchain_status(toolchain_name: str) -> Dict[str, Any]:
    """Get detailed status information for a toolchain."""
    return config_manager.get_toolchain_status(toolchain_name)


def get_all_toolchains_status() -> Dict[str, Dict[str, Any]]:
    """Get status for all configured toolchains."""
    return config_manager.get_all_toolchains_status()


def get_toolchains_summary() -> str:
    """Get a formatted summary of all toolchains and their status."""
    return config_manager.get_toolchains_summary()


def validate_toolchains() -> Dict[str, List[str]]:
    """Validate all toolchains and return issues found."""
    return config_manager.validate_toolchains()


if __name__ == "__main__":
    # Example usage and testing
    print(config_manager.get_config_summary())
    print()
    
    # Test configuration access
    grid_width = get_config('grid_settings.width', 100)
    print(f"Grid width: {grid_width}")
    
    # Test override
    set_config_override('grid_settings.width', 200)
    print(f"Grid width after override: {get_config('grid_settings.width')}")
    print()
    
    # Test toolchain status reporting
    print(get_toolchains_summary())
    print()
    
    # Test individual toolchain status
    example_toolchains = ['TheLine', 'NukeSurvivalToolkit', 'NonExistentToolchain']
    for toolchain in example_toolchains:
        status = get_toolchain_status(toolchain)
        print(f"🔍 {status['status']}")
        if status['exists'] and not status['enabled']:
            config = status['config']
            print(f"   ↳ Display name: {config.get('display_name', 'N/A')}")
            print(f"   ↳ Version: {config.get('version', 'N/A')}")
            print(f"   ↳ Description: {config.get('description', 'N/A')}")
    print()
    
    # Test toolchain validation
    validation_results = validate_toolchains()
    if validation_results['errors']:
        print("❌ Toolchain validation errors:")
        for error in validation_results['errors']:
            print(f"   • {error}")
    if validation_results['warnings']:
        print("⚠️  Toolchain validation warnings:")
        for warning in validation_results['warnings']:
            print(f"   • {warning}")
    if not validation_results['errors'] and not validation_results['warnings']:
        print("✅ All toolchains passed validation")
    print()
    
    # Test extra environment variables
    print(f"Extra env vars: {get_extra_env_vars()}")
    
    # Validate configuration
    is_valid = validate_config()
    print(f"Configuration valid: {is_valid}")
