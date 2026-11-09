"""Utility helpers bundled with the Blender extension.

Subset of playblast_plus.lib.utils — no Qt, no DCC dependencies.
"""

import re
import subprocess
import sys
from pathlib import Path


def extract_version_from_stem(stem: str) -> str:
    """Extract a version string from a file stem.

    Looks for the first occurrence of a ``v``/``V`` prefix followed by 1–4
    digits (e.g. ``v1``, ``v01``, ``v001``, ``V0023``).

    When the stem contains more than 4 digits after the version prefix (e.g.
    ``v00001``), only the first 4 digits are captured — the match stops at the
    4-digit boundary.  Version numbers longer than 4 digits are outside the
    expected range for this tool (VFX filenames rarely exceed ``v9999``).

    Args:
        stem (str): Filename stem (no directory, no extension).

    Returns:
        str: The matched version token (e.g. ``"v001"``), or ``""`` when no
             version pattern is found.
    """
    if not stem:
        return ""
    m = re.search(r'[vV]\d{1,4}', stem)
    return m.group(0) if m else ""


def parse_suffixes(csv: str) -> list[str]:
    """Parse a comma-separated string of predefined suffix values.

    Args:
        csv (str): Comma-separated suffix entries (e.g. ``"None,Chalk,Rig"``).

    Returns:
        list[str]: Non-empty, stripped entries in their original order.
    """
    return [s.strip() for s in csv.split(",") if s.strip()]


class Parsing:

    @staticmethod
    def create_ffmpeg_input(img_start: str) -> str:
        """Convert the path of the first frame in a numeric PNG sequence to an
        ffmpeg ``%0Nd`` pattern string.

        e.g. ``/tmp/shot_0001.png`` → ``/tmp/shot_%04d.png``

        Args:
            img_start (str): Path to the first frame of the sequence.

        Returns:
            str: ffmpeg-compatible input path, or None if no numeric run found.
        """
        if not img_start:
            return None
        img_start = Path(img_start)
        file_name = img_start.name
        # Anchor to end: match the frame-number digits immediately before .png
        # This avoids mis-matching Blender's object version suffixes (.001, .002)
        m = re.search(r"(\d+)\.png$", file_name, re.IGNORECASE)
        if m:
            digits = m.group(1)
            pad_len = len(digits)
            ffmpeg_input = file_name[:m.start(1)] + f"%0{pad_len}d" + ".png"
            return str(img_start.parent / ffmpeg_input)
        return None


class FolderOps:

    @staticmethod
    def explore(dir: str) -> None:
        """Open *dir* in the OS file explorer."""
        if sys.platform == "win32":
            subprocess.Popen(f'explorer "{dir}"')
        elif sys.platform == "darwin":
            subprocess.Popen(["open", dir])
        else:
            subprocess.Popen(["xdg-open", dir])

    @staticmethod
    def purge_contents(root: str, ext: str = ".*", skip_folder: str = "") -> None:
        """Delete files in *root* that match *ext*.

        Args:
            root (str): Directory to clean.
            ext (str): File extension to target, e.g. ``'.png'``. Defaults to
                       all files (``'.*'``).
            skip_folder (str): Name of an immediate subfolder to leave
                               untouched.
        """
        for f in Path(root).rglob(f"*{ext}"):
            try:
                if f.parent.name != skip_folder:
                    f.unlink()
            except OSError as e:
                print(f"[PlayblastPlus] error removing {f}: {e.strerror}")
