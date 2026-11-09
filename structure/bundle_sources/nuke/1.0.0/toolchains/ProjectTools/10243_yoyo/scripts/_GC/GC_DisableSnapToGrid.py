import nuke

nuke.toNode("preferences").knob('dag_snap_threshold').setValue(7)
nuke.toNode("preferences").knob('SnapToGrid').setValue(0)