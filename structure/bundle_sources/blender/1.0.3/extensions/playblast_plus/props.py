import bpy
from bpy.props import (
    BoolProperty,
    EnumProperty,
    StringProperty,
    PointerProperty,
)


def _reset_ayon_selection(self):
    """Reset file and creator selection when media type changes."""
    self.ayon_selected_file = ""
    self.ayon_creator_id = ""


def _look_through_camera(self, context):
    """Update callback: switch the viewport to look through the selected camera."""
    cam_name = self.camera
    if not cam_name or cam_name == 'NONE' or cam_name not in bpy.data.objects:
        return
    cam_obj = bpy.data.objects[cam_name]
    context.scene.camera = cam_obj
    space = context.space_data
    if space and space.type == 'VIEW_3D':
        space.camera = cam_obj
        # context.region_3d is not set in PropertyGroup update callbacks;
        # access RegionView3D via the WINDOW region's data attribute instead
        area = context.area
        if area:
            for region in area.regions:
                if region.type == 'WINDOW':
                    region.data.view_perspective = 'CAMERA'
                    break


class PlayblastPlusProps(bpy.types.PropertyGroup):
    """Per-scene Playblast Plus settings — stored with the .blend file."""

    output_token: StringProperty(
        name="Output Name",
        description="Token string used to build the output filename",
        default="<scene>_<user>_<camera>",
    )

    output_suffix: StringProperty(
        name="Suffix",
        description=(
            "Predefined suffix appended to the output filename with an underscore. "
            "Select 'None' to add no suffix"
        ),
        default="None",
    )

    camera: EnumProperty(
        name="Camera",
        description="Camera to use for the viewport render — switches the viewport immediately",
        items=lambda self, context: (
            [(o.name, o.name, "") for o in bpy.data.objects if o.type == 'CAMERA']
            or [("NONE", "No cameras in scene", "")]
        ),
        update=_look_through_camera,
    )

    # ------------------------------------------------------------------
    # Viewport shading
    # ------------------------------------------------------------------

    shading_mode: EnumProperty(
        name="Shading",
        description="Viewport shading mode used during the playblast",
        items=[
            ('WIREFRAME', "Wireframe", "Render in wireframe shading",
             'SHADING_WIRE', 0),
            ('SOLID', "Solid", "Render in solid shading",
             'SHADING_SOLID', 1),
            ('MATERIAL', "Material Preview", "Render with material preview shading",
             'SHADING_TEXTURE', 2),
            ('RENDERED', "Rendered", "Render using the active render engine preview",
             'SHADING_RENDERED', 3),
        ],
        default='SOLID',
    )

    # ------------------------------------------------------------------
    # Overlay toggles
    # ------------------------------------------------------------------

    overlay_mode: EnumProperty(
        name="Overlays",
        description="Overlay visibility during capture",
        items=[
            ('ON',         "On",      "Show all viewport overlays"),
            ('OFF',        "Off",     "Hide all viewport overlays"),
            ('BACKGROUND', "Bg Only", "Show camera background images only (hides other overlays)"),
        ],
        default='ON',
    )

    show_wireframe_overlay: BoolProperty(
        name="Wireframe",
        description="Draw wireframe on top of shading — forces overlays on",
        default=False,
    )

    show_cavity: BoolProperty(
        name="Cavity",
        description="Show cavity shading (only available in Solid shading mode)",
        default=False,
    )

    show_outline: BoolProperty(
        name="Outline",
        description="Show object outline (only available in Solid shading mode)",
        default=False,
    )

    # ------------------------------------------------------------------
    # Resolution & output
    # ------------------------------------------------------------------

    half_res: BoolProperty(
        name="Half Resolution",
        description="Render at 50 %% of the scene render resolution",
        default=False,
    )

    add_burnin: BoolProperty(
        name="Burnin",
        description="Embed a name / timecode burnin in the output video",
        default=False,
    )

    # ------------------------------------------------------------------
    # AYON publish
    # ------------------------------------------------------------------

    ayon_variant: StringProperty(
        name="Variant",
        description="AYON product variant for the review publish",
        default="Main",
    )

    ayon_creator_id: StringProperty(
        name="Creator",
        description="AYON traypublisher creator identifier to use for the publish",
        default="",
    )

    ayon_media_type: EnumProperty(
        name="Media Type",
        description="Type of media to publish to AYON",
        items=[
            ("MP4",      "MP4 Video",      "Publish an encoded MP4 playblast"),
            ("SEQUENCE", "Image Sequence", "Publish a PNG frame sequence (requires Keep Images)"),
            ("IMAGE",    "Still Image",    "Publish a single PNG snapshot"),
        ],
        default="MP4",
        update=lambda self, _ctx: _reset_ayon_selection(self),
    )

    ayon_selected_file: StringProperty(
        name="Selected File",
        description="Path or pattern of the media file or sequence to publish",
        default="",
    )

    # ------------------------------------------------------------------
    # Read-only state tracking (saved with .blend)
    # ------------------------------------------------------------------

    last_playblast: StringProperty(
        name="Last Playblast",
        description="Path of the most recently created playblast",
        default="",
    )

    last_output_dir: StringProperty(
        name="Last Output Directory",
        description="Output directory used for the last playblast",
        default="",
        options={'HIDDEN'},
    )

    last_temp_dir: StringProperty(
        name="Last Temp Directory",
        description="Temp capture directory used for the last playblast",
        default="",
        options={'HIDDEN'},
    )

    last_frame_count: bpy.props.IntProperty(
        name="Last Frame Count",
        description="Number of frames captured in the last playblast",
        default=0,
        options={'HIDDEN'},
    )


def register():
    bpy.utils.register_class(PlayblastPlusProps)
    bpy.types.Scene.playblast_plus = PointerProperty(type=PlayblastPlusProps)


def unregister():
    del bpy.types.Scene.playblast_plus
    bpy.utils.unregister_class(PlayblastPlusProps)
