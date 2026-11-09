"""
APNG preset loader.

Presets are defined under the ``apng_presets`` key in ``config.json`` at the
add-on root.  Edit that file to add, remove, or adjust presets.

Each preset entry::

    {
      "name":      str  — unique identifier used as EnumProperty value
      "label":     str  — human-readable name shown in the dropdown
      "width":     int  — render resolution X
      "height":    int  — render resolution Y
      "framerate": int  — scene frame rate
    }

Note: ``apng-presets.json`` is deprecated in favour of ``config.json``.
"""

# Blender requires that EnumProperty items callbacks return a list whose
# strings stay alive (no GC). We keep a module-level cache for this.
_enum_cache: list = []


def load_presets() -> list:
    """Read presets from config.json (apng_presets key). Falls back to built-in defaults."""
    try:
        from .ayon_config import load_apng_presets
        return load_apng_presets()
    except Exception as exc:
        print(f"[PlayblastPlus] Could not load APNG presets from config: {exc}")
        return []


def get_preset(name: str) -> dict | None:
    """Return the preset dict matching *name*, or None."""
    for preset in load_presets():
        if preset.get("name") == name:
            return preset
    return None


def enum_items(_self=None, _context=None) -> list:
    """Dynamic EnumProperty items callback.

    Returns a cached list of (identifier, label, description) tuples.
    Falls back to a single placeholder entry when the file is missing or empty.
    """
    global _enum_cache
    presets = load_presets()
    if not presets:
        _enum_cache = [
            ("NONE", "No presets", "Add presets under apng_presets in config.json"),
        ]
        return _enum_cache

    _enum_cache = [
        (
            p["name"],
            p.get("label", p["name"]),
            f"{p.get('width', '?')}\u00d7{p.get('height', '?')} @ {p.get('framerate', '?')} fps",
        )
        for p in presets
    ]
    return _enum_cache
