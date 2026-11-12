
import nuke

root = nuke.root()["name"].value()
rootShot = root.split("/").pop()  
renderPath = root.replace(rootShot, "renders/nuke/proxies/")

for i in nuke.selectedNodes():

    nuke.execute(i,)

    sourceWidth = i.width() 
    sourceHeight = i.height()

    filePath = i.knob('file').getValue() 
    fileName = filePath.split("/").pop().split(".").pop(0)+"_%04d.exr"   

    first = i.knob('first').getValue() 
    last = i.knob('last').getValue() 

    x = i['xpos'].value()
    y = i['ypos'].value()

    #r = nuke.nodes.Reformat()
    #r.setInput(0,i)
    #r['xpos'].setValue( float(x) )
    #r['ypos'].setValue( float(y-100) )
    #r["type"].setValue("scale")
    #r["scale"].setValue(0.5)

    w = nuke.nodes.Write()    
    w.setInput(0,i)
    w['xpos'].setValue( float(x) )
    w['ypos'].setValue( float(y-150) )  
    w["file"].setValue(renderPath + fileName)
    w["channels"].setValue("rgba")
    w["file_type"].setValue("exr")
    w["compression"].setValue("DWAA")
    w["autocrop"].setValue(1)
    w["create_directories"].setValue(1)

    nuke.execute(w,int(first),int(last))   
  
    i["proxy"].setValue(renderPath + fileName)
    #i["proxy_format"].setValue("2737 1309 0 0 2737 1309 1 ")
    
    i["localizationPolicy"].setValue("on")

    #nuke.delete(r)
    nuke.delete(w)