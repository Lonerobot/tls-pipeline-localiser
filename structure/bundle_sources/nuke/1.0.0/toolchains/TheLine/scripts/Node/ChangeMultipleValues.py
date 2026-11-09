
import nuke

## Get Selected nodes Classes ##

sel = []

for i in nuke.selectedNodes():
    a = i.Class()
    sel.append(a)

selUniq = list(set(sel))

## Node class Panel 1

p = nuke.Panel("Class")
p.addEnumerationPulldown('Class', selUniq)
p.addButton('Cancel')
p.addButton('OK')
ret = p.show()


## Get Panel 1 Inputs and clean them up 

ab = p.value('Class') 
bc = str(ab)
nodeClass = bc.split("'").pop(1)
print(nodeClass)

## Get Available Knobs

kn = []

for i in nuke.selectedNodes():
        if i.Class() == str(nodeClass):
            for a in i.knobs():   
                kn.append(a)
        else:
            print("notclass")

knobUniq = list(set(kn))
knobUniq.sort()

# Change Value pannel 2

p = nuke.Panel("ChangeValues")
p.addEnumerationPulldown('Knob', knobUniq)
p.addSingleLineInput('New Value', "")
p.addButton('Cancel')
p.addButton('Change Selected Class')
p.addButton('Change All Class')
ret = p.show()

## Get Panel 2 Inputs and clean them up 

newVal = p.value('New Value') 
knobType = p.value('Knob') 
t = str(knobType)
b = t.split("'").pop(1)

## Apply input value to selected Class

if ret == 1:   

    for i in nuke.selectedNodes():
        if i.Class() == str(nodeClass):   
            try:
                i[str(b)].setValue(float(newVal))
            except ValueError:
                i[str(b)].setValue(str(newVal))


## Apply input value to all class

if ret == 2:
    for i in nuke.allNodes():
        if i.Class() == str(nodeClass):
            try:
                i[str(b)].setValue(float(newVal))
            except ValueError:
                i[str(b)].setValue(str(newVal))