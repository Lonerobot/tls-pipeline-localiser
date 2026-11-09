
import nuke

reads = nuke.selectedNodes()
list = []
for i in reads:
    n = reads
    file = i["file"].value()
    newChannel = file.split("/").pop().split(".").pop(0)
    print(newChannel)

    ss = nuke.nodes.ShuffleCopy()
    list.append(ss)
    ss.setInput(0,i)
    ss.setInput(1,i)

# Add channel via tcl, can't do via python
    cmd = "add_layer {%s " % newChannel
    for each in ["r", "g", "b", "a"]: 
      cmd += "%s.%s " % (newChannel, each)
   
    cmd += "}"
   
    nuke.tcl(cmd)


# Set knobs on the shuffle
    ss["out"].setValue(newChannel)
    ss["out2"].setValue('rgba') 
    ss["red"].setValue("red")
    ss["green"].setValue("green")
    ss["blue"].setValue("blue") 
    ss["alpha"].setValue("alpha")
    ss["black"].setValue("red2")
    ss["white"].setValue("green2") 
    ss["red2"].setValue("blue2")
    ss["green2"].setValue("alpha2")  
    ss["label"].setValue("[knob this.out]")











def autoSC():
   readers = nuke.selectedNodes()
   
   sclist = []
   for i in range(len(readers)):
     n = readers
     f = n["file"].value()
     newChannel = f.split("/").pop().split(".").pop(0).split("_")[-1]
     
     ss = nuke.nodes.ShuffleCopy()
     sclist.append(ss)
     ss.setInput(0, sclist[i-1])
     ss.setInput(1, n)
   
   
     # Add channel via tcl, can't do via python
     cmd = "add_layer {%s " % newChannel
     for each in ["r", "g", "b", "a"]: 
       cmd += "%s.%s " % (newChannel, each)
   
     cmd += "}"
   
     nuke.tcl(cmd)
   
     # Set knobs on the shuffle
     ss["out"].setValue(newChannel)
     ss["out2"].setValue('rgba') 
     ss["red"].setValue("red")
     ss["green"].setValue("green")
     ss["blue"].setValue("blue") 
     ss["alpha"].setValue("alpha")
     ss["black"].setValue("red2")
     ss["white"].setValue("green2") 
     ss["red2"].setValue("blue2")
     ss["green2"].setValue("alpha2")
   
     ss["label"].setValue("[knob this.out]")


autoSC()