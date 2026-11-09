import nuke

merge = []
image = nuke.selectedNodes()
count = 0
num = len(image)

p = nuke.Panel('my custom panel')
p.addEnumerationPulldown('operations', 'over plus screen overlay multiply ')
ret = p.show()
op = p.value('operations')

for i in image:
    x = i['xpos'].value()
    y = i['ypos'].value()
   
    m = nuke.nodes.Merge2()    
    m.setInput(1,i)
    m['xpos'].setValue( float(x) )
    m['ypos'].setValue( float(y+120) )
    m.knob("operation").setValue(op)

    merge.append(m)

for a in merge:

    count = count + 1   
    if count == num:
        print(nuke.message("done bruv"))  
    else:  
        a.setInput(0,merge[count])
        #print(nuke.message(str(count)))


 









