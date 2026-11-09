import nuke
import re

# ============================================================================
# SETTINGS — adjust to tune B-pipe base behaviour
# ============================================================================
# B_PIPE_BASE defines the Constant node placed at the base of the B-pipe stack.
# Change 'color' to (0,0,0,1) for black, (1,1,1,1) for white, etc.
SETTINGS = {
    'B_PIPE_BASE': {
        'type':  'Constant',
        'knobs': {'color': (0.5, 0.5, 0.5, 1.0)},   # 50% grey default
    },
}

# ============================================================================
# LAYOUT CONSTANTS (pixels)
# ============================================================================
X_SPACING      = 220   # horizontal gap between layer branches
GROUP_HEIGHT   = 950   # reserved vertical height per group
GROUP_GAP      = 200   # extra gap between stacked groups
B_PIPE_GAP     = 300   # gap from last branch column to B-pipe column
Y_MERGE_OFFSET = 800   # distance below y_origin for the group merge row
Y_CHAIN_STEP   = 50    # vertical step between post-shuffle chain nodes

# ============================================================================
# POST-SHUFFLE CHAIN
# Each entry is applied to every layer branch after the Shuffle node.
# Add a Grade or ColorSpace dict here to insert it globally.
# ============================================================================
POST_SHUFFLE_CHAIN = [
    {'type': 'Premult', 'knobs': {}},
    {'type': 'Remove',  'knobs': {'operation': 'keep', 'channels': 'rgba'}},
]


# ============================================================================
# LAYER PARSING UTILITIES
# ============================================================================

def parse_layer(layer_name):
    """
    Parse a layer name of the form '..._G###_L###_<short>'.
    Returns {'g_num': int, 'l_num': int, 'short_name': str}.
    Falls back to g_num=9999, l_num=0, short_name=layer_name if no match.
    """
    m = re.search(r'G(\d{3})_L(\d{3})_(.*)', layer_name)
    if m:
        return {
            'g_num':      int(m.group(1)),
            'l_num':      int(m.group(2)),
            'short_name': m.group(3),
            'layer_id':   'G{}_L{}_{}'.format(m.group(1), m.group(2), m.group(3)),
        }
    return {'g_num': 9999, 'l_num': 0, 'short_name': layer_name, 'layer_id': layer_name}


def get_group_number(layers):
    """Return the G-number of the first layer that matches the G/L pattern."""
    for layer in layers:
        info = parse_layer(layer)
        if info['g_num'] != 9999:
            return info['g_num']
    return 9999


def sort_layers(layers):
    """Sort layers ascending by (g_num, l_num); unmatched layers sort to the end."""
    return sorted(layers, key=lambda l: (parse_layer(l)['g_num'],
                                         parse_layer(l)['l_num']))


# ============================================================================
# NODE HELPERS
# ============================================================================

def snap_dot_to_node(dot_node, target_node, y_offset=120):
    """Centre a Dot above a target node for straight pipes."""
    try:
        x = target_node.xpos() + (target_node.screenWidth() // 2) - 6
    except Exception:
        x = target_node.xpos()
    y = target_node.ypos() - y_offset
    dot_node.setXYpos(x, y)


def get_exr_layers(read_node):
    """Return unique non-standard layers from a Read node."""
    ignore = {'rgba', 'rgb', 'alpha', 'other'}
    layers = [l for l in nuke.layers(read_node) if l not in ignore]
    seen, out = set(), []
    for l in layers:
        if l not in seen:
            seen.add(l)
            out.append(l)
    return out


def _set_knob(node, knob, value):
    """Set a knob value, handling tuples/lists for multi-channel knobs."""
    k = node[knob]
    if isinstance(value, (list, tuple)):
        k.setValue(list(value))
    else:
        k.setValue(value)


def get_or_create_format(w, h, pixel_aspect=1.0):
    """Find or create a Nuke format for (w, h). Returns a nuke.Format object."""
    for fmt in nuke.formats():
        if fmt.width() == w and fmt.height() == h:
            return fmt
    # Full descriptor: width height x y r t pixel_aspect name
    name = 'EXRComper_{}x{}'.format(w, h)
    nuke.addFormat('{w} {h} 0 0 {w} {h} {pa} {name}'.format(
        w=w, h=h, pa=pixel_aspect, name=name))
    for fmt in nuke.formats():
        if fmt.width() == w and fmt.height() == h:
            return fmt
    return None


def check_and_resolve_format(valid):
    """
    Compare Read node resolutions against the root format.

    Returns (fmt_obj, warning_message):
      - fmt_obj         : nuke.Format to apply to BG_PLACEHOLDER, or None if
                          footage matches the root format exactly.
      - warning_message : string to display after building, or None if no
                          action is needed.

    Rules:
      - All groups same resolution == root  → no change, no warning.
      - All groups same, differs from root  → set format, warn.
      - Groups have different resolutions   → pick largest, set format, warn
                                              and list per-group resolutions.
      - Footage larger than root in either  → use the specific wording
                                              requested by the user.
    """
    root_fmt = nuke.root().format()
    root_w   = root_fmt.width()
    root_h   = root_fmt.height()

    # Collect (node_name, w, h, pixel_aspect) per group.
    # node.format() / node['format'].value() may return the output/proxy format
    # rather than the native file resolution in some Nuke configurations.
    # node.metadata() reads directly from the file and is the most reliable source.
    group_res = []
    for _, node, _ in valid:
        try:
            w  = int(node.metadata('input/width')  or 0)
            h  = int(node.metadata('input/height') or 0)
            if not (w and h):
                raise ValueError('zero dimensions in metadata')
            pa = node.format().pixelAspect()
        except Exception:
            # Fallback: use the node's output format
            fmt = node.format()
            w, h, pa = fmt.width(), fmt.height(), fmt.pixelAspect()
        group_res.append((node.name(), w, h, pa))

    unique_dims = list(set((r[1], r[2]) for r in group_res))
    all_same    = len(unique_dims) == 1

    if all_same:
        target_w, target_h = unique_dims[0]
        target_pa          = group_res[0][3]
    else:
        # Multiple resolutions — use the largest by pixel count
        largest   = max(group_res, key=lambda r: r[1] * r[2])
        target_w  = largest[1]
        target_h  = largest[2]
        target_pa = largest[3]

    matches_root    = (target_w == root_w and target_h == root_h)
    larger_than_root = (target_w > root_w or target_h > root_h)

    # Nothing to do if footage matches root and all groups agree
    if matches_root and all_same:
        return None, None

    fmt_obj = get_or_create_format(target_w, target_h, target_pa)

    parts = []

    if larger_than_root:
        parts.append(
            'Footage is larger than the root format.\n'
            'BG_PLACEHOLDER was set to {} x {} px'.format(target_w, target_h)
        )
    elif not matches_root:
        parts.append(
            'BG_PLACEHOLDER format set to match footage: {} x {} px\n'
            '(Root format: {} x {} px)'.format(target_w, target_h, root_w, root_h)
        )

    if not all_same:
        lines = ['Input resolution mismatch — resolutions per group:']
        for name, w, h, _ in group_res:
            lines.append('  {}: {} x {} px'.format(name, w, h))
        lines.append('Largest resolution used for BG_PLACEHOLDER: {} x {} px'.format(
            target_w, target_h))
        parts.append('\n'.join(lines))

    warning = '\n\n'.join(parts) if parts else None
    return fmt_obj, warning


def build_post_shuffle_chain(input_node, x, y_start):
    """
    Create all POST_SHUFFLE_CHAIN nodes wired in sequence below input_node.
    Returns (last_node, y_end).
    """
    current = input_node
    y = y_start
    for entry in POST_SHUFFLE_CHAIN:
        node = nuke.createNode(entry['type'], inpanel=False)
        for knob, value in entry['knobs'].items():
            _set_knob(node, knob, value)
        node.setInput(0, current)
        node.setXYpos(x, y)
        y += Y_CHAIN_STEP
        current = node
    return current, y


def build_b_pipe_base(x, y, fmt=None):
    """Create the B-pipe base node as configured in SETTINGS['B_PIPE_BASE'].

    If fmt (a nuke.Format object) is supplied, the Constant's format expression
    is cleared and the knob is set to that format explicitly.
    """
    cfg = SETTINGS['B_PIPE_BASE']
    node = nuke.createNode(cfg['type'], inpanel=False)
    for knob, value in cfg['knobs'].items():
        _set_knob(node, knob, value)
    if fmt is not None:
        # The Constant defaults to a 'root.format' expression. setValue() and
        # clearAnimated() do not reliably override it. fromScript() bypasses
        # the expression system and sets the value directly.
        fmt_str = '{w} {h} 0 0 {w} {h} {pa} {name}'.format(
            w=fmt.width(), h=fmt.height(), pa=fmt.pixelAspect(), name=fmt.name())
        node['format'].fromScript(fmt_str)
    node.setName('BG_PLACEHOLDER')
    node.setXYpos(x, y)
    return node


# ============================================================================
# GROUP TREE BUILDER
# ============================================================================

def build_group_tree(read_node, x_origin, y_origin):
    """
    Build the split-and-over node tree for one Read node at the given position.

    Layout (all relative to y_origin):
      y_origin - 150    — Read node (snapped into column)
      y_origin + 180    — base Dot (feeds horizontal branch tap chain)
      y_origin + 300    — Shuffle nodes
      y_origin + 350/400 — post-shuffle chain (Premult, Remove, …)
      y_origin + 640    — black Shuffle + Remove base for the internal over stack
      y_origin + 800    — merge row (all Merge2 nodes)

    Returns (final_merge_node, x_max).
    """
    layers  = sort_layers(get_exr_layers(read_node))
    y_merge = y_origin + Y_MERGE_OFFSET

    # -- snap Read node into the group column, then tap directly -----------
    read_node.setXYpos(x_origin, y_origin - 150)

    base_dot = nuke.createNode('Dot', inpanel=False)
    base_dot.setInput(0, read_node)
    base_dot.setXYpos(x_origin + 34, y_origin + 180)

    # -- black Shuffle + Remove as the group's internal over base ----------
    shuffle_black = nuke.createNode('Shuffle', inpanel=False)
    for ch in ('red', 'green', 'blue', 'alpha'):
        shuffle_black[ch].setValue('black')
    shuffle_black['label'].setValue('black')
    shuffle_black.setInput(0, base_dot)
    shuffle_black.setXYpos(x_origin, y_origin + 300)

    remove_black = nuke.createNode('Remove', inpanel=False)
    remove_black['operation'].setValue('keep')
    remove_black['channels'].setValue('rgba')
    remove_black.setInput(0, shuffle_black)
    remove_black.setXYpos(x_origin, y_origin + 350)

    black_dot = nuke.createNode('Dot', inpanel=False)
    black_dot.setInput(0, remove_black)
    black_dot.setXYpos(x_origin + 34, y_merge + 6)

    merge_chain  = black_dot
    previous_dot = base_dot
    x_max        = x_origin

    # -- per-layer branches -------------------------------------------------
    for i, layer_name in enumerate(layers):
        info  = parse_layer(layer_name)
        short = info['short_name']

        x        = x_origin + (i + 1) * X_SPACING
        y_branch = y_origin + 200

        # tap dot (label set after snap, below)
        dot = nuke.createNode('Dot', inpanel=False)
        dot.setInput(0, previous_dot)

        # shuffle
        shuffle = nuke.createNode('Shuffle', inpanel=False)
        shuffle['in'].setValue(layer_name)
        shuffle['label'].setValue(info['layer_id'])
        shuffle.setInput(0, dot)
        shuffle.setXYpos(x, y_branch + 100)

        # position label dot above shuffle
        snap_dot_to_node(dot, shuffle)
        dot['label'].setValue(short)
        dot['note_font_size'].setValue(20)
        dot['note_font_color'].setValue(0x8E8A7A00)

        # post-shuffle chain (Premult, Remove, …)
        chain_end, _ = build_post_shuffle_chain(
            shuffle, x, shuffle.ypos() + Y_CHAIN_STEP
        )

        # merge into running accumulator
        merge = nuke.createNode('Merge2', inpanel=False)
        merge['operation'].setValue('over')
        merge.setInput(0, merge_chain)  # B — accumulated
        merge.setInput(1, chain_end)    # A — this layer
        merge.setXYpos(x, y_merge)

        merge_chain  = merge
        previous_dot = dot
        x_max        = x + 80   # account for node width

    return merge_chain, x_max


# ============================================================================
# ENTRY POINT
# ============================================================================

def split_all_layers_over():
    # -- collect and validate selected Read nodes ---------------------------
    valid = []
    for node in nuke.selectedNodes():
        if node.Class() != 'Read':
            print("[exr2DAnimComper] Skipping '{}' — not a Read node.".format(node.name()))
            continue
        layers = get_exr_layers(node)
        if not layers:
            print("[exr2DAnimComper] Skipping '{}' — no non-standard EXR layers.".format(node.name()))
            continue
        valid.append((get_group_number(layers), node, layers))

    if not valid:
        nuke.message("No valid multichannel EXR Read nodes selected.")
        return

    # sort groups ascending by G-number
    valid.sort(key=lambda t: t[0])

    # -- resolve BG_PLACEHOLDER format before building ---------------------
    bg_fmt, fmt_warning = check_and_resolve_format(valid)

    # -- layout origin ------------------------------------------------------
    x_origin = min(node.xpos() for _, node, _ in valid)
    y_base   = min(node.ypos() for _, node, _ in valid) + 300

    # -- build each group tree ----------------------------------------------
    group_outputs = []   # list of (g_num, final_merge_node, y_origin)
    x_max_all = x_origin

    for idx, (g_num, node, _) in enumerate(valid):
        y_origin = y_base + idx * (GROUP_HEIGHT + GROUP_GAP)
        final_merge, x_max = build_group_tree(node, x_origin, y_origin)
        group_outputs.append((g_num, final_merge, y_origin))
        if x_max > x_max_all:
            x_max_all = x_max

    # -- B-pipe column ------------------------------------------------------
    x_bpipe    = x_max_all + B_PIPE_GAP
    base_node  = build_b_pipe_base(x_bpipe, y_base - 150, fmt=bg_fmt)
    b_chain    = base_node

    for g_num, group_merge, y_origin in group_outputs:
        y_bp_merge = y_origin + Y_MERGE_OFFSET

        # route dot brings the group output across to the B-pipe column
        route_dot = nuke.createNode('Dot', inpanel=False)
        route_dot.setInput(0, group_merge)
        route_dot.setXYpos(x_bpipe + 30, group_merge.ypos() + 6)

        bp_merge = nuke.createNode('Merge2', inpanel=False)
        bp_merge['operation'].setValue('over')
        bp_merge.setInput(0, b_chain)    # B — accumulated
        bp_merge.setInput(1, route_dot)  # A — this group
        bp_merge.setXYpos(x_bpipe, y_bp_merge)

        b_chain = bp_merge

    # -- post-build resolution warning ------------------------------------
    if fmt_warning:
        nuke.message(fmt_warning)


# Run immediately
split_all_layers_over()
