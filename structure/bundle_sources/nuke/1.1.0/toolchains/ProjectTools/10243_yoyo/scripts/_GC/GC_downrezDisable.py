import nuke

for n in nuke.selectedNodes():
    n['disable'].setExpression('[if {[python -eval {nuke.activeViewer().node()[\'downrez\'].value()}]== 1} {return "curve"} else {return "1"}]')