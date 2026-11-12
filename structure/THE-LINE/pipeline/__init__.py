# THE-LINE pipeline entry, in the folder TLS_PIPELINE points at.
# Host bootstrap stubs load this file and call start(host, series). Nothing runs at import time.
import importlib.util
import os
import sys


def start(host, series):
    """Load the bundle this session should use (local files only), expose it, and run its entry point.

    Returns None, loading nothing, when this host and series isn't enabled in the local config."""
    from .localiser import load_prepared_release, expose_environment, host_enabled

    if not host_enabled(host, series):
        print("TLS pipeline: {} {} is not enabled in the local config; not loading".format(host, series))
        return None
    release = load_prepared_release(host, series)
    _announce(release)
    expose_environment(release)  # sets TLS_PIPELINE_<HOST> (bundle path), _RELEASE and _MODE for this session
    for folder in release.extra_paths:  # a dev source's shared packages, imported from where they are
        if folder not in sys.path:
            sys.path.append(folder)
    _run_entry(release)
    return release


def _announce(release):
    """Say so loudly when a session isn't running the selected, published release."""
    if release.source == "dev":
        source = os.environ.get("TLS_PIPELINE_{}_SOURCE".format(release.host.upper()), "")
        print("TLS pipeline: RUNNING UNPUBLISHED SOURCE for {}: {}".format(release.host, source))
    elif release.source == "pinned":
        print("TLS pipeline: PINNED {} bundle {} (not the selected default)".format(release.host, release.release_id))


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
