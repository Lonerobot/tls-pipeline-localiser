import nuke

s = nuke.selectedNodes()
r = s[0]
m = nuke.createNode("Merge2")
m.setInput(1,r)
m.setInput(0,r)
 



