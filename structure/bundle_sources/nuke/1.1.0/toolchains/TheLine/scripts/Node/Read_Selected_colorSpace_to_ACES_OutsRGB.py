import nuke

a = nuke.selectedNodes()
for i in a: 
    i.knob("colorspace").setValue("Output - sRGB")


    