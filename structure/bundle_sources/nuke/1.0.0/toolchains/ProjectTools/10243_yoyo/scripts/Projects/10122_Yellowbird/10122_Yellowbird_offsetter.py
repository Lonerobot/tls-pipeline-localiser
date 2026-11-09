import nuke

def offset_all_read_nodes(offset):
    for node in nuke.selectedNodes():
        if node.Class() == 'Read':
            o = 1001 + float(offset)
            node['frame'].setValue(str(o));
ofst = nuke.getInput('Frame Offset', '0')
if ofst:
    offset_all_read_nodes(ofst)
    for n in nuke.selectedNodes():
        n.setSelected(False)
    for node in nuke.allNodes():
        if node.name() == 'renderCompositingMain':
            node.setSelected(True)
            i = node.input(0)
            node.setSelected(False)
            i.setSelected(True)
            t = nuke.createNode('TimeOffset', inpanel=False)
            t['time_offset'].setValue(-float(ofst));
