"""
Shortcuts utility functions for Nuke pipeline.

This module provides organized utility functions that can be used as shortcuts
in the Nuke shortcuts system.

Author: Pipeline Team
Date: July 2025
"""

# Import all utility functions from organized modules
from .basic_utilities import (
    select_all_nodes,
    deselect_all_nodes,
    frame_selected,
    frame_all,
    duplicate_selected,
    list_available_nodes,
    PasteFromClipboard2,
)

from .node_creation import (
    create_custom_grade_setup,
    create_read_write_setup,
    create_keying_setup,
    create_comp_setup
)

from .workflow_setups import (
    create_gizmo_with_backdrop,
    load_custom_gizmo_from_path,
    create_render_setup,
    create_dailies_setup
)

from .viewer_utilities import (
    toggle_overlay,
    reset_viewer,
    fit_viewer,
    toggle_viewer_channels,
    toggle_viewer_gain,
    center_viewer
)

# Export all utility functions
__all__ = [
    # Basic utilities
    'select_all_nodes',
    'deselect_all_nodes', 
    'frame_selected',
    'frame_all',
    'duplicate_selected',
    'list_available_nodes',
    'PasteFromClipboard2',
    
    # Node creation
    'create_custom_grade_setup',
    'create_read_write_setup',
    'create_keying_setup',
    'create_comp_setup',
    
    # Workflow setups
    'create_gizmo_with_backdrop',
    'load_custom_gizmo_from_path',
    'create_render_setup',
    'create_dailies_setup',
    
    # Viewer utilities
    'toggle_overlay',
    'reset_viewer',
    'fit_viewer',
    'toggle_viewer_channels',
    'toggle_viewer_gain',
    'center_viewer'
]
