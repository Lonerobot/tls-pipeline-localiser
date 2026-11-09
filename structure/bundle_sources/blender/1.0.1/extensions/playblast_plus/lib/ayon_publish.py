"""
Standalone AYON playblast publisher.

Reads project/folder/task context from AYON environment variables (set by the
AYON launcher).  Accepts a filepath via CLI or direct instantiation.

Usage (from an AYON-launched terminal, with AYON env vars set):
    # MP4 / still image
    python ayon_publish.py --filepath "P:/path/to/playblast.mp4" --media-type MP4
    # Image sequence
    python ayon_publish.py --media-type SEQUENCE --sequence-dir "P:/frames" \\
        --frame-start 1001 --frame-end 1120
"""

import os
import argparse
import sys


class AyonPlayblastPublisher:
    """Publish a playblast file or image sequence to AYON via TrayPublisher."""

    def __init__(
        self,
        filepath: str = None,
        variant: str = "Main",
        project_name: str = None,
        folder_path: str = None,
        task_name: str = None,
        creator_id: str = "settings_review",
        media_type: str = "MP4",
        frames_json: str = None,
        result_json: str = None,
    ) -> None:
        self.filepath    = filepath
        self.variant     = variant
        self.creator_id  = creator_id or "settings_review"
        self.media_type  = media_type.upper()
        self.frames_json = frames_json  # path to JSON list of frame paths (SEQUENCE mode)
        self.result_json = result_json  # path to write publish result JSON (product + version)

        # Prefer explicitly passed args; fall back to environment variables.
        # Explicit args are required when called from the Blender operator
        # because ayon_console.exe does not inherit Blender's env vars.
        self.project_name = project_name or os.getenv("AYON_PROJECT_NAME")
        self.folder_path  = folder_path  or os.getenv("AYON_FOLDER_PATH")
        self.task_name    = task_name    or os.getenv("AYON_TASK_NAME")

    def _validate(self):
        missing = []
        if not self.project_name:
            missing.append("project_name (AYON_PROJECT_NAME)")
        if not self.folder_path:
            missing.append("folder_path (AYON_FOLDER_PATH)")
        if not self.task_name:
            missing.append("task_name (AYON_TASK_NAME)")
        if missing:
            raise EnvironmentError(
                f"Missing required AYON context: {missing}\n"
                "Pass as CLI args (--project / --folder-path / --task) or "
                "ensure Blender was launched via the AYON launcher."
            )

        if self.media_type == "SEQUENCE":
            if not self.frames_json or not os.path.isfile(self.frames_json):
                raise FileNotFoundError(
                    f"Frames JSON not found: {self.frames_json}"
                )
        else:
            if not self.filepath or not os.path.isfile(self.filepath):
                raise FileNotFoundError(
                    f"Filepath does not exist: {self.filepath}"
                )

    def _load_sequence_frames(self) -> list:
        """Read the frame list written by the Blender operator."""
        import json
        with open(self.frames_json, "r", encoding="utf-8") as fh:
            frames = json.load(fh)
        if not frames:
            raise RuntimeError(f"Frames JSON is empty: {self.frames_json}")
        return frames

    def publish(self):
        self._validate()

        print(f"[ayon_publish] Project    : {self.project_name}")
        print(f"[ayon_publish] Folder     : {self.folder_path}")
        print(f"[ayon_publish] Task       : {self.task_name}")
        print(f"[ayon_publish] Variant    : {self.variant}")
        print(f"[ayon_publish] Media type : {self.media_type}")
        if self.media_type == "SEQUENCE":
            print(f"[ayon_publish] Frames JSON: {self.frames_json}")
        else:
            print(f"[ayon_publish] Filepath   : {self.filepath}")

        import ayon_api
        from ayon_core.lib.attribute_definitions import FileDefItem
        from ayon_core.pipeline import install_host
        from ayon_core.pipeline.create import CreateContext
        from ayon_traypublisher.api import TrayPublisherHost
        import pyblish.api
        from pyblish.util import publish

        folder_entity = ayon_api.get_folder_by_path(self.project_name, self.folder_path)
        if not folder_entity:
            raise RuntimeError(
                f"Folder '{self.folder_path}' not found in project '{self.project_name}'"
            )

        task_entity = ayon_api.get_task_by_name(
            self.project_name, folder_entity["id"], self.task_name
        )
        if not task_entity:
            raise RuntimeError(
                f"Task '{self.task_name}' not found on folder '{self.folder_path}'"
            )

        # Build FileDefItem(s) depending on media type.
        # Frame list for sequences was assembled by clique inside Blender and
        # written to a JSON file — no re-discovery needed here.
        if self.media_type == "SEQUENCE":
            frame_paths = self._load_sequence_frames()
            print(f"[ayon_publish] Frames loaded: {len(frame_paths)}")
            file_items = FileDefItem.from_paths(frame_paths, allow_sequences=True)
        else:
            file_items = FileDefItem.from_paths([self.filepath], allow_sequences=False)

        file_item_dict = file_items[0].to_dict()
        print(f"[ayon_publish] file_item_dict: {file_item_dict}")

        # All creators (including settings_review) expect representation_files as a list.
        # Passing a bare dict is silently discarded by AYON, leaving the default [].
        pre_create_data = {
            "representation_files": [file_item_dict],
            "reviewable": file_item_dict,
        }

        host = TrayPublisherHost()
        host.set_project_name(self.project_name)
        # Set the current context so anatomy templates and path resolution use
        # the correct folder/task (env vars alone may be stale after a task switch).
        host.set_current_context(folder_entity, task_entity)
        install_host(host)

        create_context = CreateContext(host, headless=True)

        # Validate creator is available.
        available_creators = list(create_context.creators.keys())
        print(f"[ayon_publish] Available creators: {available_creators}")
        if self.creator_id not in available_creators:
            raise RuntimeError(
                f"Creator '{self.creator_id}' was not found in the AYON create context.\n"
                f"Available creators: {available_creators}\n"
                "Use 'Refresh' in the Blender panel to pick a valid one."
            )

        create_context.create(
            self.creator_id,
            self.variant,
            folder_entity,
            task_entity,
            pre_create_data,
        )

        create_context.save_changes()

        publish_context = pyblish.api.Context()
        publish_context.data["create_context"] = create_context
        publish(publish_context, create_context.publish_plugins)

        # Check whether all instances published without errors.
        failed_instances = [
            inst for inst in publish_context
            if inst.data.get("publish") is not False
            and any(r.error for r in getattr(inst, "data", {}).get("results", []) or [])
        ]
        # pyblish stores errors on the context too; check both.
        has_errors = bool(publish_context.data.get("errorCount", 0)) or bool(failed_instances)

        # Report the published product name and version.
        import json as _json
        results = []
        for instance in publish_context:
            product_name = (
                instance.data.get("productName")
                or instance.data.get("subset")
                or instance.name
                or ""
            )
            version = instance.data.get("version")
            if product_name and not has_errors:
                v_str = f"v{version:03d}" if isinstance(version, int) else str(version or "?")
                print(f"[ayon_publish] PUBLISHED: {product_name}  {v_str}")
                results.append({"product_name": product_name, "version": version, "version_str": v_str})
            elif product_name and has_errors:
                print(f"[ayon_publish] PUBLISH ERRORS detected for: {product_name} — result JSON not written.")

        # Write result JSON so the Blender operator can surface it without log parsing.
        # Only written when there are no publish errors so the operator never shows a false positive.
        if self.result_json and results and not has_errors:
            try:
                with open(self.result_json, "w", encoding="utf-8") as _rf:
                    _json.dump(results, _rf)
            except Exception as _e:
                print(f"[ayon_publish] WARNING: could not write result JSON: {_e}")

        print("[ayon_publish] Publish complete.")

        if has_errors:
            raise RuntimeError(
                "One or more publish operations failed. Check the log for details."
            )


def main():
    parser = argparse.ArgumentParser(
        description="Publish a playblast file or image sequence to AYON via TrayPublisher."
    )
    parser.add_argument(
        "--filepath",
        default=None,
        help="Absolute path to the MP4 or PNG (required for MP4 / IMAGE modes).",
    )
    # Context args — ayon_console consumes flags like --project, --task, --folder-path
    # as its own CLI args even after '--', so we read them from env vars instead.
    # (The AYON launcher sets these before spawning Blender; the subprocess inherits them.)
    parser.add_argument("--variant",     default="Main", help="AYON product variant (default: Main).")
    parser.add_argument("--creator",     default="settings_review", help="AYON creator identifier.")
    parser.add_argument(
        "--media-type",
        default="MP4",
        dest="media_type",
        choices=["MP4", "IMAGE", "SEQUENCE"],
        help="Media type being published (default: MP4).",
    )
    # Sequence-specific args
    parser.add_argument(
        "--frames-json",
        default=None,
        dest="frames_json",
        help="Path to JSON file containing the ordered list of frame paths (SEQUENCE mode only).",
    )
    parser.add_argument(
        "--result-json",
        default=None,
        dest="result_json",
        help="Path to write publish result JSON (product name + version) for the caller.",
    )
    # ayon_console strips/consumes flags before the script sees them;
    # remove any bare '--' separators it injects into sys.argv.
    argv = [a for a in sys.argv[1:] if a != "--"]
    args = parser.parse_args(argv)

    # Context from env vars (set by the AYON launcher, inherited by the subprocess).
    project_name = os.environ.get("AYON_PROJECT_NAME") or ""
    folder_path  = os.environ.get("AYON_FOLDER_PATH")  or ""
    task_name    = os.environ.get("AYON_TASK_NAME")    or ""

    missing = [k for k, v in [
        ("AYON_PROJECT_NAME", project_name),
        ("AYON_FOLDER_PATH",  folder_path),
        ("AYON_TASK_NAME",    task_name),
    ] if not v]
    if missing:
        print(f"[ayon_publish] ERROR: missing env vars: {missing}", file=sys.stderr)
        sys.exit(1)

    AyonPlayblastPublisher(
        filepath=args.filepath,
        variant=args.variant,
        project_name=project_name,
        folder_path=folder_path,
        task_name=task_name,
        creator_id=args.creator,
        media_type=args.media_type,
        frames_json=args.frames_json,
        result_json=args.result_json,
    ).publish()


if __name__ == "__main__":
    main()
