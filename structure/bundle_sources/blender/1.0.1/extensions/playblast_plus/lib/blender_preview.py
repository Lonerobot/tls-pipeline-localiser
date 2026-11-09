from pathlib import Path

import bpy

from .bases import PreviewRender
from .utils import Parsing

# Known Issues
# ============
# Blender 4.5.x OpenImageIO Crash (EXCEPTION_ACCESS_VIOLATION in ImageBufAlgo::zover)
# When rendering with film_transparent=False and RGB color mode, OpenImageIO's PNG writer
# can crash with an access violation. Workaround: always use RGBA mode for PNG output.
# Ref: The alpha channel will simply remain opaque when not needed.


def _find_view3d_context():
    """Find the first VIEW_3D window/area/region/space for context overriding.

    Returns:
        tuple: (window, area, region, space) or (None, None, None, None)
    """
    for window in bpy.context.window_manager.windows:
        for area in window.screen.areas:
            if area.type == 'VIEW_3D':
                for region in area.regions:
                    if region.type == 'WINDOW':
                        for space in area.spaces:
                            if space.type == 'VIEW_3D':
                                return window, area, region, space
    return None, None, None, None


class BlenderPreview(PreviewRender):

    def __init__(self):
        self._saved_state = {}

    # ------------------------------------------------------------------
    # State save / restore
    # ------------------------------------------------------------------

    def _save_state(self):
        render = bpy.context.scene.render
        self._saved_state['filepath'] = render.filepath
        self._saved_state['file_format'] = render.image_settings.file_format
        self._saved_state['color_mode'] = render.image_settings.color_mode
        self._saved_state['resolution_percentage'] = render.resolution_percentage
        self._saved_state['scene_camera'] = bpy.context.scene.camera
        self._saved_state['use_file_extension'] = render.use_file_extension

        _, _, _, space = _find_view3d_context()
        if space:
            ov = space.overlay
            self._saved_state['shading_type']               = space.shading.type
            self._saved_state['view_perspective']           = space.region_3d.view_perspective
            self._saved_state['space_camera']               = space.camera
            # Master toggle
            self._saved_state['show_overlays']              = ov.show_overlays
            # Individual overlays
            self._saved_state['show_bones']                 = ov.show_bones
            self._saved_state['show_extras']                = ov.show_extras
            self._saved_state['show_floor']                 = ov.show_floor
            self._saved_state['show_axis_x']                = ov.show_axis_x
            self._saved_state['show_axis_y']                = ov.show_axis_y
            self._saved_state['show_axis_z']                = ov.show_axis_z
            self._saved_state['show_text']                  = ov.show_text
            self._saved_state['show_cursor']                = ov.show_cursor
            self._saved_state['show_annotation']            = ov.show_annotation
            self._saved_state['show_relationship_lines']    = ov.show_relationship_lines
            self._saved_state['show_outline_selected']      = ov.show_outline_selected
            self._saved_state['show_motion_paths']          = ov.show_motion_paths
            self._saved_state['show_object_origins']        = ov.show_object_origins
            self._saved_state['show_wireframes']            = ov.show_wireframes
            self._saved_state['show_face_orientation']      = ov.show_face_orientation
            if bpy.app.version >= (2, 90, 0):
                self._saved_state['show_stats']             = ov.show_stats
            # Cavity + outline (shading attributes, not overlays)
            self._saved_state['shading_cavity']             = space.shading.show_cavity
            self._saved_state['shading_outline']            = space.shading.show_object_outline

        cam = bpy.context.scene.camera
        if cam and cam.data:
            self._saved_state['show_background_images'] = cam.data.show_background_images

        self._saved_state['film_transparent'] = bpy.context.scene.render.film_transparent

    def _restore_state(self):
        render = bpy.context.scene.render
        s = self._saved_state

        if 'filepath' in s:
            render.filepath = s['filepath']
        if 'file_format' in s:
            render.image_settings.file_format = s['file_format']
        if 'color_mode' in s:
            render.image_settings.color_mode = s['color_mode']
        if 'resolution_percentage' in s:
            render.resolution_percentage = s['resolution_percentage']
        if 'scene_camera' in s:
            bpy.context.scene.camera = s['scene_camera']
        if 'use_file_extension' in s:
            render.use_file_extension = s['use_file_extension']

        _, _, _, space = _find_view3d_context()
        if space:
            ov = space.overlay
            if 'shading_type' in s:
                space.shading.type = s['shading_type']
            if 'space_camera' in s:
                space.camera = s['space_camera']
            if 'view_perspective' in s:
                space.region_3d.view_perspective = s['view_perspective']
            # Individual overlays first, then master toggle
            _restore = [
                'show_bones', 'show_extras', 'show_floor',
                'show_axis_x', 'show_axis_y', 'show_axis_z',
                'show_text', 'show_cursor', 'show_annotation',
                'show_relationship_lines', 'show_outline_selected',
                'show_motion_paths', 'show_object_origins',
                'show_wireframes', 'show_face_orientation', 'show_stats',
            ]
            for key in _restore:
                if key in s:
                    setattr(ov, key, s[key])
            if 'show_overlays' in s:
                ov.show_overlays = s['show_overlays']
            if 'shading_cavity' in s:
                space.shading.show_cavity = s['shading_cavity']
            if 'shading_outline' in s:
                space.shading.show_object_outline = s['shading_outline']

        if 'show_background_images' in s:
            cam = bpy.context.scene.camera
            if cam and cam.data:
                cam.data.show_background_images = s['show_background_images']

        if 'film_transparent' in s:
            bpy.context.scene.render.film_transparent = s['film_transparent']

    # ------------------------------------------------------------------
    # PreviewRender interface
    # ------------------------------------------------------------------

    def pre_process(self, **kwargs):
        """Save render and viewport state before the capture sequence begins."""
        self._save_state()

    def post_process(self, **kwargs):
        """Restore render and viewport state after capture."""
        self._restore_state()

    def set_override_properties(self, **kwargs):
        """Apply viewport overrides before capture.

        Kwargs:
            camera (str): Name of the camera object to render from.
            shading_mode (str): WIREFRAME | SOLID | MATERIAL | RENDERED
            overlay_mode (str): ON | OFF | BACKGROUND
                ON         - show all overlays
                OFF        - hide all overlays
                BACKGROUND - hide overlays, show camera background images only
            show_wireframe_overlay (bool): Draw wireframe on top; forces overlays on.
            half_res (bool): Render at 50 % of the scene resolution.
        """
        render = bpy.context.scene.render
        _, _, _, space = _find_view3d_context()

        # Camera: set scene camera and push the viewport into camera view
        cam_name = kwargs.get('camera')
        if cam_name and cam_name in bpy.data.objects:
            cam_obj = bpy.data.objects[cam_name]
            bpy.context.scene.camera = cam_obj
            if space:
                space.camera = cam_obj
                space.region_3d.view_perspective = 'CAMERA'

        if kwargs.get('half_res', False):
            render.resolution_percentage = 50

        overlay_mode = kwargs.get('overlay_mode', 'ON')
        show_wireframe = kwargs.get('show_wireframe_overlay', False)

        if space is not None:
            shading_mode = kwargs.get('shading_mode', 'SOLID')
            space.shading.type = shading_mode
            ov = space.overlay
            # Cavity — only meaningful in SOLID mode
            space.shading.show_cavity = (
                kwargs.get('show_cavity', False) and shading_mode == 'SOLID'
            )
            space.shading.show_object_outline = (
                kwargs.get('show_outline', False) and shading_mode == 'SOLID'
            )

            if show_wireframe:
                # Wireframe overlay requires show_overlays=True, but suppress
                # everything else so only the wireframe is drawn
                space.overlay.show_overlays = True
                ov.show_wireframes         = True
                ov.show_floor              = False
                ov.show_axis_x             = False
                ov.show_axis_y             = False
                ov.show_axis_z             = False
                ov.show_bones              = False
                ov.show_extras             = False
                ov.show_text               = False
                ov.show_cursor             = False
                ov.show_annotation         = False
                ov.show_relationship_lines = False
                ov.show_outline_selected   = False
                ov.show_motion_paths       = False
                ov.show_object_origins     = False
                ov.show_face_orientation   = False
                if bpy.app.version >= (2, 90, 0):
                    ov.show_stats          = False
            elif overlay_mode == 'OFF':
                # Master toggle + explicit floor/axis disable for robustness
                space.overlay.show_overlays = False
                ov.show_floor              = False
                ov.show_axis_x             = False
                ov.show_axis_y             = False
                ov.show_axis_z             = False
            elif overlay_mode == 'BACKGROUND':
                # Keep master ON — disable every individual overlay so only
                # camera background images remain visible
                space.overlay.show_overlays = True
                ov.show_bones              = False
                ov.show_extras             = False
                ov.show_floor              = False
                ov.show_axis_x             = False
                ov.show_axis_y             = False
                ov.show_axis_z             = False
                ov.show_text               = False
                ov.show_cursor             = False
                ov.show_annotation         = False
                ov.show_relationship_lines = False
                ov.show_outline_selected   = False
                ov.show_motion_paths       = False
                ov.show_object_origins     = False
                ov.show_wireframes         = False
                ov.show_face_orientation   = False
                if bpy.app.version >= (2, 90, 0):
                    ov.show_stats          = False
            # else overlay_mode == 'ON': leave overlays untouched

        # Background images on camera: only explicitly set for BACKGROUND/OFF
        # modes. For ON, leave whatever the user currently has untouched.
        if overlay_mode == 'BACKGROUND':
            cam = bpy.context.scene.camera
            if cam and cam.data:
                cam.data.show_background_images = True
            # Disable film transparency so the viewport renders a solid background
            # behind the camera background images.  When film_transparent is True
            # Blender 5.x honours it for OpenGL viewport renders, producing a
            # fully-transparent (invisible) background even in bg-only mode.
            bpy.context.scene.render.film_transparent = False
        elif overlay_mode == 'OFF':
            cam = bpy.context.scene.camera
            if cam and cam.data:
                cam.data.show_background_images = False

    def create(self, **kwargs) -> str:
        """Render the full frame range as a PNG sequence via OpenGL viewport render.

        Kwargs:
            filename (str): Output path stem — no extension, no frame number.
                            Blender appends 4-digit frame numbers automatically
                            (e.g. ``/tmp/shot0001.png``).

        Returns:
            str: ffmpeg-compatible input path string, or None if no frames were
                 produced.
        """
        filename = str(kwargs['filename'])
        render = bpy.context.scene.render
        # Append '.' so Blender writes stem.0001.png (VFX dot convention;
        # create_ffmpeg_input's regex matches digits preceded by '.')
        render.filepath = filename + "."
        render.image_settings.file_format = 'PNG'
        # Force extension so frame files are written as stem.0001.png in Blender 4.x
        render.use_file_extension = True
        
        # Workaround for Blender 4.5 OpenImageIO crash (EXCEPTION_ACCESS_VIOLATION in zover)
        # When film_transparent=False with RGB color mode, OpenImageIO's PNG writer can crash.
        # Force RGBA mode to work around this Blender/OpenImageIO bug.
        # The alpha channel will be ignored during post-processing if needed.
        render.image_settings.color_mode = 'RGBA'

        window, area, region, _ = _find_view3d_context()
        if window and area and region:
            with bpy.context.temp_override(window=window, area=area, region=region):
                bpy.ops.render.opengl(animation=True, write_still=False)
        else:
            bpy.ops.render.opengl(animation=True, write_still=False)

        output_dir = Path(filename).parent
        stem = Path(filename).name
        frames = sorted(output_dir.glob(f'{stem}.????.png'))

        if frames:
            return Parsing.create_ffmpeg_input(str(frames[0]))
        return None

    def snapshot(self, **kwargs) -> str:
        """Render a single frame from the OpenGL viewport.

        Kwargs:
            filename (str): Output path stem (no extension).

        Returns:
            str: Path to the saved PNG file.
        """
        filename = str(kwargs['filename'])
        render = bpy.context.scene.render
        original_filepath = render.filepath
        original_format = render.image_settings.file_format

        render.filepath = filename
        render.image_settings.file_format = 'PNG'
        # Force extension so the file is written with .png in Blender 4.x
        original_use_file_extension = render.use_file_extension
        render.use_file_extension = True

        window, area, region, _ = _find_view3d_context()
        if window and area and region:
            with bpy.context.temp_override(window=window, area=area, region=region):
                bpy.ops.render.opengl(write_still=True)
        else:
            bpy.ops.render.opengl(write_still=True)

        render.filepath = original_filepath
        render.image_settings.file_format = original_format
        render.use_file_extension = original_use_file_extension

        saved_path = filename if filename.endswith('.png') else f'{filename}.png'
        return saved_path

    def notify_user(self, message: str):
        print(f"[PlayblastPlus] {message}")
