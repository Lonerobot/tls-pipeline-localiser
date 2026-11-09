
import nuke

frame = nuke.frame()
hold = nuke.createNode("FrameHold")
hold["first_frame"].setValue(frame)





