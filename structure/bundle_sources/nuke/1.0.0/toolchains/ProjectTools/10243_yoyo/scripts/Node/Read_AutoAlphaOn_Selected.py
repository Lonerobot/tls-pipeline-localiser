import nuke

a = nuke.selectedNodes()
for i in a: 
    i.knob("auto_alpha").setValue(1)


