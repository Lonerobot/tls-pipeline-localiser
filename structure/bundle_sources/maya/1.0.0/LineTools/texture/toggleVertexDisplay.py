import maya.cmds as cmds

def doit(): 
    """
    """   

    if cmds.polyOptions( q=True, colorShadedDisplay=True)[0]:
        cmds.polyOptions( colorShadedDisplay=False )
    else:
        cmds.polyOptions( colorShadedDisplay=True)  

if __name__ == "__main__":
    doit()
