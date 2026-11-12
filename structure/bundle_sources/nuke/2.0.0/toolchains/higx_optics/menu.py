# HigxOptics GUI helpers. Installed as ~/.nuke/higx/optics/menu.py by the
# build; that folder is on the plugin path, so Nuke runs this at GUI startup
# (terminal sessions never load menu.py).
#
# Input-arrow preservation: the node exposes an input arrow only while its
# enable checkbox is on, and enabled arrows pack down in a fixed logical
# order (higx_bokeh.cpp inputEnabled()/physFor()). Nuke stores connections
# by arrow INDEX, so enabling e.g. Layer C used to shove whatever fed the
# aperture map into the new layer C arrow. The knobChanged hook below
# snapshots the connections under the old packing the moment a checkbox
# flips, then re-plugs each upstream node into the arrow that carries its
# logical input under the new packing. Script load and paste are naturally
# safe: Nuke restores knobs before it makes any connections, so the
# snapshot is empty and the hook no-ops.

import os

import nuke

# Mirrors higx_bokeh.cpp: enum InputSlot order + inputEnabled(). Keep in
# sync with the C++ when inputs are added or gating rules change.
_HIGX_OPTICS_CLASS = "HigxOptics"
_HIGX_DIFFRACTION_CLASS = "HigxDiffraction"
_HIGX_TOGGLES = (
    "use_focus_map", "use_layer_a", "use_layer_b", "use_layer_c",
    "use_aperture_map", "use_depth_a", "use_depth_b", "use_depth_c",
    "layer_a_glitter", "use_glitter_matte", "use_front_filter",
)


def _higx_packing(states):
    """Arrow order (logical input names) for a dict of checkbox states."""
    layA = states["use_layer_a"]
    layB = states["use_layer_b"]
    layC = states["use_layer_c"]
    enabled = (
        ("img", True),
        ("focus", states["use_focus_map"]),
        ("layerA", layA),
        ("layerB", layB),
        ("layerC", layC),
        ("aperture", states["use_aperture_map"]),
        ("depthA", layA and states["use_depth_a"]),
        ("depthB", layB and states["use_depth_b"]),
        ("depthC", layC and states["use_depth_c"]),
        ("glitmap", layA and states["layer_a_glitter"]
                    and states["use_glitter_matte"]),
        ("frontfilter", states["use_front_filter"]),
    )
    return [name for name, on in enabled if on]


def _higx_states(node):
    states = {}
    for name in _HIGX_TOGGLES:
        k = node.knob(name)
        states[name] = bool(k.value()) if k is not None else False
    return states


def _higx_defer(fn):
    # The DAG grows/shrinks the arrow count after this knob event settles;
    # rewire on the next event-loop tick so every new arrow exists. Outside
    # the GUI (or without Qt) run inline: terminal Nuke resizes on demand.
    if nuke.GUI:
        for mod in ("PySide6", "PySide2"):
            try:
                qtcore = __import__(mod + ".QtCore", fromlist=["QTimer"])
                qtcore.QTimer.singleShot(0, fn)
                return
            except Exception:
                pass
    fn()


def _higx_input_remap():
    k = nuke.thisKnob()
    if k is None or k.name() not in _HIGX_TOGGLES:
        return
    node = nuke.thisNode()
    if node is None:
        return
    new_states = _higx_states(node)
    old_states = dict(new_states)
    old_states[k.name()] = not new_states[k.name()]
    old_map = _higx_packing(old_states)
    new_map = _higx_packing(new_states)
    if old_map == new_map:
        return
    # Snapshot upstream nodes by logical name under the OLD packing: the
    # arrows still hold their pre-toggle indices at this point.
    conns = {}
    for i, name in enumerate(old_map):
        try:
            up = node.input(i)
        except Exception:
            up = None
        if up is not None:
            conns[name] = up
    if not conns:
        return

    def _fix(attempt=0):
        try:
            settled = True
            for i, name in enumerate(new_map):
                want = conns.get(name)
                if not node.setInput(i, want) and want is not None:
                    settled = False   # arrow not there yet; try again
            if not settled and attempt < 3:
                _higx_defer(lambda: _fix(attempt + 1))
        except Exception as e:
            print("[higx] input remap skipped: %r" % (e,))

    _higx_defer(_fix)


nuke.addKnobChanged(_higx_input_remap, nodeClass=_HIGX_OPTICS_CLASS)

# DAG look of a freshly created node: dark tile, green note font, the
# same for both nodes. knobDefault only affects nodes made after this
# runs, so it never recolours a node that already exists.
#
# The values must be DECIMAL: a "0x..." string is accepted by knobDefault
# and then quietly does nothing. HigxOptics also answers node_color()
# with the same tile colour, the NDK-native hook, but that alone left
# the node its default light grey, so these calls are what colour it.
_HIGX_TILE_COLOR = 1128481791       # 0x434343ff, dark grey
_HIGX_NOTE_COLOR = 1961143807       # 0x74e4adff, green
for _cls in (_HIGX_OPTICS_CLASS, _HIGX_DIFFRACTION_CLASS):
    nuke.knobDefault(_cls + ".tile_color", str(_HIGX_TILE_COLOR))
    nuke.knobDefault(_cls + ".note_font_color", str(_HIGX_NOTE_COLOR))

# Nodes toolbar entry. The icons sit beside this file and are passed as
# absolute paths: a bare filename relies on the plugin-path search, which
# silently draws no icon when it misses. Nuke still finds HigxOptics.png by
# name on its own for the node body and the TAB list.
#
# Nuke wants forward slashes in a path on every platform, Windows included
# (nukescripts/cattery.py does the same normalise before it hands an icon
# path to addMenu). A native backslash path is accepted and then quietly
# draws nothing.
_HIGX_ICONS = os.path.dirname(os.path.abspath(__file__))


def _higx_icon(name):
    return os.path.join(_HIGX_ICONS, name).replace(os.sep, "/")


if nuke.GUI:
    # addMenu() hands back an existing menu of the same name and ignores the
    # icon in that case, so nothing else may create "Higx" first. The OFX
    # bundle used to, through its plugin grouping, until it started
    # declining the Nuke host.
    _higx_menu = nuke.toolbar("Nodes").addMenu("Higx",
                                              icon=_higx_icon("Higx.png"))
    _higx_menu.addCommand("HigxOptics",
                          "nuke.createNode('%s')" % _HIGX_OPTICS_CLASS,
                          icon=_higx_icon("HigxOptics.png"))
    _higx_menu.addCommand("HigxDiffraction",
                          "nuke.createNode('HigxDiffraction')",
                          icon=_higx_icon("HigxOptics.png"))
