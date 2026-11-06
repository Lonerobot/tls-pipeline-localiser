"""Maya bootstrap stub. Put this folder on PYTHONPATH; Maya runs userSetup.py at startup.

Maya runs userSetup.py via execfile, so there is no __file__ here. It must not assume it runs first or alone.
"""
import importlib.util
import os
import sys
import traceback


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
    from maya import cmds

    _series = str(cmds.about(version=True)).split(".")[0]  # "2026"
    _load_pipeline().start("maya", _series)
except Exception:
    # Never stop Maya starting; report the failure instead.
    traceback.print_exc()
    print("TLS pipeline: failed to localise for maya")
