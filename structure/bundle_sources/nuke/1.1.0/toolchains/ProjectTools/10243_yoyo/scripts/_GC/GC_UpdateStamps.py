import nuke

for n in nuke.allNodes('PostageStamp'):
  n.knob("label").setValue("")
  n.knob("note_font").setValue("Verdana Bold")
  n.knob("note_font_size").setValue(26)
  n.knob("hide_input").setValue(1)
  
  if n.input(0):
    if n.input(0).knob('label').value():
      n.knob("autolabel").setValue("nuke.thisNode().input(0).knob(\"label\").value()")
    else:
      n.knob("autolabel").setValue("' no input label'")
  else:
    n.knob("autolabel").setValue("n.name()")

