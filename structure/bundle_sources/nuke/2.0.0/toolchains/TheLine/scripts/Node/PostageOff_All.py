import nuke

for a in nuke.allNodes():
    try:
        a['postage_stamp'].setValue(0)
    except:
        pass