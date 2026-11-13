"""Nuke bootstrap stub. Point NUKE_PATH at this folder; Nuke runs init.py at application start.

Everything important happens here, not in menu.py, which only runs once the UI loads.
"""
import importlib.util
import os
import sys
import traceback

import nuke


def _pipeline_root():
    """TLS_PIPELINE if set, otherwise the per-user install location (same rule as localiser.config)."""
    root = os.environ.get("TLS_PIPELINE", "").strip()
    if root:
        return root
    if sys.platform.startswith("win"):
        base = os.environ.get("LOCALAPPDATA", "")
        root = os.path.join(base, "TheLine", "pipeline") if base else ""
    elif sys.platform == "darwin":
        root = os.path.join(os.path.expanduser("~"), "Library", "Application Support", "TheLine", "Pipeline")
    else:
        data = os.environ.get("XDG_DATA_HOME") or os.path.join(os.path.expanduser("~"), ".local", "share")
        root = os.path.join(data, "theline", "pipeline")
    if not os.path.isfile(os.path.join(root, "config.json")):
        raise RuntimeError("TLS_PIPELINE is not set and there is no pipeline installed at {!r}".format(root))
    os.environ.setdefault("TLS_PIPELINE", root)
    return root


def _load_pipeline():
    if "tls_pipeline" not in sys.modules:
        root = _pipeline_root()
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
