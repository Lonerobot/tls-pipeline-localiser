#nuke.selectedNode().Class() 

import nuke

filters = ["cubic" , "impulse"]

p = nuke.Panel("Transform Filtering")
p.addEnumerationPulldown('filters', filters)
p.addButton('Cancel')
p.addButton('OK')
ret = p.show()

f = p.value('filters') 
f = str(f)
f = f.split("'").pop(1)

for i in nuke.allNodes():
        if i.Class() == str("Transform"):
            i["filter"].setValue(f)
  
for i in nuke.allNodes():
        if i.Class() == str("CornerPin2D"):
            i["filter"].setValue(f)

for i in nuke.allNodes():
        if i.Class() == str("Reformat"):
            i["filter"].setValue(f)

for i in nuke.allNodes():
        if i.Class() == str("CameraShake3"):
            i["filter"].setValue(f)
for i in nuke.allNodes():
        if i.Class() == str("ScanlineRender"):
            i["filter"].setValue(f)




