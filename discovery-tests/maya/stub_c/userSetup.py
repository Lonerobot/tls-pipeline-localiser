"""Discovery test stub C for Maya userSetup.py resolution (see .copilot/03_user_discovery.md
G3 / M2 / M3). THROWAWAY TEST CODE — not part of the localiser design.

Deploy by copying this file into Maya's version-specific user scripts folder, which Maya puts
on sys.path by default:

    <Documents>\\maya\\<version>\\scripts\\userSetup.py     (e.g. ...\\maya\\2026\\scripts)

Confirm the exact folder in Maya's Python tab with
`import maya.cmds as cmds; print(cmds.internalVar(userScriptDir=True))`. The shared
<Documents>\\maya\\scripts folder may already hold a real userSetup.py: NEVER overwrite an
existing userSetup.py. Back it up, or use a folder that has none (a PYTHONPATH entry to this
stub_c directory is the non-destructive alternative). Remove the copy afterwards.

Maya runs userSetup.py via execfile, which does not define __file__, so the log's FILE field
is a placeholder; use the userSetup_candidate events to see which file(s) could have run.
Launch Maya (vanilla and/or via AYON, optionally with stub_a/stub_b also on PYTHONPATH) and
inspect the log this writes to.
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
    line = "[{ts}] HOST=maya STUB=C FILE={file} PID={pid} EVENT={event} {extra}".format(
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


def _user_script_dir():
    try:
        import maya.cmds as cmds

        return cmds.internalVar(userScriptDir=True)
    except Exception as exc:
        return "<unavailable: {!r}>".format(exc)


_log(
    "userSetup_start",
    MAYA_CORE=os.environ.get("MAYA_CORE", "<unset>"),
    user_script_dir=_user_script_dir(),
    sys_path_len=len(sys.path),
)
# One entry per line-event so the order Maya built sys.path in (G3 precedence) is unambiguous.
for _index, _entry in enumerate(sys.path):
    _log("sys_path_entry", index=_index, path=_entry)
# Without __file__, record which sys.path folders hold a userSetup.py (G3: which one ran).
for _entry in sys.path:
    if os.path.isfile(os.path.join(_entry, "userSetup.py")):
        _log("userSetup_candidate", path=os.path.join(_entry, "userSetup.py"))

_log("userSetup_end")
