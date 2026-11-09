import os

import bpy
from bpy.props import BoolProperty, EnumProperty, IntProperty, StringProperty

from .lib.ffmpeg_utils import default_download_url, find_ffmpeg
from .lib import apng_presets


class PlayblastPlusPreferences(bpy.types.AddonPreferences):
    bl_idname = __package__

    ffmpeg_path: StringProperty(
        name="FFmpeg Path",
        description=(
            "Absolute path to the ffmpeg executable. "
            "Leave blank to use the system PATH or the add-on's local bin/ folder."
        ),
        default="",
        subtype='FILE_PATH',
    )

    default_output_token: StringProperty(
        name="Default Output Token",
        description="Default token string used for output filenames",
        default="<scene>_<camera>",
    )

    output_suffixes: StringProperty(
        name="Output Suffixes",
        description=(
            "Comma-separated list of predefined output name suffixes. "
            "The first entry ('None' by default) means no suffix is added"
        ),
        default="None,Chalk,Turnaround,Rig,Anim",
    )

    encode_args: StringProperty(
        name="Encode Arguments",
        description="FFmpeg video codec arguments inserted between input and output",
        default="-c:v libx264 -crf 21 -preset ultrafast -pix_fmt yuv420p",
    )

    keep_images: BoolProperty(
        name="Keep Intermediate Images",
        description="Keep the raw PNG frame sequence after encoding to MP4",
        default=False,
    )

    download_url: StringProperty(
        name="FFmpeg Download URL",
        description="URL to download FFmpeg from. Defaults to gyan.dev essentials (Windows), BtbN (Linux), evermeet.cx (macOS)",
        default="",
    )

    output_format: EnumProperty(
        name="Output Format",
        description="Output format for the encoded playblast",
        items=[
            ('MP4',  "MP4",             "Encode to H.264 MP4 via FFmpeg (default)", 'FILE_MOVIE',  0),
            ('APNG', "APNG",            "Encode to Animated PNG via FFmpeg", 'IMAGE_DATA', 1),
        ],
        default='MP4',
    )

    apng_transparent: BoolProperty(
        name="Use Transparency",
        description=(
            "Capture frames with an alpha channel for transparent backgrounds. "
            "Automatically sets film_transparent on the scene during capture."
        ),
        default=True,
    )

    apng_tinify: BoolProperty(
        name="Optimise with Tinify",
        description="Upload the finished APNG to the Tinify API to reduce file size",
        default=False,
    )

    apng_tinify_key: StringProperty(
        name="Tinify API Key",
        description="Your Tinify API key (https://tinify.com)",
        default="",
        subtype='PASSWORD',
    )

    apng_timeout: IntProperty(
        name="APNG Encode Timeout",
        description="Maximum seconds to wait for APNG FFmpeg encoding to finish. Increase for long sequences at high resolution",
        default=300,
        min=30,
        soft_max=1800,
        subtype='TIME',
    )

    apng_preset: EnumProperty(
        name="APNG Preset",
        description="Preset resolution and frame rate. Apply to scene via the button in the panel",
        items=apng_presets.enum_items,
    )

    ayon_quick_publish_enabled: BoolProperty(
        name="Enable Quick Publish",
        description=(
            "Show the Quick Publish panel when Blender is launched via the AYON launcher. "
            "When disabled, the Quick Publish UI is hidden and a prompt to enable it is shown instead."
        ),
        default=False,
    )

    media_player_path: StringProperty(
        name="Media Review Player",
        description=(
            "Path to the executable used to open video playblasts (MP4, APNG). "
            "Leave blank to use the OS default. DJV2 is recommended — see https://github.com/grizzlypeak3d/DJV"
        ),
        default="",
        subtype='FILE_PATH',
    )

    image_player_path: StringProperty(
        name="Image Review Player",
        description=(
            "Path to the executable used to open still-image captures (PNG). "
            "Leave blank to use the OS default. DJV2 is recommended — see https://github.com/grizzlypeak3d/DJV"
        ),
        default="",
        subtype='FILE_PATH',
    )

    def draw(self, context):
        layout = self.layout

        # ── FFmpeg ────────────────────────────────────────────────────
        box = layout.box()
        col = box.column(align=True)
        col.label(text="FFmpeg", icon='FILE_MOVIE')

        found = find_ffmpeg(self.ffmpeg_path)
        if found:
            row = col.row()
            row.label(text="Found:", icon='CHECKMARK')
            row.label(text=found)
        else:
            warn = col.row()
            warn.alert = True
            warn.label(text="FFmpeg not found", icon='ERROR')

        col.prop(self, "ffmpeg_path")
        col.separator(factor=0.3)

        # Show additional search paths from config.json
        from .lib.ayon_config import load_ffmpeg_search_paths
        search_paths = load_ffmpeg_search_paths()
        if search_paths:
            sub = col.column(align=True)
            sub.scale_y = 0.75
            sub.label(text="Additional search paths (edit config.json to change):")
            for sp in search_paths:
                row = sub.row()
                row.enabled = False
                row.label(text=sp, icon='NONE')
            col.separator(factor=0.3)

        sub = col.column(align=True)
        sub.scale_y = 0.75
        sub.label(text="Download URL (leave blank for platform default):")
        col.prop(self, "download_url", text="")
        if not self.download_url:
            hint = col.row()
            hint.enabled = False
            hint.label(text=default_download_url())
        col.separator(factor=0.5)
        col.operator("playblastplus.install_ffmpeg", icon='IMPORT')
        col.separator()
        col.prop(self, "encode_args")

        # ── Output ────────────────────────────────────────────────────
        box = layout.box()
        col = box.column(align=True)
        col.label(text="Output", icon='OUTPUT')
        col.prop(self, "default_output_token")
        col.prop(self, "output_suffixes")
        col.prop(self, "keep_images")
        col.separator(factor=0.5)
        col.prop(self, "output_format")
        if self.output_format == 'APNG':
            box2 = box.box()
            col2 = box2.column(align=True)
            col2.label(text="APNG Options (Experimental)", icon='EXPERIMENTAL')                  
            col2.label(text="Increase this value if you get timeout errors in this mode")
            col2.prop(self, "apng_transparent")
            col2.prop(self, "apng_tinify")
            if self.apng_tinify:
                col2.label(text="Tinify compresses the APNG file using the Tinify API key")       
                col2.label(text="Register to get your free key and add it to the box below")      
                col2.label(text="https://tinify.com/developers", icon='URL') 
                col2.prop(self, "apng_tinify_key")
            col2.prop(self, "apng_timeout")

        # ── Viewer ────────────────────────────────────────────────────
        box = layout.box()
        col = box.column(align=True)
        col.label(text="Viewer", icon='HIDE_OFF')
        col.label(text="DJV2 is the recommended media viewer for playblast review.")
        col.label(text="https://github.com/grizzlypeak3d/DJV", icon='URL')
        col.separator(factor=0.3)
        col.prop(self, "media_player_path")
        if not self.media_player_path:
            hint = col.row()
            hint.enabled = False
            hint.label(text="(OS default — set a path to use a preferred viewer e.g. DJV2)")
        col.prop(self, "image_player_path")
        if not self.image_player_path:
            hint = col.row()
            hint.enabled = False
            hint.label(text="(OS default — set a path to use a preferred viewer e.g. DJV2)")

        # ── AYON Integration ──────────────────────────────────────────
        box = layout.box()
        col = box.column(align=True)
        col.label(text="AYON Integration", icon='URL')
        col.prop(self, "ayon_quick_publish_enabled")
        col.separator(factor=0.5)

        from .lib.ayon_config import load_creators
        creators = load_creators()

        if creators:
            row = col.row()
            row.label(text=f"{len(creators)} creator(s) configured:", icon='CHECKMARK')
            for c in creators:
                entry_row = col.row()
                entry_row.enabled = False
                entry_row.label(text=f"    {c.get('label', c['id'])}  —  {c['id']}", icon='NONE')
        else:
            warn = col.column(align=True)
            warn.alert = True
            warn.label(text="No AYON creators configured.", icon='ERROR')
            warn.alert = False
            warn.label(text="Click 'Get Publish Creators' to retrieve the publish types for your AYON instance.")
            warn.label(text="You can align these to the file types above, along with default")
            warn.label(text="variants in the config.json file in the add-on folder.")

        col.separator(factor=0.5)
        if os.getenv("AYON_PROJECT_NAME"):
            col.operator(
                "playblastplus.refresh_ayon_creators",
                text="Get Publish Creators",
                icon='FILE_REFRESH',
            )
        else:
            sub = col.column(align=True)
            sub.enabled = False
            sub.label(text="Launch Blender via the AYON launcher to enable AYON specific features.", icon='INFO')


def register():
    bpy.utils.register_class(PlayblastPlusPreferences)


def unregister():
    bpy.utils.unregister_class(PlayblastPlusPreferences)
