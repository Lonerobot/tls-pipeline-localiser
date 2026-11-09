import maya.cmds as cmds

def enable_in_view():
    try:
        [cmds.ogs(regenerateUVTilePreview=x) for x in cmds.ls(type="file")]
    except(e):
        print ({e})

if __name__ == "__main__":
    enable_in_view()