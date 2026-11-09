""" lockNde v1.1
	created 10th may 2012
	for bugs and reports: satheesrev@gmail.com
	To lock & unlock nuke knobs inside the nuke current session.

	menu.py lines.
nuke.menu("Properties").addCommand('lock_knobs', "lockNode.lock_knobs()")
nuke.menu("Properties").addCommand('unlock_knobs', "lockNode.unLock_knobs()")

def oc():
  nodes = nuke.allNodes()
  for selNode in nodes:
    selNode.setSelected(True)
    allknobs=selNode.allKnobs()
    label = selNode['label'].getValue()
    labCheck = label.rsplit(None, 1)[-1]
    if labCheck == 'Node_Locked':
      for knob in allknobs:
          knob.setEnabled(False)
nuke.addOnScriptLoad(oc)
"""

import nuke

def lock_knobs():
    selNode = nuke.selectedNode()
    allknobs=selNode.allKnobs()
    for knob in allknobs:
          knob.setEnabled(False)
    labelVal = selNode['label'].getValue()
    labCheck = labelVal.rsplit(None, 1)
    if labCheck:
      labCheck = labCheck[-1]
    if labCheck == 'Node_Locked':
        return
    else:   
        selNode['label'].setValue(labelVal+'\nNode_Locked')



def unLock_knobs():
    selNode = nuke.selectedNode()
    allknobs=selNode.allKnobs()
    for knob in allknobs:
          knob.setEnabled(True)

    labelVal = selNode['label'].getValue()
    labCheck = labelVal.rsplit(None, 1)
    if labCheck:
      labCheck = labCheck[-1]
    if labCheck == 'Node_Locked':
        newLabel = " ".join(labelVal.split()[:-1])
        selNode['label'].setValue(newLabel)
    else:
      return
    