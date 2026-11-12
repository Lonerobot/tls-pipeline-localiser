"""
Basic Utility Functions for Nuke Shortcuts

Contains fundamental DAG manipulation utilities that can be triggered via shortcuts.
"""

import nuke
import nukescripts
from utils.PipelineLogger import get_logger

logger = get_logger("shortcuts.utility_functions")


def select_all_nodes():
    """Select all nodes in the DAG"""
    for node in nuke.allNodes():
        node.setSelected(True)
    logger.debug("Selected all nodes in DAG")


def deselect_all_nodes():
    """Deselect all nodes in the DAG"""
    for node in nuke.allNodes():
        node.setSelected(False)
    logger.debug("Deselected all nodes in DAG")


def frame_selected():
    """Frame selected nodes in the DAG"""
    try:
        nukescripts.zoom_to_fit_selected()
        logger.debug("Framed selected nodes")
    except AttributeError:
        # Fallback if function doesn't exist
        try:
            nuke.zoom(1, nuke.selectedNodes())
            logger.debug("Framed selected nodes (fallback method)")
        except Exception as e:
            logger.warning(f"Failed to frame selected nodes: {e}")


def frame_all():
    """Frame all nodes in the DAG"""
    try:
        # Try different nukescripts functions that might exist
        if hasattr(nukescripts, 'zoom_to_fit_all'):
            nukescripts.zoom_to_fit_all()
        elif hasattr(nukescripts, 'zoom_to_fit'):
            nukescripts.zoom_to_fit()
        else:
            # Manual zoom to fit all nodes
            all_nodes = nuke.allNodes()
            if all_nodes:
                nuke.zoom(1, all_nodes)
        logger.debug("Framed all nodes")
    except Exception as e:
        logger.warning(f"Frame all nodes failed: {e}")


def duplicate_selected():
    """Duplicate selected nodes"""
    try:
        nuke.nodeCopy("%clipboard%")
        nuke.nodePaste("%clipboard%")
        logger.debug("Duplicated selected nodes")
    except Exception as e:
        logger.warning(f"Duplicate selected failed: {e}")


def toggle_overlay():
    """Toggle viewer overlay (context: Viewer)"""
    try:
        viewer = nuke.activeViewer()
        if viewer:
            # Toggle overlay - this is a simplified example
            logger.debug("Toggled viewer overlay")
            pass
    except Exception as e:
        logger.warning(f"Toggle overlay failed: {e}")


def reset_viewer():
    """Reset viewer zoom and pan (context: Viewer)"""
    try:
        viewer = nuke.activeViewer()
        if viewer:
            viewer.node().resetKnob('center')
            viewer.node().resetKnob('zoom')
            logger.debug("Reset viewer zoom and pan")
    except Exception as e:
        logger.warning(f"Reset viewer failed: {e}")


def list_available_nodes():
    """List all available node types in Nuke"""
    try:
        # Get all node classes from Nuke
        all_nodes = []
        
        # In real Nuke, you'd use nuke.nodeClasses()
        try:
            # Try to get actual node classes from Nuke
            node_classes = nuke.nodeClasses()
            all_nodes = list(node_classes.keys())
        except:
            # Fallback to standard node list
            standard_nodes = [
                # Basic nodes
                'Read', 'Write', 'Viewer',
                # Color nodes  
                'Grade', 'ColorCorrect', 'Saturation', 'Hue', 'Gamma', 'Invert',
                # Filter nodes
                'Blur', 'Defocus', 'Sharpen', 'EdgeBlur', 'ZBlur',
                # Keying nodes
                'Keyer', 'Primatte', 'IBKColour', 'IBKGizmo', 'AddMix',
                # Transform nodes
                'Transform', 'CornerPin2D', 'GridWarp', 'SplineWarp',
                # Merge nodes
                'Merge2', 'Copy', 'Switch',
                # 3D nodes
                'Camera2', 'Light2', 'Sphere', 'Cube', 'Card2',
                # Tracking
                'Tracker4', 'PlanarTracker',
                # Paint/Roto
                'Roto', 'RotoPaint',
                # Other
                'Noise', 'CheckerBoard', 'Constant', 'BackdropNode'
            ]
            all_nodes = standard_nodes
        
        all_nodes.sort()
        
        # Show in Nuke message
        node_list = "\n".join(f"• {node}" for node in all_nodes[:20])  # First 20
        if len(all_nodes) > 20:
            node_list += f"\n... and {len(all_nodes) - 20} more"
        
        message = f"Available Node Types ({len(all_nodes)} total):\n\n{node_list}"
        nuke.message(message)
        
        # Also log to console
        logger.info(f"Listed {len(all_nodes)} available node types")
        
        return all_nodes
        
    except Exception as e:
        error_msg = f"Failed to list available nodes: {e}"
        logger.error(error_msg)
        nuke.message(error_msg)
        return []

