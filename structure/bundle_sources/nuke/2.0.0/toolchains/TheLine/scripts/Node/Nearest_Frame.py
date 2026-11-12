import nuke

ns = nuke.selectedNodes()

for i in ns :
    i.knob("on_error").setValue(3)
    i.knob("frame_mode").setValue(1)
    i.knob("frame").setValue("0")


