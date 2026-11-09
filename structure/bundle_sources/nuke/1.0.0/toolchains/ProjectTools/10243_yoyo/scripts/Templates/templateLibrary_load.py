import nuke
import nukescripts
import os

def import_mp4s_to_contact_sheet(folder_path, backdrop_label):
    if not os.path.isdir(folder_path):
        nuke.message(f"Invalid folder selected: {folder_path}")
        return

    mp4_files = [f for f in os.listdir(folder_path) if f.lower().endswith('.mp4')]
    if not mp4_files:
        nuke.message(f"No MP4 files found in the selected folder: {folder_path}")
        return

    read_nodes = []
    reformat_nodes = []
    text_nodes = []

    xpos = 0
    ypos = 0
    spacing = 500  # More margin between nodes

    all_x_positions = []
    all_y_positions = []

    for mp4 in sorted(mp4_files):
        filepath = os.path.join(folder_path, mp4).replace("\\", "/")
        node_name = os.path.splitext(mp4)[0]

        read_node = nuke.createNode('Read', inpanel=False)
        read_node['file'].fromUserText(filepath)
        read_node['reload'].execute()
        read_node.setName(node_name)
        read_node.setXpos(xpos)
        read_node.setYpos(ypos)
        read_node['after'].setValue('loop')

        all_x_positions.append(xpos)
        all_y_positions.append(ypos)

        # Create Sticky Note above the Read Node with updated appearance
        sticky = nuke.createNode('StickyNote', inpanel=False)
        sticky.setXpos(xpos)
        sticky.setYpos(ypos - 100)
        sticky['label'].setValue(node_name.upper())
        sticky['note_font_size'].setValue(35)
        sticky['note_font'].setValue('Arial')
        sticky['tile_color'].setValue(0xef7780ff)

        reformat_node = nuke.createNode('Reformat', inpanel=False)
        reformat_node.setInput(0, read_node)
        reformat_node['format'].setValue("HD_720")
        reformat_node['resize'].setValue("width")
        reformat_node.setXpos(xpos)
        reformat_node.setYpos(ypos + 100)

        # Create NoOp Node after Reformat
        no_op_node = nuke.createNode('NoOp', inpanel=False)
        no_op_node.setInput(0, reformat_node)
        no_op_node.setName('Load_ToolSet')
        no_op_node['tile_color'].setValue(0x3cff74ff)
        no_op_node.setXpos(xpos)
        no_op_node.setYpos(ypos + 159)

        # Add Python Script Button to NoOp
        no_op_node.addKnob(nuke.Tab_Knob('load', 'load'))
        button = nuke.PyScript_Knob('LoadToolset', 'Load Toolset')
        button.setFlag(nuke.STARTLINE)
        script_path = filepath.replace('.mp4', '.nk').replace('/', '\\')

        # Calculate the offset outside the backdrop area
        load_offset_x = max(all_x_positions) + 600
        load_offset_y = max(all_y_positions) + 600

        button.setValue(f"import os\nif os.path.exists(r'{script_path}'):\n    for n in nuke.allNodes():\n        n.setSelected(False)\n    n = nuke.nodePaste(r'{script_path}')\n    if n:\n        for node in nuke.selectedNodes():\n            node.setXpos(node.xpos() + {load_offset_x})\n            node.setYpos(node.ypos() + {load_offset_y})\nelse:\n    nuke.message('Toolset not found: {script_path}')")
        no_op_node.addKnob(button)

        text_node = nuke.createNode('Text2', inpanel=False)
        text_node.setInput(0, no_op_node)
        text_node['box'].setValue([0, 0, 0, 720])
        text_node['font_size'].setValue(60)
        text_node['font'].setValue('Arial', 'Black')
        text_node['message'].setValue(node_name.upper())
        text_node['color'].setValue([1, 1, 1, 1])
        text_node['opacity'].setValue(1)
        text_node.setXpos(xpos)
        text_node.setYpos(ypos + 200)

        read_nodes.append(read_node)
        reformat_nodes.append(reformat_node)
        text_nodes.append(text_node)

        xpos += spacing

    # Calculate backdrop dimensions with more margin
    margin_x = 150
    margin_y = 150

    min_x = min(node.xpos() for node in read_nodes + reformat_nodes + text_nodes) - margin_x
    max_x = max(node.xpos() for node in read_nodes + reformat_nodes + text_nodes) + margin_x
    min_y = min(node.ypos() for node in read_nodes + reformat_nodes + text_nodes) - margin_y
    max_y = max(node.ypos() for node in read_nodes + reformat_nodes + text_nodes) + margin_y

    backdrop = nuke.createNode("BackdropNode")
    backdrop['xpos'].setValue(min_x)
    backdrop['bdwidth'].setValue(max_x - min_x)
    backdrop['ypos'].setValue(min_y)
    backdrop['bdheight'].setValue(max_y - min_y)
    backdrop['tile_color'].setValue(0x48ff75ff)
    backdrop['note_font'].setValue('Verdana Bold')
    backdrop['note_font_size'].setValue(42)
    backdrop['appearance'].setValue('Border')
    backdrop['label'].setValue(backdrop_label)

    for node in read_nodes + reformat_nodes + text_nodes:
        node.setSelected(False)

    contact_sheet = nuke.createNode('ContactSheet', inpanel=False)
    contact_sheet.setName('ContactSheet')
    contact_sheet['center'].setValue(True)
    contact_sheet['roworder'].setValue('TopBottom')
    contact_sheet['startframe'].setValue(1)
    contact_sheet['endframe'].setValue(10)
    contact_sheet['tile_color'].setValue(0xe955ffff)

    if not contact_sheet.knob('Resolution_DevidedBy'):
        contact_sheet.addKnob(nuke.Int_Knob('Resolution_DevidedBy', 'Resolution DevidedBy'))
        contact_sheet['Resolution_DevidedBy'].setValue(1)

    contact_sheet['width'].setExpression('input.width * columns / Resolution_DevidedBy')
    contact_sheet['height'].setExpression('input.height * rows / Resolution_DevidedBy')
    contact_sheet['rows'].setExpression('(ceil(sqrt(inputs()) + 0.5))')
    contact_sheet['columns'].setExpression('(ceil(inputs() / rows))')

    for i, text_node in enumerate(text_nodes):
        contact_sheet.setInput(i, text_node)

    avg_x = sum(node.xpos() for node in text_nodes) // len(text_nodes)
    contact_sheet.setXpos(avg_x)
    contact_sheet.setYpos(ypos + 600)

    nuke.selectAll()
    nuke.zoomToFitSelected()

    #nuke.message(f"Imported {len(read_nodes)} MP4s from {folder_path}.")


# Version 18
