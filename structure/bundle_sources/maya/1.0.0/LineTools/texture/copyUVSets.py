import maya.cmds as cmds

def doit():

    selectedObjs = cmds.ls(sl=True)
    selectedGeo = cmds.filterExpand( sm=12 )

    if selectedGeo:
        for each in selectedGeo:
            cmds.polyUVSet( currentUVSet=True,  uvSet='uv')
            cmds.polyUVSet( copy=True, nuv='map1', uvSet='uv' )
            cmds.polyUVSet( currentUVSet=True,  uvSet='uv')
            cmds.delete(each, constructionHistory = True)

        cmds.inViewMessage( message=f"Copied UV Sets to map1",
                fade=True, position="midCenter", fontSize=16,
                fadeStayTime=1000, fadeOutTime=100,
                dragKill=True, bkc=0x00154060, alpha=0.7)


if __name__ == "__main__":
    doit()
