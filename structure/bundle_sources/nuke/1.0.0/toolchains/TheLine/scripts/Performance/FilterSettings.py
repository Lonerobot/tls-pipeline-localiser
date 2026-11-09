import nuke

filt = [ "High" , "Low" ]



p = nuke.Panel("Transform Filtering")
#p.addEnumerationPulldown('filters', filt )
p.addButton('High')
p.addButton('Cancel')
p.addButton('Low')
p.addNotepad('What this does',"Changes all the blurs , transforms and the scanline render quality settings to be Low or High")

#f = p.value('filters') 
#f = str(f)
#f = f.split("'").pop(1)
ret = p.show()
print(ret)


if ret == 2:

## Transforms
    for s in nuke.allNodes():
        classTypes = ['Transform' , 'CornerPin2D', 'Reformat', 'CameraShake3']
        for n in classTypes:
            if n in s.Class():
                s['filter'].setValue("Impulse")

##Blurs

    for s in nuke.allNodes():
        classTypes = ['Blur',]
        for n in classTypes:         
            if n in s.Class():
                s['filter'].setValue("box")

    for s in nuke.allNodes():
        classTypes = ['Blur', 'Defocus']
        for n in classTypes:
            if n in s.Class():
                s['quality'].setValue(5)

##scanLine

    for s in nuke.allNodes():
        classTypes = ['ScanlineRender']
        for n in classTypes:
            if n in s.Class():
                s['filter'].setValue(11)

    for s in nuke.allNodes():
        classTypes = ['ScanlineRender']
        for n in classTypes:
            if n in s.Class():
                s['antialiasing'].setValue("none")





if ret == 0:

## Transforms

    for s in nuke.allNodes():
        classTypes = ['Transform' , 'CornerPin2D', 'Reformat', 'CameraShake3', "ScanlineRender"]
        for n in classTypes:
            if n in s.Class():
                s['filter'].setValue("Cubic")

##Blurs

    for s in nuke.allNodes():
        classTypes = ['Blur']
        for n in classTypes:
            if n in s.Class():
                s['filter'].setValue("gaussian")

    for s in nuke.allNodes():
        classTypes = ['Blur', 'Defocus']
        for n in classTypes:
            if n in s.Class():
                s['quality'].setValue(15)

##scanLine


    for s in nuke.allNodes():
        classTypes = ['ScanlineRender']
        for n in classTypes:
            if n in s.Class():
                s['antialiasing'].setValue("high")