"""
Node creation utilities for Nuke shortcuts.

Contains functions for creating complex node setups and arrangements.

Author: Pipeline Team
Date: July 2025
"""

import nuke
from utils.PipelineLogger import get_logger

logger = get_logger("NodeCreation")


def create_custom_grade_setup():
    """Create a custom grade node setup with multiple connected nodes"""
    try:
        # Create a Grade node
        grade = nuke.createNode('Grade')
        
        # Create a ColorCorrect node connected to it
        color_correct = nuke.createNode('ColorCorrect')
        color_correct.setInput(0, grade)
        
        # Create a Saturation node
        saturation = nuke.createNode('Saturation')
        saturation.setInput(0, color_correct)
        
        # Select the last node
        saturation.setSelected(True)
        grade.setSelected(False)
        color_correct.setSelected(False)
        
        logger.info("Created custom grade setup (Grade -> ColorCorrect -> Saturation)")
        return saturation
        
    except Exception as e:
        error_msg = f"Failed to create custom grade setup: {e}"
        logger.error(error_msg)
        nuke.message(error_msg)
        return None


def create_read_write_setup():
    """Create a basic Read->Write node setup"""
    try:
        # Create Read node
        read_node = nuke.createNode('Read')
        
        # Create Write node connected to Read
        write_node = nuke.createNode('Write')
        write_node.setInput(0, read_node)
        
        # Select the write node
        write_node.setSelected(True)
        read_node.setSelected(False)
        
        logger.info("Created Read->Write setup")
        return write_node
        
    except Exception as e:
        error_msg = f"Failed to create Read->Write setup: {e}"
        logger.error(error_msg)
        nuke.message(error_msg)
        return None


def create_keying_setup():
    """Create a basic keying node setup"""
    try:
        # Create Keyer node
        keyer = nuke.createNode('Keyer')
        
        # Create Grade for edge refinement
        edge_grade = nuke.createNode('Grade')
        edge_grade.setInput(0, keyer)
        edge_grade['label'].setValue('Edge Refinement')
        
        # Create Blur for edge softening
        edge_blur = nuke.createNode('Blur')
        edge_blur.setInput(0, edge_grade)
        edge_blur['label'].setValue('Edge Softening')
        
        # Select the last node
        edge_blur.setSelected(True)
        keyer.setSelected(False)
        edge_grade.setSelected(False)
        
        logger.info("Created keying setup (Keyer -> Grade -> Blur)")
        return edge_blur
        
    except Exception as e:
        error_msg = f"Failed to create keying setup: {e}"
        logger.error(error_msg)
        nuke.message(error_msg)
        return None


def create_comp_setup():
    """Create a basic compositing setup with foreground and background inputs"""
    try:
        # Create input nodes
        fg_input = nuke.createNode('Input')
        fg_input['label'].setValue('Foreground')
        
        bg_input = nuke.createNode('Input')
        bg_input['label'].setValue('Background')
        bg_input.setXYpos(fg_input.xpos() + 150, fg_input.ypos())
        
        # Create merge node
        merge = nuke.createNode('Merge2')
        merge.setInput(0, bg_input)  # Background (A input)
        merge.setInput(1, fg_input)  # Foreground (B input)
        merge.setXYpos(fg_input.xpos() + 75, fg_input.ypos() + 100)
        
        # Create output
        output = nuke.createNode('Output')
        output.setInput(0, merge)
        output.setXYpos(merge.xpos(), merge.ypos() + 100)
        
        # Select the merge node
        merge.setSelected(True)
        
        logger.info("Created compositing setup (FG + BG -> Merge -> Output)")
        return merge
        
    except Exception as e:
        error_msg = f"Failed to create comp setup: {e}"
        logger.error(error_msg)
        nuke.message(error_msg)
        return None
