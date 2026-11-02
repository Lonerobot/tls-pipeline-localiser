import maya.cmds as cmds

def doit():
      
    attr_list = ["tx", 
    "ty", 
    "tz",
    "rx",
    "ry",
    "rz",
    "sx",
    "sy",
    "sz",
    ]

    selection = cmds.ls( selection=True )

    if selection:
        for obj in selection:
            for a in attr_list:
                cmds.setAttr(f'{obj}.{a}', lock=False, keyable=True,)
    else:
        cmds.inViewMessage( message=f"Unlocked Attributes on Selection",
        fade=True, position="midCenter", fontSize=16,
        fadeStayTime=1000, fadeOutTime=100,
        dragKill=True, bkc=0x00154060, alpha=0.7)

if __name__ == "__main__":
    doit()

