import nuke

a = nuke.selectedNode()
first = a.knob("first").value()
last = a.knob("last").value()

nuke.root()['first_frame'].setValue(first)
nuke.root()['last_frame'].setValue(last)
