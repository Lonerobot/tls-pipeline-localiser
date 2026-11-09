import nuke

n = nuke.selectedNode()

s = nuke.createNode("StickyNote")
txt = nuke.getInput('note', '')



s['label'].setValue(txt.upper())


x = n['xpos'].value()
y = n['ypos'].value()
  
s['xpos'].setValue( float(x+100) )
s['ypos'].setValue( float(y) )
s['note_font_size'].setValue(25)
s['bookmark'].setValue(1)
s['note_font'].setValue("1")
s['bookmark'].setValue("1")
s['tile_color'].setValue(0xd3d3d3ff)











