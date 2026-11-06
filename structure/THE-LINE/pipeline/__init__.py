# THE-LINE pipeline entry, in the folder TLS_PIPELINE points at.
# Host bootstrap stubs load this file and call start(host, series). Nothing runs at import time.
import importlib.util
import os
import sys


def start(host, series):
    """Load a prepared local bundle, expose it, and run its entry point without syncing."""
    from .localiser import load_prepared_release, expose_environment

    release = load_prepared_release(host, series)
    expose_environment(release)  # sets TLS_PIPELINE_<HOST> to the resolved bundle path
    _run_entry(release)
    return release


def _run_entry(release):
    """Execute <bundle>/<python_root>/__init__.py as a package, so the bundle can use relative imports."""
    entry_dir = str(release.python_root)
    name = "tls_bundle_" + release.host
    spec = importlib.util.spec_from_file_location(
        name, os.path.join(entry_dir, "__init__.py"), submodule_search_locations=[entry_dir]
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
