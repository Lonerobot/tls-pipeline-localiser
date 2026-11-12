# ============================
# Nuke 15 - Backdrop Maker (Floating)
# - Preset swatches with paired text colours
# - Colour picker affects backdrop only (text uses Nuke default)
# - Text size presets: Big(150) / Medium(75) / Small(25) — default Small
# - Always wraps selected nodes (no checkbox)
# - Label normalization: uppercase, "_" and "-" replaced with spaces
# - Minimal UI; window auto-closes after Create
# ============================

import nuke

# ---- Qt import (Nuke 17 ships with PySide6) ----
try:
    from PySide6 import QtWidgets, QtCore, QtGui
except ImportError:
    from PySide import QtGui as QtWidgets
    from PySide import QtCore
    QtGui = QtWidgets

# ============================
# SETTINGS — tweak these to your preference
# ============================
SETTINGS = {
    # Label font family (must exist on your OS/Nuke env)
    "FONT_FAMILY": "Arial Bold",

    # Default text size preset to use when the UI opens ("Big", "Medium", or "Small")
    "DEFAULT_TEXT_SIZE_PRESET": "Small",  # default Small

    # Backdrop appearance: "filled" (0) or "border" (1)
    "FILL_STYLE": "border",  # "filled" | "border"
}

# Text size presets (pt)
TEXT_SIZE_PRESETS = {
    "Big": 150.0,
    "Medium": 75.0,
    "Small": 25.0,
}

# ============================================================
# Preset swatches: (BACKDROP_RGBF, TEXT_RGBF)
# - Floats 0..1. TEXT_RGBF is used ONLY for presets.
# - Colour picker does NOT set text colour (uses Nuke default).
# ============================================================
PALETTE = [
    # Blue
    ((0.122, 0.275, 0.322), (0.635, 0.788, 0.835)),
    # Green
    ((0.000, 0.259, 0.259), (0.510, 0.769, 0.682)),
    # Orange
    ((0.565, 0.247, 0.122), (0.792, 0.612, 0.533)),
    # Red
    ((0.400, 0.149, 0.169), (0.867, 0.573, 0.612)),
]

# ---- Helpers (float RGB) ----
def clamp01(x):
    try:
        v = float(x)
    except Exception:
        v = 0.0
    return 0.0 if v < 0.0 else (1.0 if v > 1.0 else v)

def rgbf_to_255(rgbf):
    r, g, b = rgbf
    return (int(round(clamp01(r) * 255)),
            int(round(clamp01(g) * 255)),
            int(round(clamp01(b) * 255)))

def rgbf_to_css(rgbf):
    r, g, b = rgbf_to_255(rgbf)
    return f"rgb({r},{g},{b})"

def rgbf_to_nuke_rgba_int(rgbf, a=1.0):
    """
    Convert float rgb (0..1) to Nuke 0xRRGGBBAA (alpha last) integer.
    """
    r, g, b = rgbf_to_255(rgbf)
    a8 = int(round(clamp01(a) * 255)) & 0xFF
    return (r << 24) | (g << 16) | (b << 8) | a8

def bounds_of_nodes(nodes):
    """Return (x, y, w, h) covering the given nodes, using screen size where possible."""
    if not nodes:
        return None
    min_x = min(n.xpos() for n in nodes)
    min_y = min(n.ypos() for n in nodes)
    # Use screenWidth/screenHeight when available to get proper extents
    max_x = max(n.xpos() + getattr(n, "screenWidth", lambda: n.width() if hasattr(n, "width") else 80)() for n in nodes)
    max_y = max(n.ypos() + getattr(n, "screenHeight", lambda: n.height() if hasattr(n, "height") else 50)() for n in nodes)
    return (min_x, min_y, max_x - min_x, max_y - min_y)

def normalize_label(text):
    """Uppercase and replace underscores/hyphens with spaces."""
    if not text:
        return ""
    t = text.replace("_", " ").replace("-", " ")
    return t.upper()

def qcolor_to_rgbf(qc):
    """QtGui.QColor -> (r,g,b) floats 0..1"""
    r, g, b, _a = qc.getRgbF()
    return (clamp01(r), clamp01(g), clamp01(b))

def rgbf_to_qcolor(rgbf):
    r, g, b = rgbf
    qc = QtGui.QColor()
    qc.setRgbF(clamp01(r), clamp01(g), clamp01(b), 1.0)
    return qc

def create_backdrop(label_text, rgbf_color, text_rgbf_override=None, font_size_pt=None, padding=80, default_size=(320, 200)):
    """
    Create a BackdropNode with color and label.
    - Colors are float RGB tuples in 0..1
    - Always wraps currently selected nodes (if any).
    - font_size_pt overrides preset. If None, uses the current preset from UI/SETTINGS.
    - text_rgbf_override: if provided, sets note_font_color; if None, uses Nuke default.
    """
    rgbf_color = tuple(clamp01(c) for c in rgbf_color)
    if text_rgbf_override is not None:
        text_rgbf_override = tuple(clamp01(c) for c in text_rgbf_override)

    sel = nuke.selectedNodes()
    if sel:
        x, y, w, h = bounds_of_nodes(sel)
        x -= padding
        y -= padding
        w += padding * 2
        h += padding * 2
    else:
        all_nodes = [n for n in nuke.allNodes() if n.Class() != "BackdropNode"]
        if all_nodes:
            avg_x = sum(n.xpos() for n in all_nodes) // max(len(all_nodes), 1)
            avg_y = sum(n.ypos() for n in all_nodes) // max(len(all_nodes), 1)
        else:
            avg_x, avg_y = (0, 0)
        x = avg_x - default_size[0] // 2
        y = avg_y - default_size[1] // 2
        w, h = default_size

    bd = nuke.nodes.BackdropNode()
    bd["xpos"].setValue(int(x))
    bd["ypos"].setValue(int(y))
    bd["bdwidth"].setValue(int(w))
    bd["bdheight"].setValue(int(h))

    if label_text:
        bd["label"].setValue(normalize_label(label_text))

    # --- Apply font settings ---
    try:
        bd["note_font"].setValue(SETTINGS.get("FONT_FAMILY", "Arial"))
    except Exception:
        pass
    try:
        size_to_set = float(font_size_pt) if font_size_pt is not None else float(
            TEXT_SIZE_PRESETS.get(SETTINGS.get("DEFAULT_TEXT_SIZE_PRESET", "Small"), 25.0)
        )
        bd["note_font_size"].setValue(size_to_set)
    except Exception:
        pass

    # --- Colors ---
    bd["tile_color"].setValue(rgbf_to_nuke_rgba_int(rgbf_color, 1.0))
    if text_rgbf_override is not None:
        bd["note_font_color"].setValue(rgbf_to_nuke_rgba_int(text_rgbf_override, 1.0))
    # else: don't touch note_font_color (uses Nuke default)

    # --- Appearance (filled or border) ---
    appearance = 0 if SETTINGS.get("FILL_STYLE", "filled").lower() == "filled" else 1
    try:
        bd["appearance"].setValue(appearance)
    except Exception:
        pass

    # Put backdrop behind others visually
    bd.setSelected(False)
    bd["z_order"].setValue(-1)

    nuke.tprint("[BackdropMaker] Created backdrop:",
                label_text, "→", bd["label"].value(),
                "rgb:", rgbf_color, "text rgb:", ("<default>" if text_rgbf_override is None else text_rgbf_override),
                "appearance:", appearance,
                "wrapped_selection=", bool(sel))
    return bd

# ---- UI (Floating Window) ----
class BackdropMaker(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super(BackdropMaker, self).__init__(parent)
        self.setWindowTitle("Backdrop Maker")
        self.setWindowFlags(QtCore.Qt.Window | QtCore.Qt.WindowTitleHint | QtCore.Qt.WindowCloseButtonHint)

        # Defaults from first preset
        self.selected_rgbf, self.selected_text_rgbf = PALETTE[0]
        # Default text size preset
        self.selected_text_size_name = SETTINGS.get("DEFAULT_TEXT_SIZE_PRESET", "Small")

        # --- Inputs ---
        self.labelEdit = QtWidgets.QLineEdit()
        self.labelEdit.setPlaceholderText("Backdrop label")

        # Preview swatch
        self.preview = QtWidgets.QLabel()
        self.preview.setFixedSize(48, 28)
        self.preview.setStyleSheet(
            f"background: {rgbf_to_css(self.selected_rgbf)}; border: 1px solid rgba(0,0,0,0.25); border-radius: 4px;"
        )

        # "Colour picker" heading + blank button
        self.pickerHeading = QtWidgets.QLabel("Colour picker")
        font = self.pickerHeading.font()
        font.setBold(True)
        self.pickerHeading.setFont(font)

        self.pickBgBtn = QtWidgets.QPushButton("")  # blank button
        self.pickBgBtn.setFixedSize(80, 28)
        self.pickBgBtn.setToolTip("Open colour picker")
        self.pickBgBtn.clicked.connect(self.onPickBg)

        # Text size preset selector
        self.sizeCombo = QtWidgets.QComboBox()
        self.sizeCombo.addItems(["Big", "Medium", "Small"])
        try:
            idx = ["Big", "Medium", "Small"].index(self.selected_text_size_name)
        except ValueError:
            idx = 2  # Small
        self.sizeCombo.setCurrentIndex(idx)
        self.sizeCombo.currentTextChanged.connect(self.onSizeChanged)

        # --- Top form layout ---
        top_form = QtWidgets.QGridLayout()
        row = 0
        top_form.addWidget(QtWidgets.QLabel("Label:"), row, 0)
        top_form.addWidget(self.labelEdit, row, 1, 1, 3)
        row += 1
        top_form.addWidget(QtWidgets.QLabel("Color:"), row, 0)
        top_form.addWidget(self.preview, row, 1)
        row += 1
        top_form.addWidget(self.pickerHeading, row, 0, 1, 4)
        row += 1
        top_form.addWidget(self.pickBgBtn, row, 1)

        # --- Swatch grid (no names; presets carry text colour) ---
        swatch_grid = QtWidgets.QGridLayout()
        swatch_grid.setSpacing(6)
        cols = 6
        for i, (rgbf, text_rgbf) in enumerate(PALETTE):
            btn = QtWidgets.QPushButton()
            btn.setFixedSize(36, 36)
            btn.setCursor(QtCore.Qt.PointingHandCursor)
            btn.setStyleSheet("border: 1px solid rgba(0,0,0,0.25); border-radius: 6px;")
            sw = QtWidgets.QLabel()
            sw.setAutoFillBackground(True)
            sw.setStyleSheet(f"background: {rgbf_to_css(rgbf)}; border-radius: 4px;")
            lay = QtWidgets.QVBoxLayout(btn)
            lay.setContentsMargins(3, 3, 3, 3)
            lay.addWidget(sw)
            btn._rgbf = rgbf
            btn._text_rgbf = text_rgbf
            btn.clicked.connect(self.onPresetClick)
            r, c = divmod(i, cols)
            swatch_grid.addWidget(btn, r, c)

        # Create button + text size row at the bottom
        bottom_row = QtWidgets.QHBoxLayout()
        bottom_row.addWidget(QtWidgets.QLabel("Text Size:"))
        bottom_row.addWidget(self.sizeCombo)
        bottom_row.addStretch(1)

        self.createBtn = QtWidgets.QPushButton("Create Backdrop")
        self.createBtn.setFixedHeight(32)
        self.createBtn.clicked.connect(self.onCreate)

        # Layout
        outer = QtWidgets.QVBoxLayout(self)
        outer.addLayout(top_form)
        outer.addSpacing(6)
        outer.addLayout(swatch_grid)
        outer.addSpacing(8)
        outer.addLayout(bottom_row)
        outer.addWidget(self.createBtn)
        outer.addStretch(1)

    # ---- UI callbacks ----
    def onPresetClick(self):
        btn = self.sender()
        self.selected_rgbf = btn._rgbf
        self.selected_text_rgbf = btn._text_rgbf   # enable preset text colour
        self.preview.setStyleSheet(
            f"background: {rgbf_to_css(self.selected_rgbf)}; border: 1px solid rgba(0,0,0,0.25); border-radius: 4px;"
        )
        nuke.tprint("[BackdropMaker] Preset selected (bg+text)")

    def onPickBg(self):
        qc = QtWidgets.QColorDialog.getColor(
            initial=rgbf_to_qcolor(self.selected_rgbf),
            parent=self,
            title="Pick Backdrop Color",
            options=QtWidgets.QColorDialog.ShowAlphaChannel  # alpha ignored; always 1.0
        )
        if qc.isValid():
            self.selected_rgbf = qcolor_to_rgbf(qc)
            self.selected_text_rgbf = None  # picker uses Nuke default text colour
            self.preview.setStyleSheet(
                f"background: {rgbf_to_css(self.selected_rgbf)}; border: 1px solid rgba(0,0,0,0.25); border-radius: 4px;"
            )

    def onSizeChanged(self, name):
        if name in TEXT_SIZE_PRESETS:
            self.selected_text_size_name = name

    def onCreate(self):
        label_text = self.labelEdit.text().strip()
        try:
            font_size_pt = TEXT_SIZE_PRESETS.get(self.selected_text_size_name, 25.0)
            bd = create_backdrop(
                label_text,
                self.selected_rgbf,
                text_rgbf_override=self.selected_text_rgbf,  # None => keep default text colour
                font_size_pt=font_size_pt
            )
            # Select the new backdrop for convenience
            for n in nuke.selectedNodes():
                n.setSelected(False)
            bd.setSelected(True)
        except Exception as e:
            nuke.message("Failed to create backdrop:\n\n" + str(e))
            nuke.tprint("[BackdropMaker] Error:", e)
        finally:
            # Always close after clicking Create (success or error)
            self.close()

# ---- Launcher (floating only) ----
_backdrop_maker_window = None

def show_backdrop_maker():
    """Show (or raise) the floating Backdrop Maker window."""
    global _backdrop_maker_window
    if _backdrop_maker_window is None or not isinstance(_backdrop_maker_window, BackdropMaker):
        _backdrop_maker_window = BackdropMaker()
    _backdrop_maker_window.show()
    _backdrop_maker_window.raise_()
    _backdrop_maker_window.activateWindow()

# ---- Optional: Add to Nuke menu ----
# try:
#     nuke.menu("Nuke").addCommand("Backdrop/Backdrop Maker...", "show_backdrop_maker()", "")
# except Exception as _e:
#     nuke.tprint("[BackdropMaker] Menu registration failed:", _e)

# If you want it to pop up immediately on script load, uncomment:
# show_backdrop_maker()
