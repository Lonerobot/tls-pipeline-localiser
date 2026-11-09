import nuke

v = 0.3
x = 3 
sum = v/x*10
print(sum )

root = nuke.root()["name"].value() 
rootShot = root.split("/").pop()  
scriptName = root.split("/").pop().split(".").pop(0)
renderPath = root.replace(rootShot, "renders/nuke/proxys/")


for i in nuke.selectedNodes():

    sourceWidth = i.width() 
    sourceHeight = i.height()

    #filePath = i.knob('file').getValue() 
    #fileName = filePath.split("/").pop().split(".").pop(0)+"_%04d.exr"  


    #first = i.knob('first').getValue() 
    #last = i.knob('last').getValue() 

    ff = int(nuke.Root()['first_frame'].getValue(0))
    lf = int(nuke.Root()['last_frame'].getValue(0))

    x = i['xpos'].value()
    y = i['ypos'].value()

    channels = ["rgba","all","rgb"]
    p = nuke.Panel("Proxy settings")
    p.addSingleLineInput('Name', "")
    p.addSingleLineInput('Resolution', 1)
    p.addEnumerationPulldown('Channels', channels)
    p.addSingleLineInput('firstFrame', ff)
    p.addSingleLineInput('lastFrame', lf)
    p.addButton('Cancel')
    p.addButton('OK')

    ret = p.show()

    name = p.value('Name') 
    res = p.value('Resolution') 
    res = float(res)
    chan = p.value('Channels') 
    chan = str(chan)
    chan = chan.split("'").pop(1)
    ff = p.value('firstFrame')
    lf = p.value('lastFrame')


    r = nuke.createNode("Reformat")
    #r.setInput(0,i)
    r['xpos'].setValue( float(x) )
    r['ypos'].setValue( float(y+100) )
    r["type"].setValue("scale")
    r["scale"].setValue(res)

    w = nuke.createNode("Write")    
    #w.setInput(0,i)
    w['xpos'].setValue( float(x) )
    w['ypos'].setValue( float(y+150) )  
    w["file"].setValue(renderPath + scriptName + "_" + name + "_%04d.exr" )
    w["channels"].setValue(chan)
    w["file_type"].setValue("exr")
    w["compression"].setValue("DWAA")
    w["autocrop"].setValue(1)
    w["create_directories"].setValue(1)
    nuke.execute(w,int(ff),int(lf))  
    w["reading"].setValue(1)
    w["checkHashOnRead"].setValue(0)
    

    r = nuke.createNode("Reformat")
    #r.setInput(0,i)
    r['xpos'].setValue( float(x) )
    r['ypos'].setValue( float(y+300) )
    r["type"].setValue("scale")
    r["scale"].setValue(1)
    r["filter"].setValue("impulse")
    
    

    #nuke.execute(w,int(first),int(last))   
    
    #i["localizationPolicy"].setValue("on")

    #nuke.delete(r)
    #nuke.delete(w)