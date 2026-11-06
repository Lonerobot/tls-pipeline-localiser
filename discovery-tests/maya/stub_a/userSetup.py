"""Discovery test stub A for Maya userSetup.py resolution (see .copilot/03_user_discovery.md
G3 / M1 / M3). THROWAWAY TEST CODE — not part of the localiser design.

Deploy by adding this file's directory to PYTHONPATH (simulating the localiser's own stub
location) alongside stub_b's directory (simulating a second, separately-sourced userSetup.py,
e.g. AYON-provided). Launch Maya and inspect the log file this writes to.
"""
import builtins
import os
import tempfile
import time

LOG_PATH = os.environ.get("TLS_DISCOVERY_LOG") or os.path.join(
    tempfile.gettempdir(), "tls_discovery.log"
)
# Maya runs userSetup.py via execfile, which does not define __file__.
_THIS_FILE = globals().get("__file__", "<no __file__ under Maya execfile>")

# Module names we want to know the import time of, relative to this userSetup.py running.
# Extend this tuple if your studio's pipeline entry point has a different name.
_WATCH_NAMES = ("mayaScriptLibrary", "corescripts_template")


def _log(event, **fields):
    extra = " ".join("{}={}".format(k, v) for k, v in fields.items())
    line = "[{ts}] HOST=maya STUB=A FILE={file} PID={pid} EVENT={event} {extra}".format(
        ts=time.strftime("%Y-%m-%dT%H:%M:%S"),
        file=_THIS_FILE,
        pid=os.getpid(),
        event=event,
        extra=extra,
    )
    print(line)
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except OSError:
        pass


_log(
    "userSetup_start",
    MAYA_CORE=os.environ.get("MAYA_CORE", "<unset>"),
    sys_path_len=len(__import__("sys").path),
)

# --- M1 instrumentation: temporarily wrap builtins.__import__ to log the first import of
# anything matching _WATCH_NAMES, then restore the original on userSetup_end. This only tells
# us *when* an import happens relative to this script, not who triggered it.
_original_import = builtins.__import__
_seen = set()


def _watching_import(name, *args, **kwargs):
    if name not in _seen and any(watch in name for watch in _WATCH_NAMES):
        _seen.add(name)
        _log("import_observed", module=name)
    return _original_import(name, *args, **kwargs)


builtins.__import__ = _watching_import

try:
    pass  # Nothing else to do here for the discovery test itself.
finally:
    _log("userSetup_end")
    # Leave the import watcher installed for the rest of the session so later lazy imports
    # (e.g. a menu command clicked after startup) are still logged. Remove this file's
    # PYTHONPATH entry once the test is done to stop watching.
