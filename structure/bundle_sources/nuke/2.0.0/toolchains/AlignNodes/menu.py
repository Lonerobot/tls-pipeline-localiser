import nuke
import sbnAlignReadNodes_2020 as sbn

#n = nuke.menu('Nodes')
n = nuke.menu('Nuke').addMenu('Edit/Align Read Nodes')

n.addCommand("Align Read Nodes",
             lambda: sbn.sbnAlignNodes('default'),
             "L",
             shortcutContext=2)

n.addCommand("Align Read Nodes (vertical)",
             lambda: sbn.sbnAlignNodes('vertical'),
             "shift+L",
             shortcutContext=2)

n.addCommand("Align Read Nodes (horizontal)",
             lambda: sbn.sbnAlignNodes('horizontal'))

n.addCommand("Align Read Nodes (zigzag)",
             lambda: sbn.sbnAlignNodes('zigzag'))
