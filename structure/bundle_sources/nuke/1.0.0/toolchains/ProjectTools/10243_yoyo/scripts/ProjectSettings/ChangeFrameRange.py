import nuke

def changeFrameRange():
	if nuke.exists("CHARS_BEU"):
		charBeu = nuke.toNode("CHARS_BEU")
		startFrame =  charBeu["first"].value()
		endFrame =  charBeu["last"].value()
		nuke.root().knob('first_frame').setValue(startFrame)
		nuke.root().knob('last_frame').setValue(endFrame)

	else: 
		allReadNodes = nuke.allNodes('Read')
		for node in allReadNodes: 
			startFrame =  node["first"].value()
			endFrame =  node["last"].value()
			if  endFrame - startFrame >0:
				name =  node["name"].value()
				if nuke.ask('CHARS_BEU does not exist.\n\nDo you want to use node: ' + name + ' with range' + `startFrame` + ' - ' + `endFrame`):  
					nuke.root().knob('first_frame').setValue(startFrame)
					nuke.root().knob('last_frame').setValue(endFrame)
					break 

changeFrameRange()