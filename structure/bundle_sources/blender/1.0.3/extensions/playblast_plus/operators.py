import shutil
from pathlib import Path

import bpy
from bpy.types import Operator

from .lib.blender_scene import Blender_Scene
from .lib.blender_preview import BlenderPreview
from .lib import encode, tokens, utils
from .lib.ffmpeg_utils import dl_state, find_ffmpeg, start_install


def _ffmpeg_path(context) -> str | None:
    """Return the ffmpeg executable path using the 3-step discovery order."""
    prefs = context.preferences.addons[__package__].preferences
    return find_ffmpeg(prefs.ffmpeg_path)


# ---------------------------------------------------------------------------
# Main viewport render
# ---------------------------------------------------------------------------

class PLAYBLASTPLUS_OT_run(Operator):
    """Render the active viewport frame range and encode to MP4"""
    bl_idname = "playblastplus.run"
    bl_label = "Viewport Render"
    bl_description = "Capture the viewport frame range and encode to MP4"

    def execute(self, context):
        props = context.scene.playblast_plus
        prefs = context.preferences.addons[__package__].preferences

        ffmpeg = _ffmpeg_path(context)
        if not ffmpeg:
            self.report(
                {'ERROR'},
                "FFmpeg not found. Set a path in Preferences → Add-ons → Playblast Plus "
                "or use Install FFmpeg.",
            )
            return {'CANCELLED'}

        # ------------------------------------------------------------------
        # Paths
        # ------------------------------------------------------------------
        output_dir = Blender_Scene.get_output_dir()
        temp_dir   = Blender_Scene.get_temp_capture_dir()
        output_name = tokens.format_tokens(props.output_token, None) or "playblast"
        if props.output_suffix and props.output_suffix != "None":
            output_name = f"{output_name}_{props.output_suffix}"

        # ------------------------------------------------------------------
        # Capture
        # ------------------------------------------------------------------
        renderer = BlenderPreview()
        # Capture film_transparent before any state changes so the restore
        # below always reflects the user's original setting.
        _orig_film_transparent = context.scene.render.film_transparent
        renderer.pre_process()
        renderer.set_override_properties(
            camera=props.camera,
            shading_mode=props.shading_mode,
            overlay_mode=props.overlay_mode,
            show_wireframe_overlay=props.show_wireframe_overlay,
            show_cavity=props.show_cavity,
            show_outline=props.show_outline,
            half_res=props.half_res,
        )

        # Apply transparency override for APNG if requested
        if prefs.output_format == 'APNG' and prefs.apng_transparent:
            context.scene.render.film_transparent = True
            context.scene.render.image_settings.color_mode = 'RGBA'

        ffmpeg_input = renderer.create(filename=str(Path(temp_dir) / output_name))
        renderer.post_process()
        context.scene.render.film_transparent = _orig_film_transparent

        if not ffmpeg_input:
            self.report({'ERROR'}, "PlayblastPlus: capture produced no frames.")
            return {'CANCELLED'}

        # ------------------------------------------------------------------
        # Encode
        # ------------------------------------------------------------------
        framerate   = Blender_Scene.getFrameRate()
        frame_start, frame_end = Blender_Scene.getFrameRange()
        frame_count = int(frame_end - frame_start + 1)

        if prefs.output_format == 'APNG':
            output_path = str(Path(output_dir) / f"{output_name}.apng")
            print(
                f"[PlayblastPlus] APNG encode: {ffmpeg_input} "
                f"@ {int(round(framerate))} fps → {output_path}"
            )
            import time as _time
            _t_encode = _time.monotonic()
            ok = encode.apng_from_image_sequence(
                ffmpeg_path=ffmpeg,
                image_seq_path=ffmpeg_input,
                output_path=output_path,
                framerate=framerate,
                start_frame=int(frame_start),
                end_frame=frame_count,
                post_open=not (prefs.apng_tinify and prefs.apng_tinify_key),
                timeout=prefs.apng_timeout,
                player_path=prefs.media_player_path,
            )
            if not ok and not Path(output_path).is_file():
                self.report({'ERROR'}, "PlayblastPlus: APNG encode failed or timed out. Increase 'APNG Encode Timeout' in add-on preferences if needed.")
            if ok:
                _encode_secs = _time.monotonic() - _t_encode
                _apng_mb = Path(output_path).stat().st_size / (1024 * 1024)
                print(
                    f"[PlayblastPlus] APNG encode done in {_encode_secs:.1f}s  "
                    f"— output size: {_apng_mb:.2f} MB"
                )
            if ok and prefs.apng_tinify:
                if not prefs.apng_tinify_key:
                    print("[PlayblastPlus] Tinify: skipped — API key not set")
                    self.report({'WARNING'}, "PlayblastPlus: Tinify key is not set in preferences")
                else:
                    from .lib.tinify_client import compress_file
                    print(f"[PlayblastPlus] Tinify: uploading {_apng_mb:.2f} MB to api.tinify.com…")
                    tinify_ok, tinify_info = compress_file(prefs.apng_tinify_key, output_path, output_path)
                    if tinify_ok:
                        print(
                            f"[PlayblastPlus] Tinify: \u2713 compressed in {tinify_info['elapsed_s']:.1f}s  "
                            f"{tinify_info['size_before_mb']:.2f} MB \u2192 {tinify_info['size_after_mb']:.2f} MB  "
                            f"({tinify_info['saved_pct']:.1f}% saved)  "
                            f"[{tinify_info['compressions_this_month']} compressions this month]"
                        )
                    else:
                        print(f"[PlayblastPlus] Tinify: \u2717 {tinify_info['message']}")
                        self.report({'WARNING'}, f"PlayblastPlus: Tinify failed — {tinify_info['message']}")
                    if tinify_ok:
                        import bpy as _bpy
                        _bpy.ops.wm.path_open(filepath=output_path)
        else:
            output_path = str(Path(output_dir) / f"{output_name}.mp4")
            ok = encode.mp4_from_image_sequence(
                ffmpeg_path=ffmpeg,
                image_seq_path=ffmpeg_input,
                output_path=output_path,
                framerate=framerate,
                start_frame=int(frame_start),
                end_frame=frame_count,
                add_burnin=props.add_burnin,
                burnin_text=output_name,
                post_open=True,
                input_args=prefs.encode_args,
                player_path=prefs.media_player_path,
            )

        if not ok:
            self.report({'ERROR'}, "PlayblastPlus: encode failed.")
            return {'CANCELLED'}

        props.last_playblast = output_path
        props.last_output_dir = output_dir
        props.last_temp_dir = temp_dir

        # ------------------------------------------------------------------
        # Frame cleanup
        # ------------------------------------------------------------------
        if prefs.keep_images:
            frames_dir = Path(output_dir) / 'frames' / output_name
            frames_dir.mkdir(parents=True, exist_ok=True)
            moved = 0
            for f in Path(temp_dir).iterdir():
                if f.suffix == '.png' and f.name.startswith(output_name + '.'):
                    shutil.move(str(f), str(frames_dir / f.name))
                    moved += 1
            self.report(
                {'INFO'},
                f"PlayblastPlus: saved \u2192 {output_path}  |  {moved} frames \u2192 {frames_dir}",
            )
        else:
            utils.FolderOps.purge_contents(temp_dir, ext='.png')
            self.report({'INFO'}, f"PlayblastPlus: saved → {output_path}")
        return {'FINISHED'}


# ---------------------------------------------------------------------------
# Snapshot
# ---------------------------------------------------------------------------

class PLAYBLASTPLUS_OT_snapshot(Operator):
    """Capture a single frame from the active viewport"""
    bl_idname = "playblastplus.snapshot"
    bl_label = "Snap"
    bl_description = "Capture a single viewport frame as PNG"

    def execute(self, context):
        props = context.scene.playblast_plus

        output_dir  = Blender_Scene.get_output_dir()
        captures_dir = Path(output_dir) / 'captures'
        captures_dir.mkdir(exist_ok=True)

        output_name = tokens.format_tokens(props.output_token, None) or "playblast"
        if props.output_suffix and props.output_suffix != "None":
            output_name = f"{output_name}_{props.output_suffix}"
        frame_str   = str(Blender_Scene.current_frame()).zfill(4)

        renderer = BlenderPreview()
        renderer.pre_process()
        renderer.set_override_properties(
            shading_mode=props.shading_mode,
            overlay_mode=props.overlay_mode,
            show_wireframe_overlay=props.show_wireframe_overlay,
            show_cavity=props.show_cavity,
            show_outline=props.show_outline,
        )

        snap_path = renderer.snapshot(
            filename=str(captures_dir / f'{output_name}_{frame_str}')
        )
        renderer.post_process()

        props.last_playblast = snap_path or ""
        self.report({'INFO'}, f"PlayblastPlus: snapshot → {snap_path}")
        return {'FINISHED'}


# ---------------------------------------------------------------------------
# Token helper
# ---------------------------------------------------------------------------

class PLAYBLASTPLUS_OT_insert_token(Operator):
    """Append a token to the output name field"""
    bl_idname = "playblastplus.insert_token"
    bl_label = "Insert Token"
    bl_description = "Append this token to the Output Name field"

    token: bpy.props.StringProperty(name="Token")

    def execute(self, context):
        props = context.scene.playblast_plus
        props.output_token = props.output_token + self.token
        return {'FINISHED'}


class PLAYBLASTPLUS_OT_set_ayon_variant(Operator):
    """Set the AYON publish variant"""
    bl_idname = "playblastplus.set_ayon_variant"
    bl_label = "Set Variant"
    bl_description = "Use this variant for the AYON publish"

    variant: bpy.props.StringProperty(name="Variant")

    def execute(self, context):
        context.scene.playblast_plus.ayon_variant = self.variant
        return {'FINISHED'}


class PLAYBLASTPLUS_OT_set_suffix(Operator):
    """Set the predefined output name suffix"""
    bl_idname = "playblastplus.set_suffix"
    bl_label = "Set Suffix"
    bl_description = "Apply this predefined suffix to the output filename"

    suffix: bpy.props.StringProperty(name="Suffix")

    def execute(self, context):
        context.scene.playblast_plus.output_suffix = self.suffix
        return {'FINISHED'}


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

class PLAYBLASTPLUS_OT_open_output(Operator):
    """Open the playblast output folder in the system file explorer"""
    bl_idname = "playblastplus.open_output"
    bl_label = "Open Output Folder"
    bl_description = "Open the output folder in the system file explorer"

    def execute(self, context):
        utils.FolderOps.explore(Blender_Scene.get_output_dir())
        return {'FINISHED'}


class PLAYBLASTPLUS_OT_open_last(Operator):
    """Open the most recently created playblast in the system viewer"""
    bl_idname = "playblastplus.open_last"
    bl_label = "Open Last"
    bl_description = "Open the most recently created playblast file"

    def execute(self, context):
        last = context.scene.playblast_plus.last_playblast
        if last and Path(last).is_file():
            prefs = context.preferences.addons[__package__].preferences
            ext = Path(last).suffix.lower()
            if ext in {'.png', '.jpg', '.jpeg', '.exr', '.tiff', '.tif'}:
                player_path = prefs.image_player_path
            else:
                player_path = prefs.media_player_path
            encode.open_media_file(last, player_path=player_path)
        else:
            self.report({'WARNING'}, "PlayblastPlus: no playblast file found.")
        return {'FINISHED'}


class PLAYBLASTPLUS_OT_apply_apng_preset(Operator):
    """Apply the selected APNG preset to the scene resolution and frame rate"""
    bl_idname = "playblastplus.apply_apng_preset"
    bl_label = "Apply to Scene"
    bl_description = "Set scene resolution and frame rate to match the selected APNG preset"

    def execute(self, context):
        from .lib.apng_presets import get_preset
        prefs = context.preferences.addons[__package__].preferences
        preset = get_preset(prefs.apng_preset)
        if not preset:
            self.report({'WARNING'}, "PlayblastPlus: preset not found.")
            return {'CANCELLED'}

        render = context.scene.render
        render.resolution_x = preset["width"]
        render.resolution_y = preset["height"]
        render.resolution_percentage = 100
        context.scene.render.fps = preset.get("framerate", 24)

        label = preset.get("label", preset["name"])
        w, h, fps = preset["width"], preset["height"], preset.get("framerate", 24)
        self.report({'INFO'}, f"PlayblastPlus: applied '{label}' — {w}×{h} @ {fps} fps")
        return {'FINISHED'}


# Module-level registry of active publish processes so the timer can reference them.
_ayon_publish_procs: list = []

# Last publish result — shown in the panel until the next publish starts.
# Keys: "label" (str), "success" (bool), "log_path" (str)
_ayon_last_publish_result: dict = {}

# Cache of (identifier, label) tuples fetched from traypublisher inside Blender.
# Populated by PLAYBLASTPLUS_OT_refresh_ayon_creators.
_ayon_creator_cache: list = []  # list of dicts: {"id": str, "label": str, "family": str}

# Cache of discovered media files per media type (populated by refresh_ayon_media).
# MP4 / IMAGE entries : {"path": str, "label": str}
# SEQUENCE entries    : {"pattern": str, "frame_start": int, "frame_end": int,
#                        "label": str, "frames": list[str], "directory": str}
_ayon_media_cache: dict = {"MP4": [], "SEQUENCE": [], "IMAGE": []}


class PLAYBLASTPLUS_OT_refresh_ayon_creators(Operator):
    """Probe AYON traypublisher creators via subprocess (avoids OTIO crash inside Blender)"""
    bl_idname = "playblastplus.refresh_ayon_creators"
    bl_label = "Refresh Creators"
    bl_description = "Fetch available AYON publish creators (runs outside Blender to avoid crash)"

    def execute(self, context):
        import os as _os
        import json as _json
        import subprocess
        import tempfile
        from pathlib import Path as _Path

        project_name = _os.getenv("AYON_PROJECT_NAME", "")
        if not project_name:
            self.report({'ERROR'}, "PlayblastPlus: AYON_PROJECT_NAME is not set.")
            return {'CANCELLED'}

        ayon_exe = _os.getenv("AYON_EXECUTABLE", "")
        if not ayon_exe or not _Path(ayon_exe).is_file():
            self.report(
                {'ERROR'},
                "PlayblastPlus: AYON_EXECUTABLE not found — launch Blender from the AYON launcher.",
            )
            return {'CANCELLED'}

        script_path = _Path(__file__).parent / "lib" / "ayon_probe_creators.py"
        if not script_path.is_file():
            self.report({'ERROR'}, f"PlayblastPlus: Probe script missing: {script_path}")
            return {'CANCELLED'}

        # Write results to a temp JSON file; subprocess fills it.
        tmp_fh = tempfile.NamedTemporaryFile(
            suffix=".json", delete=False, prefix="pbp_creators_"
        )
        tmp_fh.close()
        output_path = tmp_fh.name

        try:
            result = subprocess.run(
                [ayon_exe, "run", str(script_path), "--",
                 "--output", output_path],
                timeout=30,
                capture_output=True,
                text=True,
            )
        except subprocess.TimeoutExpired:
            self.report({'ERROR'}, "PlayblastPlus: Creator probe timed out (30 s).")
            return {'CANCELLED'}
        except Exception as e:
            self.report({'ERROR'}, f"PlayblastPlus: Creator probe failed: {e}")
            return {'CANCELLED'}

        if result.returncode != 0:
            err = (result.stderr or result.stdout or "").strip()[-300:]
            self.report({'ERROR'}, f"PlayblastPlus: Creator probe exited {result.returncode}: {err}")
            return {'CANCELLED'}

        try:
            with open(output_path, "r", encoding="utf-8") as fh:
                creators = _json.load(fh)
        except Exception as e:
            self.report({'ERROR'}, f"PlayblastPlus: Could not read creator results: {e}")
            return {'CANCELLED'}
        finally:
            try:
                _os.unlink(output_path)
            except Exception:
                pass

        _ayon_creator_cache.clear()
        _ayon_creator_cache.extend(creators)

        # Persist to config.json so they survive Blender restarts.
        try:
            from .lib.ayon_config import save_creators
            save_creators(creators)
        except Exception as _e:
            print(f"[PlayblastPlus] Could not save creators to config: {_e}")

        # If the scene's current creator_id is no longer valid, reset to first entry.
        props = context.scene.playblast_plus
        known_ids = {c["id"] for c in _ayon_creator_cache}
        if props.ayon_creator_id not in known_ids and _ayon_creator_cache:
            props.ayon_creator_id = _ayon_creator_cache[0]["id"]

        self.report(
            {'INFO'},
            f"PlayblastPlus: found {len(_ayon_creator_cache)} AYON creators.",
        )
        return {'FINISHED'}


class PLAYBLASTPLUS_OT_set_ayon_creator(bpy.types.Operator):
    """Select this AYON creator for the review publish"""
    bl_idname = "playblastplus.set_ayon_creator"
    bl_label = "Select Creator"
    bl_description = "Use this AYON creator for the publish"

    creator_id: bpy.props.StringProperty()

    def execute(self, context):
        context.scene.playblast_plus.ayon_creator_id = self.creator_id
        return {'FINISHED'}


class PLAYBLASTPLUS_OT_refresh_ayon_media(Operator):
    """Scan the playblast output directory for publishable media files"""
    bl_idname = "playblastplus.refresh_ayon_media"
    bl_label = "Refresh Media"
    bl_description = "Rescan output directories for MP4, image sequence, and still image files"

    def execute(self, context):
        from .lib.blender_scene import Blender_Scene
        from .lib.media_discovery import discover_mp4, discover_images, discover_sequences

        output_dir = Blender_Scene.get_output_dir()
        _ayon_media_cache["MP4"]      = discover_mp4(output_dir)
        _ayon_media_cache["IMAGE"]    = discover_images(output_dir)
        _ayon_media_cache["SEQUENCE"] = discover_sequences(output_dir)

        props = context.scene.playblast_plus
        entries = _ayon_media_cache.get(props.ayon_media_type, [])
        if entries:
            first = entries[0]
            props.ayon_selected_file = first.get("path") or first.get("pattern", "")
        else:
            props.ayon_selected_file = ""

        total = sum(len(v) for v in _ayon_media_cache.values())
        self.report({'INFO'}, f"PlayblastPlus: found {total} publishable file(s).")
        return {'FINISHED'}


class PLAYBLASTPLUS_OT_set_ayon_media_file(Operator):
    """Select a media file or sequence to publish to AYON"""
    bl_idname = "playblastplus.set_ayon_media_file"
    bl_label = "Select File"
    bl_description = "Use this file or sequence for the AYON publish"

    filepath: bpy.props.StringProperty()

    def execute(self, context):
        context.scene.playblast_plus.ayon_selected_file = self.filepath
        return {'FINISHED'}


def _ayon_publish_poll() -> float | None:
    """Timer callback: poll active AYON publish subprocesses and log their output."""
    import sys as _sys

    def _redraw_all():
        try:
            for window in bpy.context.window_manager.windows:
                for area in window.screen.areas:
                    if area.type == 'VIEW_3D':
                        area.tag_redraw()
        except Exception:
            pass

    still_running = []
    for entry in _ayon_publish_procs:
        proc   = entry["proc"]
        log_fh = entry["log_fh"]
        label  = entry["label"]

        ret = proc.poll()
        if ret is None:
            still_running.append(entry)
        else:
            # Drain any remaining output
            try:
                remainder = proc.stdout.read()
                if remainder:
                    log_fh.write(remainder)
            except Exception:
                pass
            log_fh.flush()
            log_fh.close()
            log_path = entry["log_path"]
            if ret == 0:
                print(f"[PlayblastPlus] AYON publish succeeded: {label}  log → {log_path}")
                # Read the result JSON written by ayon_publish.py.
                pub_info = ""
                import json as _json
                result_path = entry["result_path"]
                try:
                    with open(result_path, "r", encoding="utf-8") as _rf:
                        results = _json.load(_rf)
                    if results:
                        r = results[0]
                        pub_info = f"{r['product_name']}  {r['version_str']}"
                except Exception:
                    pass
                _ayon_last_publish_result.update(
                    {"label": label, "success": True, "log_path": log_path, "pub_info": pub_info}
                )
                if pub_info:
                    print(f"[PlayblastPlus] Published: {pub_info}")
                try:
                    _lbl, _lp, _pi = label, log_path, pub_info
                    def _popup_ok(self, context, _l=_lbl, _lp=_lp, _pi=_pi):
                        col = self.layout.column(align=True)
                        display = _pi if _pi else _l
                        col.label(text=f"Published: {display}", icon='CHECKMARK')
                        col.separator(factor=0.3)
                        col.label(text=_lp, icon='FILE_TEXT')
                    bpy.context.window_manager.popup_menu(
                        _popup_ok, title="AYON Publish Complete", icon='INFO'
                    )
                except Exception:
                    pass
            else:
                print(
                    f"[PlayblastPlus] AYON publish FAILED (exit {ret}): {label}\n"
                    f"  See log: {log_path}"
                )
                _ayon_last_publish_result.update(
                    {"label": label, "success": False, "log_path": log_path}
                )
                # Print the last 40 lines of the log to the Blender console
                try:
                    with open(log_path, "r", encoding="utf-8", errors="replace") as f:
                        lines = f.readlines()
                    tail = lines[-40:] if len(lines) > 40 else lines
                    print("[PlayblastPlus] --- publish log tail ---")
                    print("".join(tail))
                    print("[PlayblastPlus] --- end log ---")
                except Exception as e:
                    print(f"[PlayblastPlus] Could not read log: {e}")
                try:
                    _lbl, _lp = label, log_path
                    def _popup_err(self, context, _l=_lbl, _lp=_lp):
                        col = self.layout.column(align=True)
                        col.label(text=f"Publish FAILED for '{_l}'.", icon='ERROR')
                        col.separator(factor=0.3)
                        col.label(text="See log for details:", icon='FILE_TEXT')
                        col.label(text=_lp)
                    bpy.context.window_manager.popup_menu(
                        _popup_err, title="AYON Publish Failed", icon='ERROR'
                    )
                except Exception:
                    pass
            _redraw_all()

    _ayon_publish_procs[:] = still_running
    # Redraw on every tick while publishing so the "Publishing…" indicator updates
    if still_running:
        _redraw_all()
        return 1.0
    return None


class PLAYBLASTPLUS_OT_ayon_publish(Operator):
    """Publish the last playblast to AYON via TrayPublisher"""
    bl_idname = "playblastplus.ayon_publish"
    bl_label = "Publish to AYON"
    bl_description = "Send the last rendered playblast to AYON for review"

    def execute(self, context):
        import os as _os
        import sys as _sys
        import subprocess
        import datetime
        from pathlib import Path as _Path

        props = context.scene.playblast_plus

        # ── AYON executable ───────────────────────────────────────────────
        ayon_exe = _os.getenv("AYON_EXECUTABLE", "")
        if not ayon_exe:
            self.report(
                {'ERROR'},
                "PlayblastPlus: AYON_EXECUTABLE is not set. "
                "Launch Blender from the AYON launcher.",
            )
            return {'CANCELLED'}
        if not _Path(ayon_exe).is_file():
            self.report(
                {'ERROR'},
                f"PlayblastPlus: AYON_EXECUTABLE path does not exist: {ayon_exe}",
            )
            return {'CANCELLED'}

        # ── AYON context — read from Blender's own env vars ───────────────
        project_name = _os.getenv("AYON_PROJECT_NAME", "")
        folder_path  = _os.getenv("AYON_FOLDER_PATH", "")
        task_name    = _os.getenv("AYON_TASK_NAME", "")

        missing = []
        if not project_name: missing.append("AYON_PROJECT_NAME")
        if not folder_path:  missing.append("AYON_FOLDER_PATH")
        if not task_name:    missing.append("AYON_TASK_NAME")
        if missing:
            self.report(
                {'ERROR'},
                f"PlayblastPlus: Missing AYON context variables: {', '.join(missing)}. "
                "Launch Blender from the AYON launcher with a task context active.",
            )
            return {'CANCELLED'}

        # ── Variant & creator ─────────────────────────────────────────────
        variant = props.ayon_variant.strip()
        if not variant:
            self.report({'ERROR'}, "PlayblastPlus: AYON variant cannot be empty.")
            return {'CANCELLED'}

        creator_id = props.ayon_creator_id.strip()
        if not creator_id:
            self.report(
                {'ERROR'},
                "PlayblastPlus: No product type selected — press Refresh to load creators.",
            )
            return {'CANCELLED'}

        # ── Media selection ───────────────────────────────────────────────
        prefs         = context.preferences.addons[__package__].preferences
        media_type    = props.ayon_media_type
        selected_file = props.ayon_selected_file.strip()

        if not selected_file:
            self.report(
                {'ERROR'},
                "PlayblastPlus: No media file selected — use the refresh button to scan output.",
            )
            return {'CANCELLED'}

        seq_entry = None
        if media_type == 'SEQUENCE':
            for e in _ayon_media_cache.get('SEQUENCE', []):
                if e.get("pattern") == selected_file:
                    seq_entry = e
                    break
            if not seq_entry:
                self.report(
                    {'ERROR'},
                    "PlayblastPlus: Selected sequence not found in cache — refresh media first.",
                )
                return {'CANCELLED'}
            if not prefs.keep_images:
                self.report(
                    {'WARNING'},
                    "PlayblastPlus: 'Keep Images' is disabled — sequence frames may not exist on disk.",
                )
        elif media_type in ('MP4', 'IMAGE'):
            if not _Path(selected_file).is_file():
                self.report(
                    {'ERROR'},
                    f"PlayblastPlus: File not found on disk: {selected_file}",
                )
                return {'CANCELLED'}

        # ── Publish script ────────────────────────────────────────────────
        script_path = _Path(__file__).parent / "lib" / "ayon_publish.py"
        if not script_path.is_file():
            self.report(
                {'ERROR'},
                f"PlayblastPlus: Publish script missing: {script_path}",
            )
            return {'CANCELLED'}

        # ── Label for UI feedback ─────────────────────────────────────────
        if media_type == 'SEQUENCE' and seq_entry:
            pub_label = seq_entry["label"]
        else:
            pub_label = _Path(selected_file).name

        # ── Log file ──────────────────────────────────────────────────────
        import json as _json
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        log_dir  = _Path(__file__).parent / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        # Sanitise task/variant so they are safe in a filename.
        def _safe_slug(s):
            return "".join(c if c.isalnum() or c in "-_" else "_" for c in s)
        slug = f"{_safe_slug(task_name)}_{_safe_slug(variant)}_{ts}"
        log_path    = log_dir / f"ayon_publish_{slug}.log"
        result_path = log_dir / f"ayon_result_{slug}.json"
        log_fh   = open(log_path, "w", encoding="utf-8")
        log_fh.write(
            f"[PlayblastPlus] AYON publish started {ts}\n"
            f"  project    : {project_name}\n"
            f"  folder     : {folder_path}\n"
            f"  task       : {task_name}\n"
            f"  variant    : {variant}\n"
            f"  media_type : {media_type}\n"
            f"  file       : {selected_file}\n\n"
        )
        log_fh.flush()
        print(f"[PlayblastPlus] AYON publish log → {log_path}")

        # ── For sequences, write the already-assembled frame list to JSON ─
        # clique ran inside Blender (media_discovery.py); the publish script
        # just reads this list — no re-discovery needed there.
        frames_json_path = None
        if media_type == 'SEQUENCE':
            frames_json_path = log_dir / f"ayon_frames_{ts}.json"
            with open(frames_json_path, "w", encoding="utf-8") as _jf:
                _json.dump(seq_entry["frames"], _jf)
            log_fh.write(f"  frames     : {len(seq_entry['frames'])} frames → {frames_json_path}\n\n")
            log_fh.flush()

        # ── Launch — pass context explicitly so ayon_console inherits it ──
        if media_type == 'SEQUENCE':
            cmd = [
                ayon_exe, "run", str(script_path), "--",
                "--variant",      variant,
                "--creator",      creator_id,
                "--media-type",   "SEQUENCE",
                "--frames-json",  str(frames_json_path),
                "--result-json",  str(result_path),
            ]
        else:
            cmd = [
                ayon_exe, "run", str(script_path), "--",
                "--filepath",    selected_file,
                "--variant",     variant,
                "--creator",     creator_id,
                "--media-type",  media_type,
                "--result-json", str(result_path),
            ]

        proc = subprocess.Popen(
            cmd,
            stdout=log_fh,
            stderr=subprocess.STDOUT,
        )

        _ayon_publish_procs.append({
            "proc":        proc,
            "log_fh":      log_fh,
            "log_path":    str(log_path),
            "result_path": str(result_path),
            "label":       pub_label,
        })

        if not bpy.app.timers.is_registered(_ayon_publish_poll):
            bpy.app.timers.register(_ayon_publish_poll, first_interval=1.0)

        self.report(
            {'INFO'},
            f"PlayblastPlus: publishing '{pub_label}' [{media_type}] (variant: {variant}) — "
            f"log → {log_path}",
        )
        return {'FINISHED'}


# ---------------------------------------------------------------------------
# FFmpeg installer (modal — download runs in a background thread)
# ---------------------------------------------------------------------------

def _redraw_areas() -> float | None:
    """Timer callback: tag VIEW_3D and PREFERENCES areas for redraw while install runs."""
    try:
        for window in bpy.context.window_manager.windows:
            for area in window.screen.areas:
                if area.type in ('VIEW_3D', 'PREFERENCES'):
                    area.tag_redraw()
    except Exception:
        pass
    return 0.1 if dl_state["running"] else None


class PLAYBLASTPLUS_OT_install_ffmpeg(Operator):
    """Download and install FFmpeg to the add-on's local bin/ folder"""
    bl_idname = "playblastplus.install_ffmpeg"
    bl_label = "Install FFmpeg"
    bl_description = "Download FFmpeg from the internet and install it to the add-on bin/ folder"

    def execute(self, context):
        if dl_state["running"]:
            self.report({'WARNING'}, "FFmpeg install already in progress.")
            return {'CANCELLED'}

        prefs = context.preferences.addons[__package__].preferences
        start_install(url=prefs.download_url)

        if not bpy.app.timers.is_registered(_redraw_areas):
            bpy.app.timers.register(_redraw_areas, first_interval=0.1)

        def _on_complete():
            if dl_state["running"]:
                return 0.25
            if dl_state["done"]:
                installed = find_ffmpeg()
                if installed:
                    try:
                        bpy.context.preferences.addons[__package__].preferences.ffmpeg_path = installed
                    except Exception:
                        pass
            return None

        bpy.app.timers.register(_on_complete, first_interval=0.25)
        return {'FINISHED'}


# ---------------------------------------------------------------------------
# Registration
class PLAYBLASTPLUS_OT_open_preferences(Operator):
    """Open Playblast Plus add-on preferences"""
    bl_idname = "playblastplus.open_preferences"
    bl_label = "Playblast Plus Preferences"
    bl_description = "Open Playblast Plus add-on preferences"

    def execute(self, context):
        bpy.ops.preferences.addon_show(module=__package__)
        return {'FINISHED'}


# ---------------------------------------------------------------------------

_CLASSES = [
    PLAYBLASTPLUS_OT_run,
    PLAYBLASTPLUS_OT_snapshot,
    PLAYBLASTPLUS_OT_insert_token,
    PLAYBLASTPLUS_OT_set_ayon_variant,
    PLAYBLASTPLUS_OT_set_suffix,
    PLAYBLASTPLUS_OT_open_output,
    PLAYBLASTPLUS_OT_open_last,
    PLAYBLASTPLUS_OT_apply_apng_preset,
    PLAYBLASTPLUS_OT_install_ffmpeg,
    PLAYBLASTPLUS_OT_refresh_ayon_creators,
    PLAYBLASTPLUS_OT_set_ayon_creator,
    PLAYBLASTPLUS_OT_refresh_ayon_media,
    PLAYBLASTPLUS_OT_set_ayon_media_file,
    PLAYBLASTPLUS_OT_ayon_publish,
    PLAYBLASTPLUS_OT_open_preferences,
]


def register():
    for cls in _CLASSES:
        bpy.utils.register_class(cls)

    # Pre-populate creator cache from config.json so it survives Blender restarts.
    try:
        from .lib.ayon_config import load_creators
        saved = load_creators()
        if saved:
            _ayon_creator_cache.extend(saved)
    except Exception as exc:
        print(f"[PlayblastPlus] Could not pre-load creators from config: {exc}")


def unregister():
    for cls in reversed(_CLASSES):
        bpy.utils.unregister_class(cls)
