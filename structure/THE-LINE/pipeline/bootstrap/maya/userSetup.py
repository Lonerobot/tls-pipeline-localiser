"""Maya bootstrap stub. Put this folder on PYTHONPATH; Maya runs userSetup.py at startup.

Maya runs userSetup.py via execfile, so there is no __file__ here. It must not assume it runs first or alone.
"""
import importlib.util
import os
import sys
import traceback


def _pipeline_root():
    """TLS_PIPELINE if set, otherwise the per-user install location (same rule as localiser.config)."""
    root = os.environ.get("TLS_PIPELINE", "").strip()
    if root:
        return root
    if sys.platform.startswith("win"):
        base = os.environ.get("LOCALAPPDATA", "")
        root = os.path.join(base, "TheLine", "Pipeline") if base else ""
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
    from maya import cmds

    _series = str(cmds.about(version=True)).split(".")[0]  # "2026"
    _load_pipeline().start("maya", _series)
except Exception:
    # Never stop Maya starting; report the failure instead.
    traceback.print_exc()
    print("TLS pipeline: failed to localise for maya")
