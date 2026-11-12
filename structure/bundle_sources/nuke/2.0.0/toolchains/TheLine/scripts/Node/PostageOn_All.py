import nuke

for a in nuke.allNodes():
    try:
        a['postage_stamp'].setValue(1)
    except:
        pass