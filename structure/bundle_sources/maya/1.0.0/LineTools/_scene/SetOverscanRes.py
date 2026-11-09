import maya.cmds as cmds

OVERSCAN_WIDTH = 3372
OVERSCAN_HEIGHT = 2028
PIXEL_ASPECT = 1.0
DEVICE_ASPECT = 1.663

def setRes(w,h, pAx, pAr):
    cmds.setAttr("defaultResolution.aspectLock", 0)
    cmds.setAttr("defaultResolution.width", w)
    cmds.setAttr("defaultResolution.height", h)
    cmds.setAttr("defaultResolution.pixelAspect", pAx)
    cmds.setAttr("defaultResolution.deviceAspectRatio", pAr)

def apply():
    setRes(OVERSCAN_WIDTH,OVERSCAN_HEIGHT,PIXEL_ASPECT,DEVICE_ASPECT)

if __name__ == "__main__":
    apply()




