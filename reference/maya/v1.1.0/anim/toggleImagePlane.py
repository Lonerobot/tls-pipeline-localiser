import maya.cmds as cmds

def doit():
    selCam = cmds.ls(sl = True)
    camShape = cmds.listRelatives(selCam, type='camera', fullPath=True)

    if camShape:
        imagePlanes = cmds.listConnections(camShape[0], type="imagePlane") or []
        
        print (f'{selCam[0]} imagePlanes {imagePlanes}')

        if imagePlanes:
            for ip in imagePlanes:
                ImageName = ip.split('>')[+1]
                if cmds.getAttr(str(ImageName) + '.visibility') == 1:
                    cmds.setAttr(str(ImageName) + '.visibility', 0)
                elif cmds.getAttr(str(ImageName) + '.visibility') == 0:
                    cmds.setAttr(str(ImageName) + '.visibility', 1)
    else:
        cmds.inViewMessage( message="Please Select a Camera",
            fade=True, position="midCenter", fontSize=16,
            fadeStayTime=1000, fadeOutTime=100,
            dragKill=True, bkc=0x00154060, alpha=0.7)


if __name__ == "__main__":
    doit()
