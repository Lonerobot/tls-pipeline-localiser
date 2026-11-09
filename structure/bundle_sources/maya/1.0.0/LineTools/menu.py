"""THE LINE menu for Maya, built from the script library folders at startup.

Menu item callbacks are plain Python callables, so no menu definition file is generated or read.
"""

import importlib
import os
from functools import partial

from tls_common import MayaLogger

from . import scriptLibrary


class log(MayaLogger):
    NAME = "line_tools.menu"

MENU_NAME = "TheLineMenu"
MENU_LABEL = "THE LINE"


def install(root=None):
    """Build the menu once Maya's UI is ready. Does nothing in batch or standalone sessions."""
    from maya import cmds, utils

    if cmds.about(batch=True):
        return
    utils.executeDeferred(partial(build, root))


def build(root=None):
    """(Re)build the menu from the folders on disk."""
    from maya import cmds, mel, utils

    library = scriptLibrary.scan(root)

    if cmds.menu(MENU_NAME, exists=True):
        cmds.deleteUI(MENU_NAME)
    cmds.menu(MENU_NAME, label=MENU_LABEL, parent=mel.eval("$tmp = $gMainWindow"), tearOff=True)

    for script in library.top_level:
        _add_item(script, root)
    if library.top_level and library.sections:
        cmds.menuItem(divider=True)
    for section in library.sections:
        cmds.menuItem(label=section.title, subMenu=True, tearOff=True)
        for script in section.scripts:
            _add_item(script, root)
        cmds.setParent(MENU_NAME, menu=True)

    cmds.menuItem(divider=True)
    cmds.menuItem(label="Rebuild Menu", command=lambda *_: utils.executeDeferred(partial(build, root)))
    cmds.menuItem(label="About THE LINE Pipeline...", command=show_about)
    log.info("%s menu built: %d top level, %d submenus", MENU_LABEL, len(library.top_level), len(library.sections))


def about_text():
    """What this session is running, from the TLS_PIPELINE_MAYA_* variables the pipeline entry sets."""
    try:
        return importlib.import_module("tls_pipeline.about").text("maya")
    except Exception:
        release = os.environ.get("TLS_PIPELINE_MAYA_RELEASE", "")
        return "THE LINE pipeline\n\n" + ("Release:  " + release if release else "No pipeline bundle is loaded.")


def show_about(*_):
    from maya import cmds

    cmds.confirmDialog(title="About THE LINE Pipeline", message=about_text(), button=["OK"])


def _notify(text):
    """Show a message in the viewport, where a failed menu click is easy to miss in the Script Editor."""
    from maya import cmds

    cmds.inViewMessage(amg="<hl>{}</hl>".format(text), pos="topCenter", fade=True)


def _add_item(script, root):
    from maya import cmds

    annotation = "{}/{}".format(script.section, script.file_name)
    if script.requires:
        annotation += "  (needs {})".format(", ".join(name for name, _ in script.requires))
    cmds.menuItem(
        label=script.title,
        annotation=annotation,
        command=lambda *_: scriptLibrary.run_script(script.section, script.file_name, root, notify=_notify),
    )
