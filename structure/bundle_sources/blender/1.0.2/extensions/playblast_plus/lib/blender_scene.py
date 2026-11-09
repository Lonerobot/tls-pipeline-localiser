from pathlib import Path

import bpy

from .bases import Scene

# Capture __package__ at import time, stripping the .lib subpackage so that
# bpy.utils.extension_path_user receives the top-level addon package name.
_PKG = __package__.rpartition('.')[0] or __package__


def _user_path(subpath: str = "") -> Path:
    """Return a writable per-user directory for this addon.

    Uses ``bpy.utils.extension_path_user`` when running as a proper extension
    (``bl_ext.*`` namespace).  Falls back to
    ``bpy.utils.resource_path('USER')/playblast_plus`` when loaded via
    Script Directories as a legacy addon.
    """
    try:
        base = Path(bpy.utils.extension_path_user(_PKG, path=subpath, create=True))
    except (ValueError, RuntimeError):
        # Legacy addon path (Script Directories / not an installed extension)
        base = Path(bpy.utils.resource_path('USER')) / 'playblast_plus'
        if subpath:
            base = base / subpath
        base.mkdir(parents=True, exist_ok=True)
    return base


class Blender_Scene(Scene):

    @staticmethod
    def main_window():
        """Blender has no Qt main window — returns None."""
        return None


    @staticmethod
    def get_name(full_path: bool = False) -> str:
        filepath = bpy.data.filepath
        if filepath:
            path = Path(filepath)
            return str(path) if full_path else path.stem
        return None

    @staticmethod
    def get_scene_cameras():
        return [obj.name for obj in bpy.data.objects if obj.type == 'CAMERA']

    @staticmethod
    def get_current_camera():
        cam = bpy.context.scene.camera
        return cam.name if cam else None

    @staticmethod
    def set_viewport_camera(name: str):
        obj = bpy.data.objects.get(name)
        if obj and obj.type == 'CAMERA':
            bpy.context.scene.camera = obj

    @staticmethod
    def current_frame() -> int:
        return bpy.context.scene.frame_current

    @staticmethod
    def getFrameRate() -> int:
        return bpy.context.scene.render.fps

    @staticmethod
    def getFrameRange() -> tuple:
        scene = bpy.context.scene
        return (scene.frame_start, scene.frame_end)

    @staticmethod
    def get_render_resolution(multiplier: float = 1.0) -> tuple:
        render = bpy.context.scene.render
        scale = render.resolution_percentage / 100.0
        width = int(render.resolution_x * scale * multiplier)
        height = int(render.resolution_y * scale * multiplier)
        return (width, height)

    @staticmethod
    def get_user_directory() -> str:
        """Per-user storage directory (works for both extension and legacy installs)."""
        return str(_user_path())

    @staticmethod
    def get_output_dir() -> str:
        """Returns a 'playblasts' folder next to the .blend file.
        Falls back to the user directory if the file is unsaved.
        """
        filepath = bpy.data.filepath
        if filepath:
            playblast_dir = Path(filepath).parent / 'playblasts'
        else:
            playblast_dir = _user_path() / 'playblasts'

        playblast_dir.mkdir(parents=True, exist_ok=True)
        return str(playblast_dir)

    @staticmethod
    def get_temp_capture_dir() -> str:
        """Temporary directory for raw PNG frame sequences before FFmpeg encode."""
        return str(_user_path('pbp_captures'))

    @staticmethod
    def warning_message(text: str):
        print(f"WARNING: {text}")

    @staticmethod
    def info_message(text: str):
        print(text)

    @staticmethod
    def error_message(text: str):
        print(f"ERROR: {text}")
