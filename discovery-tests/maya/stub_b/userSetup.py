"""Discovery test stub B for Maya userSetup.py resolution (see .copilot/03_user_discovery.md
G3 / M3). THROWAWAY TEST CODE — not part of the localiser design.

Represents a second, separately-sourced userSetup.py (e.g. an AYON-provided one). Deploy by
adding this file's directory to PYTHONPATH alongside (but at a different sys.path position
than) stub_a's directory, then launch Maya.
"""
import os
import sys
import tempfile
import time

LOG_PATH = os.environ.get("TLS_DISCOVERY_LOG") or os.path.join(
    tempfile.gettempdir(), "tls_discovery.log"
)
# Maya runs userSetup.py via execfile, which does not define __file__.
_THIS_FILE = globals().get("__file__", "<no __file__ under Maya execfile>")


def _log(event, **fields):
    extra = " ".join("{}={}".format(k, v) for k, v in fields.items())
    line = "[{ts}] HOST=maya STUB=B FILE={file} PID={pid} EVENT={event} {extra}".format(
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
    sys_path_len=len(sys.path),
)
_log("userSetup_end")
