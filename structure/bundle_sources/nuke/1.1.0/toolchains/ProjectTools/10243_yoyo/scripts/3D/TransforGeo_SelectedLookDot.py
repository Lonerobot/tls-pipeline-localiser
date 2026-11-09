
import nuke

reads = nuke.selectedNodes() 

xPos = reads[0]['xpos'].value()
yPos = reads[0]['ypos'].value()

a = nuke.nodes.Dot()
a["hide_input"].setValue(1)
a.setXpos( int(xPos))
a.setYpos( int(yPos)+200 )

for i in reads:
    i.setInput(2, a)
















