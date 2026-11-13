"""Media file discovery for Playblast Plus AYON publish panel.

Discovers publishable media from the playblast output directory:

* MP4 files  — ``<output_dir>/*.mp4``
* Still PNGs — ``<output_dir>/captures/*.png``
* Sequences  — ``<output_dir>/frames/**/*.png`` grouped into frame sequences

Sequence grouping tries ``clique`` first (available when Blender is launched
via AYON, since AYON adds its dependency package to ``sys.path``).  Falls back
to a regex-based grouper if clique is not importable.
"""

import re
from pathlib import Path


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _assemble_with_clique(files: list) -> list | None:
    """Group *files* into sequences using clique.

    Returns a list of sequence dicts, or ``None`` if clique is not available.
    """
    try:
        import clique
    except ImportError:
        return None

    collections, _remainder = clique.assemble([str(f) for f in files])

    result = []
    for col in collections:
        indexes = sorted(col.indexes)
        if not indexes:
            continue
        frames = [
            f"{col.head}{str(idx).zfill(col.padding)}{col.tail}"
            for idx in indexes
        ]
        pattern = f"{col.head}{'#' * col.padding}{col.tail}"
        result.append({
            "pattern":     pattern,
            "frame_start": indexes[0],
            "frame_end":   indexes[-1],
            "label":       Path(pattern).name,
            "frames":      frames,
            "directory":   str(Path(frames[0]).parent),
        })
    return result


def _assemble_with_regex(files: list) -> list:
    """Group files into sequences using a trailing-digit regex (fallback)."""
    _NUM_RE = re.compile(r'^(.*?)(\d+)(\.[^.]+)$')

    groups: dict = {}
    for f in files:
        name = Path(f).name
        m = _NUM_RE.match(name)
        if m:
            prefix, num_str, ext = m.groups()
            padding = len(num_str)
            key = (str(Path(f).parent), prefix, ext, padding)
            groups.setdefault(key, []).append((int(num_str), str(f)))

    result = []
    for (directory, prefix, ext, padding), frame_list in groups.items():
        if len(frame_list) < 2:
            continue  # skip singletons
        frame_list.sort()
        frame_nums  = [n for n, _ in frame_list]
        frame_paths = [p for _, p in frame_list]
        pattern = f"{prefix}{'#' * padding}{ext}"
        result.append({
            "pattern":     str(Path(directory) / pattern),
            "frame_start": frame_nums[0],
            "frame_end":   frame_nums[-1],
            "label":       pattern,
            "frames":      frame_paths,
            "directory":   directory,
        })
    return result


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def discover_mp4(output_dir: str) -> list:
    """Return ``[{"path": str, "label": str}, ...]`` for ``*.mp4`` in *output_dir*."""
    root = Path(output_dir)
    if not root.is_dir():
        return []
    return [{"path": str(f), "label": f.name} for f in sorted(root.glob("*.mp4"))]


def discover_images(output_dir: str) -> list:
    """Return ``[{"path": str, "label": str}, ...]`` for PNGs in ``captures/``."""
    captures_dir = Path(output_dir) / "captures"
    if not captures_dir.is_dir():
        return []
    return [
        {"path": str(f), "label": f.name}
        for f in sorted(captures_dir.glob("*.png"))
    ]


def discover_sequences(output_dir: str) -> list:
    """Return grouped sequences from ``frames/**/*.png``.

    Each entry::

        {
            "pattern":     str,   # e.g. "/…/shot_####.png"
            "frame_start": int,
            "frame_end":   int,
            "label":       str,   # filename pattern only
            "frames":      list,  # absolute paths
            "directory":   str,
        }
    """
    frames_dir = Path(output_dir) / "frames"
    if not frames_dir.is_dir():
        return []

    all_files = sorted(str(f) for f in frames_dir.rglob("*.png"))
    if not all_files:
        return []

    result = _assemble_with_clique(all_files)
    if result is None:
        result = _assemble_with_regex(all_files)
    return result
