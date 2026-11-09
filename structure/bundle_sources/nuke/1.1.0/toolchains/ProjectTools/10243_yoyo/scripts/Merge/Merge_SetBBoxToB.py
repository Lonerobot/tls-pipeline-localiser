import nuke

for s in nuke.selectedNodes("Merge2"):
            s['bbox'].setValue(3)