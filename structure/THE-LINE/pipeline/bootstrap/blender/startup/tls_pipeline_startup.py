"""Blender bootstrap stub. Set BLENDER_SYSTEM_SCRIPTS to the folder containing startup/ (bootstrap/blender).

Blender calls register() during startup, before saved add-ons load, so localising must happen here
synchronously, not from a timer. Blender also swallows exceptions raised from register(), so failures
are printed here.
"""
import importlib.util
import os
import sys
import traceback

import bpy


def _load_pipeline():
    if "tls_pipeline" not in sys.modules:
        root = os.environ["TLS_PIPELINE"]
        spec = importlib.util.spec_from_file_location(
            "tls_pipeline", os.path.join(root, "__init__.py"), submodule_search_locations=[root]
        )
        module = importlib.util.module_from_spec(spec)
        sys.modules["tls_pipeline"] = module
        spec.loader.exec_module(module)
    return sys.modules["tls_pipeline"]


def register():
    try:
        series = "{}.{}".format(*bpy.app.version[:2])  # "5.2"
        _load_pipeline().start("blender", series)
    except Exception:
        traceback.print_exc()
        print("TLS pipeline: failed to localise for blender")


def unregister():
    pass
