"""Nuke bootstrap menu: Help > About THE LINE Pipeline. Nuke runs menu.py only in the GUI, after init.py has
started the pipeline, so by now the session's release is in the environment.
"""
import importlib
import traceback

import nuke


def _about():
    try:
        message = importlib.import_module("tls_pipeline.about").text("nuke")
    except Exception:
        message = "THE LINE pipeline\n\nNo pipeline bundle is loaded in this session."
    nuke.message("<pre>{}</pre>".format(message.replace("&", "&amp;").replace("<", "&lt;")))


try:
    nuke.menu("Nuke").addCommand("Help/About THE LINE Pipeline", _about)
except Exception:
    traceback.print_exc()
    print("TLS pipeline: could not add the About menu item")
