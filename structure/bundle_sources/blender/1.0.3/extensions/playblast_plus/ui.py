import os

import bpy
from bpy.types import Panel, Menu

from . import bl_info
from .lib.tokens import list_tokens
from .lib.custom_icons import get_icon_id
from .lib.utils import parse_suffixes


def _panel_title() -> str:
    v = bl_info["version"]
    title = f"Playblast Plus  v{v[0]}.{v[1]}.{v[2]}"
    ayon = os.getenv("AYON_PROJECT_NAME")
    if ayon:
        title += f"  -  {ayon}"
    return title


# ---------------------------------------------------------------------------
# Token insert menu
# ---------------------------------------------------------------------------

class PLAYBLASTPLUS_MT_token_menu(Menu):
    bl_label = "Insert Token"
    bl_idname = "PLAYBLASTPLUS_MT_token_menu"

    def draw(self, context):
        layout = self.layout
        for token, info in list_tokens().items():
            op = layout.operator(
                "playblastplus.insert_token",
                text=f"{info['label']}  {token}",
                icon='ADD',
            )
            op.token = token


class PLAYBLASTPLUS_MT_suffix_menu(Menu):
    bl_label = "Select Suffix"
    bl_idname = "PLAYBLASTPLUS_MT_suffix_menu"

    def draw(self, context):
        prefs = context.preferences.addons[__package__].preferences
        layout = self.layout
        props = context.scene.playblast_plus
        suffixes = parse_suffixes(prefs.output_suffixes)
        for s in suffixes:
            is_selected = props.output_suffix == s
            op = layout.operator(
                "playblastplus.set_suffix",
                text=s,
                icon='CHECKMARK' if is_selected else 'NONE',
            )
            op.suffix = s


# ---------------------------------------------------------------------------
# 3D viewport header menu
# ---------------------------------------------------------------------------

class VIEW3D_MT_playblastplus(Menu):
    bl_label = "Playblast Plus"
    bl_idname = "VIEW3D_MT_playblastplus"

    def draw(self, context):
        layout = self.layout
        layout.operator("playblastplus.run",      text="Playblast",    icon='RENDER_ANIMATION')
        layout.operator("playblastplus.snapshot", text="Snapshot",     icon='IMAGE')
        layout.separator()
        layout.operator("playblastplus.open_output", text="Open Folder", icon='FILE_FOLDER')
        layout.operator("playblastplus.open_last",   text="Open Last",   icon='FILE_MOVIE')


def _menu_func_view3d(self, context):
    self.layout.menu(VIEW3D_MT_playblastplus.bl_idname)


class PLAYBLASTPLUS_MT_creator_menu(Menu):
    bl_label = "Select Creator"
    bl_idname = "PLAYBLASTPLUS_MT_creator_menu"

    def draw(self, context):
        from .operators import _ayon_creator_cache
        layout = self.layout
        props = context.scene.playblast_plus
        for entry in _ayon_creator_cache:
            is_selected = props.ayon_creator_id == entry["id"]
            op = layout.operator(
                "playblastplus.set_ayon_creator",
                text=entry["label"],
                icon='CHECKMARK' if is_selected else 'NONE',
            )
            op.creator_id = entry["id"]


class PLAYBLASTPLUS_MT_variant_menu(Menu):
    bl_label = "Select Variant"
    bl_idname = "PLAYBLASTPLUS_MT_variant_menu"

    def draw(self, context):
        from .lib.ayon_config import load_config
        layout = self.layout
        props = context.scene.playblast_plus
        media_type = props.ayon_media_type
        cfg = load_config()
        variants = cfg.get(media_type, {}).get("variants", [])
        if not variants:
            layout.label(text="No variants configured", icon='INFO')
            return
        for v in variants:
            is_selected = props.ayon_variant == v
            op = layout.operator(
                "playblastplus.set_ayon_variant",
                text=v,
                icon='CHECKMARK' if is_selected else 'NONE',
            )
            op.variant = v


class PLAYBLASTPLUS_MT_media_file_menu(Menu):
    bl_label = "Select Media File"
    bl_idname = "PLAYBLASTPLUS_MT_media_file_menu"

    def draw(self, context):
        from .operators import _ayon_media_cache
        layout = self.layout
        props = context.scene.playblast_plus
        media_type = props.ayon_media_type
        entries = _ayon_media_cache.get(media_type, [])
        if not entries:
            layout.label(text="No files found", icon='INFO')
            return
        for entry in entries:
            fp = entry.get("path") or entry.get("pattern", "")
            is_selected = props.ayon_selected_file == fp
            op = layout.operator(
                "playblastplus.set_ayon_media_file",
                text=entry["label"],
                icon='CHECKMARK' if is_selected else 'NONE',
            )
            op.filepath = fp


# ---------------------------------------------------------------------------
# Main (flat) panel — no sub-panels, all content in boxes
# ---------------------------------------------------------------------------

class PLAYBLASTPLUS_PT_main(Panel):
    bl_label = _panel_title()
    bl_idname = "PLAYBLASTPLUS_PT_main"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Playblast Plus'

    def draw(self, context):
        layout = self.layout
        props = context.scene.playblast_plus
        prefs = context.preferences.addons[__package__].preferences

        # ── Header / description box (Shotput pattern) ──────────────────
        box = layout.box()
        col = box.column(align=True)
        ayon = os.getenv("AYON_PROJECT_NAME")
        header_row = col.row(align=True)
        if ayon:
            icon = get_icon_id("ayon")
            header_row.label(text="Playblast Plus — Animation Review", **icon)
        else:
            header_row.label(text="Playblast Plus — Animation Review", icon='RENDER_ANIMATION')
        header_row.operator(
            "playblastplus.open_preferences",
            text="",
            icon='PREFERENCES',
            emboss=False,
        )
        col.separator(factor=0.4)
        sub = col.column(align=True)
        sub.scale_y = 0.75
        if ayon and not prefs.ayon_quick_publish_enabled:
            sub.label(text="Go to prefs to enable AYON Quick Publish")
        else:
            sub.label(text="Capture and encode the viewport frame range")

        # ── Tool guard (format-aware) ─────────────────────────────────────
        from .lib.ffmpeg_utils import dl_state, find_ffmpeg

        if dl_state["running"]:
            box = layout.box()
            col = box.column(align=True)
            col.label(text="Downloading FFmpeg…", icon='IMPORT')
            col.progress(
                factor=dl_state["progress"],
                text=f"{int(dl_state['progress'] * 100)} %",
            )
            return
        if dl_state["error"]:
            box = layout.box()
            col = box.column(align=True)
            col.alert = True
            col.label(text="Download failed", icon='ERROR')
            col.label(text=dl_state["error"])
            col.separator(factor=0.3)
            col.operator("playblastplus.install_ffmpeg", text="Retry", icon='FILE_REFRESH')
            return
        if not find_ffmpeg(prefs.ffmpeg_path):
            warn = layout.box().column(align=True)
            warn.alert = True
            warn.label(text="FFmpeg not found", icon='ERROR')
            warn.label(text="Playblast Plus needs this to convert to mp4/APNG")
            warn.separator(factor=0.3)
            warn.operator("playblastplus.install_ffmpeg", icon='IMPORT')
            return

        if prefs.output_format == 'APNG':
            info = layout.box().column(align=True)
            info.alert = True
            info.label(text="APNG conversion can take some time at higher resolutions", icon='INFO')

            # ── APNG Preset ────────────────────────────────────────────
            from .lib.apng_presets import get_preset
            pbox = layout.box()
            pcol = pbox.column(align=True)
            pcol.label(text="Preset", icon='PRESET')
            pcol.prop(prefs, "apng_preset", text="")
            preset_data = get_preset(prefs.apng_preset)
            if preset_data:
                info_row = pcol.row(align=True)
                info_row.enabled = False
                info_row.label(
                    text=f"Resolution:  {preset_data['width']} \u00d7 {preset_data['height']}  @  {preset_data.get('framerate', '?')} fps"
                )
            pcol.operator("playblastplus.apply_apng_preset", icon='SCENE_DATA')

        # ── Camera ──────────────────────────────────────────────────────
        box = layout.box()
        col = box.column(align=True)
        col.label(text="Camera", icon='CAMERA_DATA')
        col.prop(props, "camera", text="")

        # ── Output name ─────────────────────────────────────────────────
        box = layout.box()
        col = box.column(align=True)
        col.label(text="Output Name", icon='FILE_TEXT')
        split = col.split(factor=0.7, align=True)
        left = split.row(align=True)
        left.prop(props, "output_token", text="")
        left.menu("PLAYBLASTPLUS_MT_token_menu", text="", icon='ADD')
        suffixes = parse_suffixes(prefs.output_suffixes)
        suffix_label = props.output_suffix if props.output_suffix in suffixes else "None"
        split.menu("PLAYBLASTPLUS_MT_suffix_menu", text=suffix_label, icon='DOWNARROW_HLT')

        # ── Shading (icon-only) ──────────────────────────────────────────
        box = layout.box()
        col = box.column(align=True)
        col.label(text="Shading", icon='SHADING_SOLID')
        row = col.row(align=True)
        row.prop_enum(props, "shading_mode", 'WIREFRAME', text="Wire",     icon='SHADING_WIRE')
        row.prop_enum(props, "shading_mode", 'SOLID',     text="Solid",    icon='SHADING_SOLID')
        row.prop_enum(props, "shading_mode", 'MATERIAL',  text="Material", icon='SHADING_TEXTURE')
        row.prop_enum(props, "shading_mode", 'RENDERED',  text="Render",   icon='SHADING_RENDERED')

        # ── Options (3 rows × 2 cols) ────────────────────────────────────
        box = layout.box()
        col = box.column(align=True)
        col.label(text="Overrides", icon='OVERLAY')

        grid = col.column(align=True)

        # Row 1: overlay mode
        row = grid.row(align=True)
        row.prop_enum(props, "overlay_mode", 'ON',  text="Overlays On")
        row.prop_enum(props, "overlay_mode", 'OFF', text="Overlays Off")

        # Row 2: bg only | wireframe
        row = grid.row(align=True)
        row.prop_enum(props, "overlay_mode", 'BACKGROUND', text="Bg Only")
        row.prop(props, "show_wireframe_overlay", toggle=True)

        # Row 3: cavity | outline — only shown in SOLID shading
        if props.shading_mode == 'SOLID':
            row = grid.row(align=True)
            row.prop(props, "show_cavity",  toggle=True)
            row.prop(props, "show_outline", toggle=True)

        # ── Output ───────────────────────────────────────────────────────
        box = layout.box()
        col = box.column(align=True)
        col.label(text="Output", icon='OUTPUT')
        row = col.row(align=True)
        row.prop(props, "half_res", toggle=True)
        if prefs.output_format == 'MP4':
            row.prop(props, "add_burnin", toggle=True)
        row = col.row(align=True)
        row.operator("playblastplus.open_output", text="Open Folder", icon='FILE_FOLDER')
        row.operator("playblastplus.open_last",   text="Open Last",   icon='FILE_MOVIE')

        # ── Capture ──────────────────────────────────────────────────────
        box = layout.box()
        col = box.column(align=True)
        col.label(text="Capture", icon='CAMERA_DATA')
        row = col.row(align=True)
        row.scale_y = 2.0
        if prefs.output_format == 'APNG':            
            row.alert = True
            row.operator("playblastplus.run", text="Create APNG", icon='RENDER_ANIMATION')
            row.alert = False        
        else:
            row.operator("playblastplus.run", text="Playblast", icon='RENDER_ANIMATION')

        row.operator("playblastplus.snapshot", text="Snap",      icon='IMAGE')

        # ── AYON Publish (only shown when running inside AYON with Quick Publish enabled) ────────────
        if os.getenv("AYON_PROJECT_NAME") and prefs.ayon_quick_publish_enabled:
            from .operators import (
                _ayon_creator_cache,
                _ayon_media_cache,
                _ayon_publish_procs,
                _ayon_last_publish_result,
            )
            from .lib.ayon_config import load_config

            layout.separator(factor=0.5)
            ayon_box = layout.box()
            ayon_col = ayon_box.column(align=True)

            # Section header
            header_row = ayon_col.row(align=True)
            ayon_icon = get_icon_id("ayon")
            header_row.label(text="Quick Publish", **ayon_icon)

            ayon_col.separator(factor=0.5)

            # Context info
            folder_path = os.getenv("AYON_FOLDER_PATH", "—")
            task_name   = os.getenv("AYON_TASK_NAME",   "—")
            ctx_col = ayon_col.column(align=True)
            ctx_col.scale_y = 0.8
            ctx_col.enabled = False
            ctx_col.label(text=f"Folder:  {folder_path}", icon='FILE_FOLDER')
            ctx_col.label(text=f"Task:    {task_name}",   icon='ARMATURE_DATA')

            ayon_col.separator(factor=0.5)

            # ── Media Type toggle ────────────────────────────────────────
            ayon_col.label(text="Media Type", icon='FILE_MOVIE')
            mt_row = ayon_col.row(align=True)
            mt_row.prop_enum(props, "ayon_media_type", "MP4",      text="MP4")
            mt_row.prop_enum(props, "ayon_media_type", "SEQUENCE", text="Sequence")
            mt_row.prop_enum(props, "ayon_media_type", "IMAGE",    text="Image")

            media_type = props.ayon_media_type

            # Warn if Sequence selected but keep_images is off
            if media_type == 'SEQUENCE' and not prefs.keep_images:
                warn_col = ayon_col.column(align=True)
                warn_col.alert = True
                warn_col.label(text="Enable 'Keep Images' in preferences", icon='ERROR')
                warn_col.label(text="to preserve frame sequences for publish.")

            ayon_col.separator(factor=0.3)

            # ── File selection (menu + refresh icon) ─────────────────────
            entries = _ayon_media_cache.get(media_type, [])
            selected_file = props.ayon_selected_file

            file_row = ayon_col.row(align=True)
            if entries:
                sel_label = "Select file…"
                for e in entries:
                    fp = e.get("path") or e.get("pattern", "")
                    if fp == selected_file:
                        sel_label = e["label"]
                        break
                file_row.menu(
                    "PLAYBLASTPLUS_MT_media_file_menu",
                    text=sel_label,
                    icon='FILE',
                )
            else:
                no_file = file_row.row(align=True)
                no_file.alert = True
                no_file.label(text="No files — press refresh", icon='INFO')
            file_row.operator(
                "playblastplus.refresh_ayon_media",
                text="",
                icon='FILE_REFRESH',
            )

            ayon_col.separator(factor=0.3)

            # ── Product type (filtered toggle buttons + inline refresh) ───
            cfg = load_config()
            allowed_products = cfg.get(media_type, {}).get("products", ["review"])
            filtered_creators = [
                c for c in _ayon_creator_cache
                if c["family"] in allowed_products
            ]

            ayon_col.label(text="Product Type", icon='SHADERFX')
            prod_row = ayon_col.row(align=True)
            if filtered_creators:
                for entry in filtered_creators:
                    is_selected = props.ayon_creator_id == entry["id"]
                    op = prod_row.operator(
                        "playblastplus.set_ayon_creator",
                        text=entry["label"],
                        depress=is_selected,
                    )
                    op.creator_id = entry["id"]
            else:
                no_cr_row = ayon_col.row(align=True)
                no_cr_row.alert = True
                no_cr_row.label(
                    text="Creators not configured — open Preferences",
                    icon='ERROR',
                )
                no_cr_row.operator(
                    "playblastplus.open_preferences",
                    text="",
                    icon='PREFERENCES',
                )

            ayon_col.separator(factor=0.3)

            # ── Variant field ─────────────────────────────────────────────
            var_row = ayon_col.row(align=True)
            var_row.prop(props, "ayon_variant", text="Variant")
            var_row.menu("PLAYBLASTPLUS_MT_variant_menu", text="", icon='DOWNARROW_HLT')

            ayon_col.separator(factor=0.3)

            # ── Publish button ────────────────────────────────────────────
            is_publishing = bool(_ayon_publish_procs)

            # file must be in the current media type's cache (not just non-empty)
            file_in_cache = bool(selected_file) and any(
                (e.get("path") or e.get("pattern", "")) == selected_file
                for e in entries
            )
            # creator must be valid for the current media type (in filtered list)
            creator_valid = bool(filtered_creators) and (
                props.ayon_creator_id in {c["id"] for c in filtered_creators}
            )
            variant_set = bool(props.ayon_variant.strip())

            can_publish = (
                file_in_cache
                and creator_valid
                and variant_set
                and not is_publishing
                and not (media_type == 'SEQUENCE' and not prefs.keep_images)
            )

            pub_row = ayon_col.row(align=True)
            pub_row.scale_y = 1.6
            pub_row.enabled = can_publish
            pub_row.operator(
                "playblastplus.ayon_publish",
                text="Publish to AYON",
                **get_icon_id("ayon"),
            )

            # ── Publish status ────────────────────────────────────────────
            if is_publishing:
                ayon_col.separator(factor=0.3)
                prog_row = ayon_col.row(align=True)
                prog_row.enabled = False
                prog_row.label(text="Publishing…", icon='SORTTIME')
            elif _ayon_last_publish_result:
                ayon_col.separator(factor=0.3)
                res_col = ayon_col.column(align=True)
                res_col.scale_y = 0.8
                res_col.enabled = False
                if _ayon_last_publish_result["success"]:
                    pub_info = _ayon_last_publish_result.get("pub_info", "")
                    display  = pub_info if pub_info else _ayon_last_publish_result["label"]
                    res_col.label(
                        text=f"Published: {display}",
                        icon='CHECKMARK',
                    )
                else:
                    res_col.alert = True
                    res_col.label(
                        text=f"Failed: {_ayon_last_publish_result['label']}",
                        icon='ERROR',
                    )


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

_CLASSES = [
    PLAYBLASTPLUS_MT_token_menu,
    PLAYBLASTPLUS_MT_suffix_menu,
    PLAYBLASTPLUS_MT_creator_menu,
    PLAYBLASTPLUS_MT_media_file_menu,
    PLAYBLASTPLUS_MT_variant_menu,
    VIEW3D_MT_playblastplus,
    PLAYBLASTPLUS_PT_main,
]


def register():
    for cls in _CLASSES:
        bpy.utils.register_class(cls)
    bpy.types.VIEW3D_HT_header.append(_menu_func_view3d)


def unregister():
    bpy.types.VIEW3D_HT_header.remove(_menu_func_view3d)
    for cls in reversed(_CLASSES):
        bpy.utils.unregister_class(cls)


