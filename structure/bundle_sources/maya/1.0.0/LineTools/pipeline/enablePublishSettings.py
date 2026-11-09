import maya.cmds as cmds

def doit():
    
    scene_sets = cmds.listSets( allSets=True )
    set_params = ["keepImages","writeColorSets"]

    for opSet in scene_sets:
        for param in set_params:
            attr_path = "{0}.{1}".format (opSet, param)
            if cmds.objExists(attr_path):
                cmds.setAttr (attr_path, 1)
                print ( "Set {0} to ON for {1}".format(param, opSet))    

if __name__ == "__main__":
    doit()

