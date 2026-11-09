import os
import time
import nuke

try:
    # Nuke 16.0+ uses Qt 6 / PySide6.
    from PySide6 import QtWidgets, QtGui
except ImportError:
    try:
        # Keep compatibility with older Nuke versions such as Nuke 15.
        from PySide2 import QtWidgets, QtGui
    except ImportError:
        QtWidgets, QtGui = None, None


def paste_clipboard_image():
    """
    Grab an image from the system clipboard, save it into
    'references/' next to the current .nk file, and create a Read node.
    """
    if QtWidgets is None or QtGui is None:
        nuke.message("PySide6/PySide2 Qt bindings are not available in this Nuke build.")
        return

    # Require saved script, so we know where "references" goes
    nk_path = nuke.root().name()
    if not nk_path:
        nuke.message("Please save your Nuke script first.")
        return

    proj_dir = os.path.dirname(nk_path)
    ref_dir = os.path.join(proj_dir, "references")
    os.makedirs(ref_dir, exist_ok=True)

    cb = QtWidgets.QApplication.clipboard()
    if not cb:
        nuke.message("Clipboard not accessible.")
        return

    img = cb.image()
    if img.isNull():
        nuke.message("Clipboard does not contain an image.")
        return

    # Save as PNG with timestamp
    fname = "clipboard_%s.png" % time.strftime("%Y%m%d_%H%M%S")
    out_path = os.path.join(ref_dir, fname)
    if not img.save(out_path, "PNG"):
        nuke.message("Failed to save image.")
        return

    node = nuke.createNode("Read", f'file {{{out_path}}}', inpanel=False)
    node.setSelected(True)
    nuke.zoomToFitSelected()
    return node

if __name__ == "__main__":
    paste_clipboard_image()