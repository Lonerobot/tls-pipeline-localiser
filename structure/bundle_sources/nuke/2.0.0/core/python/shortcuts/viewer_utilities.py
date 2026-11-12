"""
Viewer utility functions for Nuke shortcuts.

Contains functions for viewer-specific operations and manipulations.

Author: Pipeline Team
Date: July 2025
"""

import nuke
import nukescripts
from utils.PipelineLogger import get_logger

logger = get_logger("ViewerUtilities")


def toggle_overlay():
    """Toggle viewer overlay (context: Viewer)"""
    try:
        # Use nukescripts for reliable viewer operations
        nukescripts.toggle_viewer_matte_overlay()
        logger.debug("Toggled viewer overlay")
    except Exception as e:
        logger.warning(f"Failed to toggle overlay: {e}")


def reset_viewer():
    """Reset viewer zoom and pan (context: Viewer)"""
    try:
        # Use nukescripts for reliable viewer reset
        nukescripts.reset_zoom()
        logger.debug("Reset viewer zoom and pan")
    except Exception as e:
        logger.warning(f"Failed to reset viewer: {e}")


def fit_viewer():
    """Fit image to viewer window"""
    try:
        # Use nukescripts to fit image
        nukescripts.zoom_to_fit()
        logger.debug("Fit image to viewer")
    except Exception as e:
        logger.warning(f"Failed to fit viewer: {e}")


def toggle_viewer_channels():
    """Cycle through common viewer channels (RGB, Alpha, etc.)"""
    try:
        viewer = nuke.activeViewer()
        if viewer:
            # Use nukescripts for channel switching if available
            nukescripts.toggle_viewer_channels()
            logger.debug("Toggled viewer channels")
        else:
            logger.warning("No active viewer found")
    except Exception as e:
        logger.warning(f"Failed to toggle viewer channels: {e}")


def toggle_viewer_gain():
    """Toggle between common viewer gain values"""
    try:
        viewer = nuke.activeViewer()
        if viewer:
            # Simple gain toggle between 1.0 and 2.0
            try:
                current_gain = viewer.node()['gain'].value() if viewer.node().knob('gain') else 1.0
                new_gain = 2.0 if current_gain == 1.0 else 1.0
                if viewer.node().knob('gain'):
                    viewer.node()['gain'].setValue(new_gain)
                    logger.info(f"Set viewer gain to {new_gain}")
                else:
                    logger.warning("Viewer gain control not available")
            except:
                logger.warning("Could not access viewer gain control")
        else:
            logger.warning("No active viewer found")
    except Exception as e:
        logger.warning(f"Failed to toggle viewer gain: {e}")


def center_viewer():
    """Center the viewer on the current image"""
    try:
        # Use nukescripts to center viewer
        nukescripts.reset_zoom()  # This centers and fits the image
        logger.debug("Centered viewer")
    except Exception as e:
        logger.warning(f"Failed to center viewer: {e}")
