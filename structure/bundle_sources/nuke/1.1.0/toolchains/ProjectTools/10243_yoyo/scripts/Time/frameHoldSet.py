#For more info visit www.harrisonly.co.uk
import nuke

#FrameHold with SetThisFrame
def frameHoldSet():
	n = nuke.thisNode()
	
	#Sets current frame on create
	n['first_frame'].setValue(nuke.frame())
	
	#Creates SetThisFrame button
	tabName = nuke.Tab_Knob("Set_This_Frame", "SetThisFrame")
	n.addKnob(tabName)
	scriptButton = nuke.PyScript_Knob("SetThisFrame", "SetThisFrame")
	n.addKnob(scriptButton)
	n.knob("SetThisFrame").setCommand("""node = nuke.thisNode()
node['first_frame'].setValue(nuke.frame()) """) 