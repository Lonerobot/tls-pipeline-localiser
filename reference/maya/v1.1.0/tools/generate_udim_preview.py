import maya.cmds as cmds

def doit():    
    [cmds.ogs(regenerateUVTilePreview=x) for x in cmds.ls(type="file")]
    
if __name__ == "__main__":
    doit()
