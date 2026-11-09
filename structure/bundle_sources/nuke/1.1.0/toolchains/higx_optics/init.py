# Version selector for the Higx Nuke plugins. Installed as
# ~/.nuke/higx/optics/init.py (the build installs it, the Linux tarball ships
# it); do not edit the installed copy, edit the source in nuke/.
#
# Layout (~/.nuke/higx is the Higx brand folder, shared with other Higx
# products; this product owns only optics/ inside it):
#   ~/.nuke/init.py                     <- the user's own file:
#                                          nuke.pluginAddPath('./higx/optics')
#   ~/.nuke/higx/optics/init.py         <- THIS FILE, picks the version folder
#   ~/.nuke/higx/optics/menu.py         <- GUI helpers, shared by every version
#   ~/.nuke/higx/optics/Nuke17.1/       <- the plugin binaries (.dll / .so) + tcl stubs
#   ~/.nuke/higx/optics/Nuke17.0/       <- ... one folder per Nuke major.minor
#
# The plugin binaries are built against each Nuke's own NDK, so only the
# folder matching the running Nuke goes on the plugin path.
import os
import nuke

_here = os.path.dirname(os.path.abspath(__file__))
_ver = "Nuke%d.%d" % (nuke.NUKE_VERSION_MAJOR, nuke.NUKE_VERSION_MINOR)
_path = os.path.join(_here, _ver)
if os.path.isdir(_path):
    nuke.pluginAddPath(_path)
else:
    print("[higx] no Higx plugin build for %s in %s" % (_ver, _here))
