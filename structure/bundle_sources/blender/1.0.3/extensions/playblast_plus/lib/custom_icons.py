"""Custom icon manager for Playblast Plus.

Loads PNG icons from assets/icons/ and exposes them as integer icon_ids
for use in Blender layouts.
"""

from pathlib import Path


class icons:
    """Custom icon IDs — set during register()."""
    _icons_ = None

    ayon = 0

    @classmethod
    def register(cls):
        from bpy.utils import previews

        if cls._icons_:
            cls.unregister()
        cls._icons_ = previews.new()

        # custom_icons.py lives in lib/; icons are one level up at assets/icons/
        icons_dir = Path(__file__).parent.parent / "assets" / "icons"
        for attr in [a for a in vars(cls) if not a.startswith('_')]:
            if not isinstance(getattr(cls, attr), int):
                continue
            icon_path = icons_dir / f"{attr}.png"
            if not icon_path.exists():
                continue
            try:
                icon = cls._icons_.load(attr, str(icon_path), 'IMAGE')
                _ = icon.icon_pixels[0]  # force load (Blender quirk)
                setattr(cls, attr, icon.icon_id)
            except Exception as e:
                print(f"[PlayblastPlus] Failed to load icon '{attr}': {e}")

    @classmethod
    def unregister(cls):
        if cls._icons_:
            from bpy.utils import previews
            previews.remove(cls._icons_)
            cls._icons_ = None
            cls.ayon = 0


def get_icon_id(name: str) -> dict:
    """Return a dict suitable for **-unpacking into layout calls.

    Returns ``{"icon_value": id}`` when a custom icon exists,
    falls back to ``{"icon": "NONE"}`` so calls never raise.
    """
    val = getattr(icons, name, 0)
    if val:
        return {"icon_value": val}
    return {"icon": "NONE"}
