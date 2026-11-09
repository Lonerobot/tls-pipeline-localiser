"""
#   _____ _  _ ___   _     ___ _  _ ___
#  |_   _| || | __| | |   |_ _| \| | __|
# _______________________________________
#    | | | || |___| |____|___|_|\_|___|
                                                
#    ___ _____ _   _ ___ ___ ___  
#   / __|_   _| | | |   \_ _/ _ \
#   \__ \ | | | |_| | |) | | (_) |
#   |___/ |_|  \___/|___/___\___/
                                                

Playblast Plus — Blender Extension

Self-contained viewport playblast capture and FFmpeg encode tool.

Install
-------
Zip the contents of this folder and install via
Edit > Preferences > Extensions > Install from Disk (Blender 4.2+).

Build the zip from the repo root::

    blender --command extension build --source-dir addons/playblast_blender --output-dir dist

Then install ``dist/playblast_plus-x.x.x.zip`` through the Blender UI.
"""

bl_info = {
    "name": "Playblast Plus",
    "description": "Viewport playblast capture with FFmpeg encoding",
    "blender": (4, 0, 0),
    "category": "Render",
    "author": "Playblast Plus Contributors",
    "version": (1, 6, 11),
    "location": "View3D > Sidebar > PBP",
    "doc_url": "",
    "warning": "",
    "support": "COMMUNITY",
}


from . import preferences, props, operators, ui
from .lib import register_tokens
from .lib.custom_icons import icons as custom_icons

_MODULES = [preferences, props, operators, ui]


def register():
    custom_icons.register()
    for mod in _MODULES:
        mod.register()


def unregister():
    for mod in reversed(_MODULES):
        mod.unregister()
    custom_icons.unregister()
