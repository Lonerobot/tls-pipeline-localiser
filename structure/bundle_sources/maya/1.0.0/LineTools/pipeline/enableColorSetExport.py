import maya.cmds as cmds

def doit():
    
    scene_sets = cmds.listSets( allSets=True )
    
    # opInstanceSets = [opSet for opSet in scene_sets if cmds.objExists("{0}.{1}".format (opSet, 'writeColorSets'))]
    # for anim_set in opInstanceSets:
    #     cmds.setAttr ("{0}.{1}".format (anim_set, 'writeColorSets'), 1)

    # I think this is a bit clearer to understand than the list comprehension and repeated format statements 
    # i.e. no way to specify a variable return in an LC
    for opSet in scene_sets:
        attr_path = "{0}.{1}".format (opSet, 'writeColorSets')
        if cmds.objExists(attr_path):
            cmds.setAttr (attr_path, 1)
            print ( "Set Write Color Sets to ON for {0}".format(opSet))        

if __name__ == "__main__":
    doit()

