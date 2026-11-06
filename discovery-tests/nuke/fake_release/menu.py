"""Fake localised release's menu.py — logs its own execution time so we can confirm it runs
only when the UI loads, later than init.py (see .copilot/03_user_discovery.md G2 / N3).
THROWAWAY TEST CODE."""
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


_log("fake_release_menu_ran")
