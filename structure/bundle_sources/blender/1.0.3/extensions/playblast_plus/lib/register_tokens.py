"""Register Blender-specific tokens with the bundled token system.

This module is kept for backwards compatibility. Tokens are also registered
directly in __init__.py when the extension loads.
"""
import os
from pathlib import Path

from . import tokens
from .blender_scene import Blender_Scene
from .utils import extract_version_from_stem


tokens.register_token(
    "<camera>",
    lambda options: Blender_Scene.get_current_camera() or "camera",
    label="Camera name",
)

tokens.register_token(
    "<scene>",
    lambda options: Blender_Scene.get_name() or "playblast",
    label="Current scene name",
)

tokens.register_token(
    "<blendfile>",
    lambda options: Blender_Scene.get_name() or "playblast",
    label="Blend file name without extension",
)

tokens.register_token(
    "<viewlayer>",
    lambda options: __import__('bpy').context.view_layer.name,
    label="Active view layer",
)

def _resolve_version(options) -> str:
    import bpy
    fp = bpy.data.filepath
    return extract_version_from_stem(Path(fp).stem if fp else "")


tokens.register_token(
    "<version>",
    _resolve_version,
    label="Version string from blend file name (e.g. v001)",
)

# ── AYON tokens — only registered when running inside an AYON pipeline ──────
if os.getenv("AYON_PROJECT_NAME") and os.getenv("AYON_WORKDIR"):
    tokens.register_token(
        "<ayon_project>",
        lambda options: os.getenv("AYON_PROJECT_NAME", ""),
        label="AYON project name",
    )
    tokens.register_token(
        "<ayon_task>",
        lambda options: os.getenv("AYON_TASK_NAME", ""),
        label="AYON task name",
    )
