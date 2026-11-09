


import nuke

margin = 200
xpMax = nuke.selectedNode().xpos()
xpMin = nuke.selectedNode().xpos()
ypMax = nuke.selectedNode().ypos()
ypMin = nuke.selectedNode().ypos()
 
for a in nuke.selectedNodes():
    if a.xpos() > xpMax:
        xpMax = a.xpos()
    if a.xpos() < xpMin:
        xpMin = a.xpos()
    if a.ypos() > ypMax:
        ypMax = a.ypos()
    if a.ypos() < ypMin:
        ypMin = a.ypos()
 
bd = nuke.nodes.BackdropNode(bdwidth=(xpMax-xpMin)+margin, bdheight=(ypMax-ypMin)+margin) 
bd.setXpos(xpMin-margin//2)
bd.setYpos(ypMin-margin//2)

##Create name input pannel
p = nuke.Panel("Name")
p.addSingleLineInput('Name',"")
p.addSingleLineInput('Font Size',"100")
ret = p.show()    
name1 = p.value('Name') 
size = p.value('Font Size') 
name = name1.upper()

bd["label"].setValue(name)
bd["note_font_size"].setValue(int(size))














