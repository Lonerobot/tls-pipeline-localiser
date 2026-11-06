"""Discovery test stub for Nuke NUKE_PATH / pluginAddPath ordering (see
.copilot/03_user_discovery.md G2 / N3). THROWAWAY TEST CODE — not part of the localiser design.

Deploy: point NUKE_PATH at this file's directory (stub/), not at fake_release/. Launch Nuke and
inspect the log file this writes to.
"""
import os
import tempfile
import time

import nuke  # Nuke's embedded Python module; only importable when run inside Nuke.

LOG_PATH = os.environ.get("TLS_DISCOVERY_LOG") or os.path.join(
    tempfile.gettempdir(), "tls_discovery.log"
)


def _log(event, **fields):
    extra = " ".join("{}={}".format(k, v) for k, v in fields.items())
    line = "[{ts}] HOST=nuke FILE={file} PID={pid} EVENT={event} {extra}".format(
        ts=time.strftime("%Y-%m-%dT%H:%M:%S"),
        file=__file__,
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


_log("stub_init_start")

_fake_release = os.environ.get("TLS_DISCOVERY_NUKE_FAKE_RELEASE") or os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "fake_release"
)
_fake_release = os.path.normpath(_fake_release)

_log("plugin_add_path_call", target=_fake_release)
# Guard against a stale or wrong override (e.g. a variable left over from another host's test).
_log(
    "target_check",
    exists=os.path.isdir(_fake_release),
    has_init=os.path.isfile(os.path.join(_fake_release, "init.py")),
    has_menu=os.path.isfile(os.path.join(_fake_release, "menu.py")),
)
nuke.pluginAddPath(_fake_release)

_log("stub_init_end")
