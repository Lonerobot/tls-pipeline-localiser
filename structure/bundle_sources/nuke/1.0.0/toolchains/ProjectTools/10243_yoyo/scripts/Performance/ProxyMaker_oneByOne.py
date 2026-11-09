
import nuke

root = nuke.root()["name"].value() 
rootShot = root.split("/").pop()  
scriptName = root.split("/").pop().split(".").pop(0)
renderPath = root.replace(rootShot, "renders/nuke/proxys/")


for i in nuke.selectedNodes():

    file = i.knob('file')
    print(file)
       
    if file == None :
        print("no")

        name = i.knob('name').getValue() 
        print(name)
        
    else:
        print("yes")
       
        filePath = i.knob('file').getValue() 
        name = filePath.split("/").pop().split(".").pop(0)
        print(name )

    ff = int(nuke.Root()['first_frame'].getValue(0))
    lf = int(nuke.Root()['last_frame'].getValue(0))

    x = i['xpos'].value()
    y = i['ypos'].value()

    channels = ["rgba","all","rgb"]
    p = nuke.Panel("Proxy settings")
    p.addSingleLineInput('Name', name)
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

    fileName = name +"_%04d.exr"
    print(fileName)

    writePath = renderPath + scriptName + "_" + fileName 

    r = nuke.createNode("Reformat")
    r['xpos'].setValue( float(x) )
    r['ypos'].setValue( float(y-100) )
    r["type"].setValue("scale")
    r["scale"].setValue(res)

    w = nuke.createNode("Write")    
    w['xpos'].setValue( float(x) )
    w['ypos'].setValue( float(y-150) )  
    w["file"].setValue( writePath )
    w["channels"].setValue(chan)
    w["file_type"].setValue("exr")
    w["compression"].setValue("DWAA")
    w["autocrop"].setValue(1)
    w["create_directories"].setValue(1)
    nuke.execute(w,int(ff),int(lf))  

    nuke.delete(r)
    nuke.delete(w)

    r = nuke.createNode('Read')
    r['file'].setValue( writePath )
    r["localizationPolicy"].setValue("on")
    r['xpos'].setValue( float(x) )
    r['ypos'].setValue( float(y-100) )
 

    

  
    
    




