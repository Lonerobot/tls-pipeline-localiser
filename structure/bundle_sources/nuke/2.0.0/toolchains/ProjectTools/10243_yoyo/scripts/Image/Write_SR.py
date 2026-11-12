
import nuke

root = nuke.root()["name"].value()
rootShot = root.split("/").pop(-1)

if root == "":
    nuke.message('Need to save fist')
else:  
    shotNum = rootShot.split("_").pop(1)

path = "Y:/SECURE PROJECTS/10111_SRIRACHA/shots/" + shotNum + "/publish/comp/comp/movie/default/SR_" + shotNum + "_comp_default_v001.mov"

print(path) 
   
write = nuke.createNode("Write")    
write["file"].setValue(path)
write["meta_codec"].setValue(2)
write["file_type"].setValue("mov")
write["create_directories"].setValue(1)






















