# THE-LINE pipeline: what is this DCC session running? Answers from the environment the pipeline entry set at
# startup (TLS_PIPELINE_<HOST>_RELEASE, _MODE and the bundle path), so it needs no access to the localiser or
# the network. Stdlib only; the host menus call text() and show the result in their own dialog.
import os

TITLE = "THE LINE pipeline"
MODES = {
    "studio": "studio default",
    "pinned": "pinned (not the studio default)",
    "dev": "unpublished source (development)",
}


def identity(host, environ=None):
    """{'host', 'release', 'mode', 'path', 'root'} for this session, or None if no bundle was loaded."""
    environ = os.environ if environ is None else environ
    prefix = "TLS_PIPELINE_" + host.upper()
    release = environ.get(prefix + "_RELEASE", "").strip()
    if not release:
        return None
    return {
        "host": host,
        "release": release,
        "mode": environ.get(prefix + "_MODE", "").strip() or "studio",
        "path": environ.get(prefix, "").strip(),
        "root": environ.get("TLS_PIPELINE", "").strip(),
    }


def text(host, environ=None):
    """A short, plain-text About message for a dialog."""
    info = identity(host, environ)
    if info is None:
        return "{}\n\nNo pipeline bundle is loaded in this session.\nIs {} enabled in the pipeline manager?".format(
            TITLE, host.capitalize()
        )
    lines = [
        TITLE,
        "",
        "Release:  " + info["release"],
        "Source:   " + MODES.get(info["mode"], info["mode"]),
    ]
    if info["path"]:
        lines.append("Bundle:   " + info["path"])
    if info["root"]:
        lines.append("Pipeline: " + info["root"])
    return "\n".join(lines)
