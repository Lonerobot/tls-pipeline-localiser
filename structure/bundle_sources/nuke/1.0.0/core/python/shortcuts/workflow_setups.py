"""
Workflow setup utilities for Nuke shortcuts.

Contains functions for creating complex gizmo setups and advanced workflows.

Author: Pipeline Team
Date: July 2025
"""

import nuke
import os
import glob
from pathlib import Path
from utils.PipelineLogger import get_logger

logger = get_logger("WorkflowSetups")


def create_gizmo_with_backdrop():
    """Create a gizmo and automatically wrap it in a backdrop"""
    try:
        # Get the gizmo name from user
        gizmo_name = nuke.getInput('Gizmo Name', 'MyGizmo')
        if not gizmo_name:
            return None
        
        # Create the gizmo
        gizmo = nuke.createNode(gizmo_name)
        
        # Create a backdrop around it
        backdrop = nuke.createNode('BackdropNode')
        backdrop['label'].setValue(f"{gizmo_name} Setup")
        backdrop['note_font_size'].setValue(20)
        
        # Position the backdrop around the gizmo
        gizmo_pos = [gizmo.xpos(), gizmo.ypos()]
        backdrop.setXYpos(gizmo_pos[0] - 50, gizmo_pos[1] - 50)
        backdrop['bdwidth'].setValue(200)
        backdrop['bdheight'].setValue(150)
        
        logger.info(f"Created {gizmo_name} with backdrop")
        return gizmo
        
    except Exception as e:
        error_msg = f"Failed to create gizmo with backdrop: {e}"
        logger.error(error_msg)
        nuke.message(error_msg)
        return None


def load_custom_gizmo_from_path():
    """Load a custom gizmo from a specific path"""
    try:
        # You can customize this path or make it configurable
        gizmo_path = "Y:/PIPELINE/gizmos/custom"
        
        # Get list of available gizmos
        gizmo_files = glob.glob(f"{gizmo_path}/*.gizmo")
        
        if not gizmo_files:
            nuke.message(f"No gizmos found in {gizmo_path}")
            return None
        
        # Show a dialog to select gizmo
        gizmo_names = [Path(f).stem for f in gizmo_files]
        choice = nuke.choice('Select Gizmo', 'Choose a gizmo to create:', gizmo_names)
        
        if choice is not None:
            selected_gizmo = gizmo_names[choice]
            gizmo = nuke.createNode(selected_gizmo)
            logger.info(f"Created custom gizmo: {selected_gizmo}")
            return gizmo
        
    except Exception as e:
        error_msg = f"Failed to load custom gizmo: {e}"
        logger.error(error_msg)
        nuke.message(error_msg)
        return None


def create_render_setup():
    """Create a complete render setup with multiple write nodes"""
    try:
        # Get the input node (or create one if none selected)
        selected = nuke.selectedNodes()
        if selected:
            input_node = selected[0]
        else:
            input_node = nuke.createNode('Read')
            input_node['label'].setValue('Main Input')
        
        # Create beauty write
        beauty_write = nuke.createNode('Write')
        beauty_write.setInput(0, input_node)
        beauty_write['label'].setValue('Beauty Pass')
        beauty_write['file'].setValue('[python {nuke.script_directory()}]/renders/[python {nuke.root().name().split(".")[0]}]_beauty_v001.exr')
        
        # Create proxy write
        proxy_write = nuke.createNode('Write')
        proxy_write.setInput(0, input_node)
        proxy_write['label'].setValue('Proxy')
        proxy_write['file'].setValue('[python {nuke.script_directory()}]/renders/proxy/[python {nuke.root().name().split(".")[0]}]_proxy_v001.mov')
        proxy_write.setXYpos(beauty_write.xpos() + 200, beauty_write.ypos())
        
        # Position the writes below the input
        beauty_write.setXYpos(input_node.xpos() - 100, input_node.ypos() + 100)
        proxy_write.setXYpos(input_node.xpos() + 100, input_node.ypos() + 100)
        
        # Create a backdrop for the render setup
        backdrop = nuke.createNode('BackdropNode')
        backdrop['label'].setValue('Render Setup')
        backdrop['note_font_size'].setValue(24)
        backdrop.setXYpos(input_node.xpos() - 150, input_node.ypos() - 50)
        backdrop['bdwidth'].setValue(400)
        backdrop['bdheight'].setValue(200)
        
        logger.info("Created render setup with beauty and proxy writes")
        return beauty_write
        
    except Exception as e:
        error_msg = f"Failed to create render setup: {e}"
        logger.error(error_msg)
        nuke.message(error_msg)
        return None


def create_dailies_setup():
    """Create a dailies/review setup with slate and burn-ins"""
    try:
        # Get input
        selected = nuke.selectedNodes()
        if selected:
            input_node = selected[0]
        else:
            input_node = nuke.createNode('Read')
            input_node['label'].setValue('Comp Input')
        
        # Create reformat for delivery
        reformat = nuke.createNode('Reformat')
        reformat.setInput(0, input_node)
        reformat['format'].setValue('HD_1080')
        reformat['label'].setValue('HD Delivery Format')
        
        # Create text node for burn-ins
        text_node = nuke.createNode('Text2')
        text_node.setInput(0, reformat)
        text_node['message'].setValue('[python {nuke.script_directory().split("/")[-1]}] - [python {nuke.root().name()}] - Frame [frame]')
        text_node['box'].setValue([50, 50, 1870, 100])
        text_node['label'].setValue('Burn-in Text')
        
        # Create write for dailies
        dailies_write = nuke.createNode('Write')
        dailies_write.setInput(0, text_node)
        dailies_write['label'].setValue('Dailies Output')
        dailies_write['file'].setValue('[python {nuke.script_directory()}]/dailies/[python {nuke.root().name().split(".")[0]}]_dailies_v001.mov')
        
        # Position nodes
        reformat.setXYpos(input_node.xpos(), input_node.ypos() + 100)
        text_node.setXYpos(reformat.xpos(), reformat.ypos() + 100)
        dailies_write.setXYpos(text_node.xpos(), text_node.ypos() + 100)
        
        logger.info("Created dailies setup with reformat, burn-ins, and output")
        return dailies_write
        
    except Exception as e:
        error_msg = f"Failed to create dailies setup: {e}"
        logger.error(error_msg)
        nuke.message(error_msg)
        return None
