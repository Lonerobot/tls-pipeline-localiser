import nuke
import re

def snap_dot_to_node(dot_node, target_node, y_offset=120):
    """Align the Dot centered above the target node for straight pipes."""
    try:
        x = target_node.xpos() + (target_node.screenWidth() // 2) - 6
    except Exception:
        x = target_node.xpos()
    y = target_node.ypos() - y_offset
    dot_node.setXYpos(x, y)

def get_exr_layers(read_node):
    ignore = {'rgba', 'rgb', 'alpha', 'other'}
    layers = [l for l in nuke.layers(read_node) if l not in ignore]
    seen, out = set(), []
    for l in layers:
        if l not in seen:
            seen.add(l)
            out.append(l)
    return out

def build_split_over(node):
    """
    For each non-standard layer:
      Dot -> Shuffle(in=layer) -> Remove(keep rgba), labeled
    Merge all branches with 'over', starting from a black base.
    """

    X = node.xpos()
    Y = node.ypos() + 200
    x_spacing = 220

    layers = get_exr_layers(node)
    if not layers:
        nuke.message("No extra EXR layers found on the selected Read.")
        return

    # Input tap
    mainDot = nuke.createNode('Dot', inpanel=False)
    mainDot.setInput(0, node)
    mainDot.setXYpos(X + 30, Y)

    baseDot = nuke.createNode('Dot', inpanel=False)
    baseDot.setInput(0, mainDot)
    baseDot.setXYpos(X + 30, Y + 180)

    # Black RGBA base
    shuffle_black = nuke.createNode('Shuffle', inpanel=False)
    for ch in ('red', 'green', 'blue', 'alpha'):
        shuffle_black[ch].setValue('black')
    shuffle_black['label'].setValue('black')
    shuffle_black.setInput(0, baseDot)
    shuffle_black.setXYpos(X, Y + 300)

    remove_black = nuke.createNode('Remove', inpanel=False)
    remove_black['operation'].setValue('keep')
    remove_black['channels'].setValue('rgba')
    remove_black.setInput(0, shuffle_black)
    remove_black.setXYpos(X, Y + 400)

    black_dot = nuke.createNode('Dot', inpanel=False)
    black_dot.setInput(0, remove_black)
    y_merge = Y + 800
    black_dot.setXYpos(X + 30, y_merge)
    merge_chain = black_dot

    # Per-layer branches, merged with 'over'
    previous_dot = baseDot
    for i, layer in enumerate(layers):
        x = X + (i + 1) * x_spacing
        y = Y + 200

        dot = nuke.createNode('Dot', inpanel=False)
        dot.setInput(0, previous_dot)

        shuffle = nuke.createNode('Shuffle', inpanel=False)
        shuffle['in'].setValue(layer)
        shuffle['label'].setValue('[value in]')
        shuffle.setInput(0, dot)
        shuffle.setXYpos(x, y + 100)

        premult = nuke.createNode('Premult', inpanel=False)
        #premult['in'].setValue(layer)
        #premult['label'].setValue('[value in]')
        premult.setInput(0, shuffle)
        premult.setXYpos(x, y + 150)

        

        #s = "d_colour_G010_L010_BANX_OUTLINE"

        # Use regex to capture everything after Gxxx_Lxxx_
        match = re.search(r"G\d{3}_L\d{3}_(.*)", layer)
        if match:
            layer = match.group(1)
            print(layer)  # BANX_OUTLINE
        else:
            result = layer  # fallback if pattern not found






        snap_dot_to_node(dot, shuffle)
        dot['label'].setValue(layer)
        dot['note_font_size'].setValue(20)
        dot['note_font_color'].setValue(0x8E8A7A00)



        remove = nuke.createNode('Remove', inpanel=False)
        remove['operation'].setValue('keep')
        remove['channels'].setValue('rgba')
        remove.setInput(0, premult)
        remove.setXYpos(x, y + 200)

        



        merge = nuke.createNode('Merge2', inpanel=False)
        merge['operation'].setValue('over')
        merge.setInput(0, merge_chain)  # B (accumulated)
        merge.setInput(1, remove)       # A (new layer)
        merge.setXYpos(x, y_merge)

        merge_chain = merge
        previous_dot = dot

    

def split_all_layers_over():
    try:
        read_node = nuke.selectedNode()
    except Exception:
        nuke.message("Select a Read node with a multichannel EXR.")
        return

    if read_node.Class() != "Read":
        nuke.message("Select a Read node with a multichannel EXR.")
        return

    build_split_over(read_node)

# Run immediately
split_all_layers_over()
