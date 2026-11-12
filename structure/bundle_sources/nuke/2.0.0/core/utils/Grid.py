"""
Nuke Grid Preferences Utility

Utility functions for setting up Nuke's grid preferences and display settings.

Author: Pipeline Team
Date: July 2025
"""

import nuke
import sys
from pathlib import Path
from .PipelineLogger import get_logger

# Get logger for this module
logger = get_logger("Grid")

# Add parent directory to path to import config
current_dir = Path(__file__).parent
parent_dir = current_dir.parent
if str(parent_dir) not in sys.path:
    sys.path.insert(0, str(parent_dir))

try:
    from config import get_grid_settings
    # Load grid settings from configuration
    config_settings = get_grid_settings()
    
    # Check if grid settings are enabled
    if not config_settings.get('enabled', False):
        logger.info("Grid settings are disabled in configuration. Skipping grid setup.")
        config_settings = {}  # Empty settings to use fallback defaults without applying them
except ImportError as e:
    logger.warning(f"Could not import config module: {e}. Using fallback defaults.")
    config_settings = {
        'width': 110,
        'height': 24,
        'snap_threshold': 90,
        'overlay_color': 1145324799
    }
except Exception as e:
    logger.error(f"Error loading grid configuration: {e}. Using fallback defaults.")
    config_settings = {
        'width': 110,
        'height': 24,
        'snap_threshold': 90,
        'overlay_color': 1145324799
    }

# Default grid preferences constants (with config overrides)
DEFAULT_GRID_WIDTH = config_settings.get('width', 110)
DEFAULT_GRID_HEIGHT = config_settings.get('height', 24)
DEFAULT_SNAP_THRESHOLD = config_settings.get('snap_threshold', 90)
DEFAULT_OVERLAY_COLOR = config_settings.get('overlay_color', 1145324799)  # Integer representation of overlay color


def setPreferences(width, height, snap, int_overlay):
    """
    Set grid preferences in Nuke.
    
    Args:
        width (int): Grid width
        height (int): Grid height 
        snap (int): Snap threshold
        int_overlay (int): Overlay color as integer
    """
    try:
        logger.info(f"Setting grid preferences: width={width}, height={height}, snap={snap}, overlay={int_overlay}")
        
        pref = nuke.toNode('preferences')
        if not pref:
            logger.error("Could not access Nuke preferences node")
            return False
            
        pref['GridWidth'].setValue(width)
        pref['GridHeight'].setValue(height)
        pref['SnapToGrid'].setValue(True)
        pref['show_grid'].setValue(True)
        pref['dag_snap_threshold'].setValue(snap)
        pref['OverlayColor'].setValue(int_overlay)
        
        logger.info("Grid preferences set successfully")
        return True
        
    except Exception as e:
        logger.error(f"Failed to set grid preferences: {e}")
        return False


def get_grid_preferences():
    """
    Get current grid preferences from Nuke.
    
    Returns:
        dict: Dictionary containing current grid settings
    """
    try:
        pref = nuke.toNode('preferences')
        if not pref:
            logger.error("Could not access Nuke preferences node")
            return None
            
        settings = {
            'width': pref['GridWidth'].getValue(),
            'height': pref['GridHeight'].getValue(),
            'snap_to_grid': pref['SnapToGrid'].getValue(),
            'show_grid': pref['show_grid'].getValue(),
            'snap_threshold': pref['dag_snap_threshold'].getValue(),
            'overlay_color': pref['OverlayColor'].getValue()
        }
        
        logger.debug(f"Retrieved grid preferences: {settings}")
        return settings
        
    except Exception as e:
        logger.error(f"Failed to get grid preferences: {e}")
        return None


def reset_grid_to_defaults():
    """Reset grid preferences to default values."""
    logger.info("Resetting grid preferences to defaults")
    return setPreferences(
        width=DEFAULT_GRID_WIDTH,
        height=DEFAULT_GRID_HEIGHT, 
        snap=DEFAULT_SNAP_THRESHOLD,
        int_overlay=DEFAULT_OVERLAY_COLOR
    )


def is_grid_enabled():
    """
    Check if grid settings are enabled in configuration.
    
    Returns:
        bool: True if grid settings are enabled, False otherwise
    """
    try:
        from config import get_grid_settings
        settings = get_grid_settings()
        return settings.get('enabled', False)
    except Exception as e:
        logger.warning(f"Could not check grid enabled status: {e}")
        return False


def apply_default_grid_settings():
    """
    Apply the default grid settings defined by the constants.
    Only applies if grid settings are enabled in configuration.
    
    Returns:
        bool: True if successful, False otherwise
    """
    if not is_grid_enabled():
        logger.info("Grid settings are disabled in configuration. Skipping grid application.")
        return True  # Return True as this is expected behavior
    
    logger.info("Applying default grid settings")
    return setPreferences(
        width=DEFAULT_GRID_WIDTH,
        height=DEFAULT_GRID_HEIGHT,
        snap=DEFAULT_SNAP_THRESHOLD,
        int_overlay=DEFAULT_OVERLAY_COLOR
    )


def get_default_grid_settings():
    """
    Get the default grid settings as a dictionary.
    
    Returns:
        dict: Dictionary with default grid settings
    """
    return {
        'width': DEFAULT_GRID_WIDTH,
        'height': DEFAULT_GRID_HEIGHT,
        'snap_threshold': DEFAULT_SNAP_THRESHOLD,
        'overlay_color': DEFAULT_OVERLAY_COLOR
    }



