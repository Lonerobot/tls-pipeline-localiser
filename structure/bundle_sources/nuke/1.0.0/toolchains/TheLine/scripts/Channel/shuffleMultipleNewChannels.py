
import nuke

nodes = nuke.selectedNodes()
fn = nodes[0]
m = nuke.nodes.Merge2()
m.knob("also_merge").setValue("all")
x = fn['xpos'].value()
y = fn['ypos'].value()
m['xpos'].setValue( float(x) )
m['ypos'].setValue( float(y+500) )


count = 4
   

for i in nodes:
    count = count + 1

    
    for n in nuke.allNodes():
        if n.Class() == "Viewer":
            n.setInput(0, i)     

    
    node = nuke.selectedNode()
    
    txt = nuke.getInput('matte name', '')
    print(txt)
    
    txt2 = "MatteExport_" + txt 
    
    ss = nuke.nodes.Shuffle()
    ss.setInput(0, i)
       
    # Add channel via tcl, can't do via python
    cmd = "add_layer {%s " % txt2
    for each in ["r", "g", "b", "a"]: 
        cmd += "%s.%s " % (txt2, each)
       
    cmd += "}"
       
    nuke.tcl(cmd)
    
    # Set knobs on the shuffle
    ss["out"].setValue(txt2)
    ss["out2"].setValue('rgba') 
    ss["red"].setValue("alpha")
    ss["green"].setValue("alpha")
    ss["blue"].setValue("alpha") 
    ss["alpha"].setValue("alpha")
    ss["black"].setValue("red2")
    ss["white"].setValue("green2") 
    ss["red2"].setValue("blue2")
    ss["label"].setValue("[knob this.out]")
    ss["green2"].setValue("alpha2")  

    #nuke.delete(view)



    m.setInput(count,ss)
    






