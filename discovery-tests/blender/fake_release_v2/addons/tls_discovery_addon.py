"""Fake pipeline add-on (v2) used by the Blender discovery test — same module name as v1, in a
different folder, used to test the B2 stale-path / re-point scenario: does refreshing the
script-directory entry's `directory` pick up this file instead of v1's, in the same session,
without creating a duplicate entry? See .copilot/03_user_discovery.md B2. THROWAWAY TEST CODE.
"""

bl_info = {
    "name": "TLS Discovery Test Addon",
    "author": "tls-pipeline-localiser discovery test",
    "version": (2, 0, 0),
    "blender": (5, 0, 0),
    "location": "N/A",
    "description": "Marker add-on only used to test in-session script-directory discovery.",
    "category": "Testing",
}

import os
import tempfile
import time


def _log(event):
    log_path = os.environ.get("TLS_DISCOVERY_LOG") or os.path.join(
        tempfile.gettempdir(), "tls_discovery.log"
    )
    line = "[{ts}] HOST=blender FILE={file} PID={pid} EVENT={event}".format(
        ts=time.strftime("%Y-%m-%dT%H:%M:%S"), file=__file__, pid=os.getpid(), event=event
    )
    print(line)
    try:
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except OSError:
        pass


def register():
    _log("fake_addon_register_v2")


def unregister():
    _log("fake_addon_unregister_v2")
