from maya import cmds

def fix_shape_nodes():
    all = cmds.ls(sl=True, dag=True, shapes=True)
    if all:
        for shape in all:
            cmds.rename(shape, "{0}Shape".format(cmds.listRelatives(shape, parent=True)[0]))
    else:
        cmds.inViewMessage( message=f"Please select a group",
        fade=True, position="midCenter", fontSize=16,
        fadeStayTime=1000, fadeOutTime=100,
        dragKill=True, bkc=0x00154060, alpha=0.7)

if __name__ == '__main__':
        fix_shape_nodes()