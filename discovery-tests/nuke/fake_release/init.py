"""Fake localised release's init.py — logs its own execution so we can confirm, relative to
stub/init.py's log lines, whether nuke.pluginAddPath() causes this to run in the same startup
pass (see .copilot/03_user_discovery.md G2). THROWAWAY TEST CODE."""
import os
import tempfile
import time

LOG_PATH = os.environ.get("TLS_DISCOVERY_LOG") or os.path.join(
    tempfile.gettempdir(), "tls_discovery.log"
)


def _log(event):
    line = "[{ts}] HOST=nuke FILE={file} PID={pid} EVENT={event}".format(
        ts=time.strftime("%Y-%m-%dT%H:%M:%S"),
        file=__file__,
        pid=os.getpid(),
        event=event,
    )
    print(line)
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except OSError:
        pass


_log("fake_release_init_ran")
