"""Nuke bootstrap stub. Point NUKE_PATH at this folder; Nuke runs init.py at application start.

Everything important happens here, not in menu.py, which only runs once the UI loads.
"""
import importlib.util
import os
import sys
import traceback

import nuke


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


try:
    _series = f"{nuke.NUKE_VERSION_MAJOR}.{nuke.NUKE_VERSION_MINOR}"  # "17.0"
    _load_pipeline().start("nuke", _series)
except Exception:
    # Never stop Nuke starting; report the failure instead.
    traceback.print_exc()
    print("TLS pipeline: failed to localise for nuke")
