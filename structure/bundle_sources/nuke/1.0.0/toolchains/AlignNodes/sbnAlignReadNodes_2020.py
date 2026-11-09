# ------------------------------
# sbnAlignReadNodes_2020 v1.14 (production clean)
# ------------------------------

import nuke
from operator import itemgetter

# initialize toggle at module import
glToggleRS = 0   # 0 -> horizontal, 1 -> zigzag, 2 -> vertical


def getBaseName(sFullFileName):
    aSplit = sFullFileName.split("/")[-1:]
    return aSplit[0]


def sbnAlignNodes(sMode):
    """
    Align selected Read nodes by filename sort, in the given mode:
      'horizontal', 'vertical', 'zigzag', or 'default' (cycles)
    """
    global glToggleRS

    oNodes = nuke.selectedNodes()            # any class
    oNodesReader = nuke.selectedNodes("Read")  # only reads

    # Nothing selected
    if len(oNodes) == 0:
        return

    # Mixed selection (not all Reads) -> autoplace and exit
    if len(oNodesReader) != len(oNodes):
        for oNode in oNodes:
            oNode.autoplace()
        return

    # Collect info for sorting & positioning
    aList = []  # [idx, baseName, nodeName, file, xpos, ypos]
    for i, oNode in enumerate(oNodes):
        if oNode.Class() == "Read":
            sNodeName = oNode.name()
            sFile = oNode['file'].getValue()
            sBaseName = getBaseName(sFile)
            xpos = oNode.xpos()
            ypos = oNode.ypos()
            aList.append([i, sBaseName, sNodeName, sFile, xpos, ypos])

    if not aList:
        return

    # Sorts
    aListSortedBasename = sorted(aList, key=itemgetter(1))
    aListSortedXPos     = sorted(aList, key=itemgetter(4))
    aListSortedYPos     = sorted(aList, key=itemgetter(5))

    xpos = aListSortedXPos[0][4]
    ypos = aListSortedYPos[0][5]
    yposStart = ypos

    # Toggle logic for 'default'
    if sMode == "default":
        if glToggleRS == 0:
            sMode = "horizontal"
        elif glToggleRS == 1:
            sMode = "zigzag"
        elif glToggleRS == 2:
            sMode = "vertical"
        glToggleRS = (glToggleRS + 1) % 3

    # Move nodes in filename order
    for oItem in aListSortedBasename:
        nodeName = oItem[2]
        oNode = nuke.toNode(nodeName)
        if not oNode:
            continue

        try:
            oNode['selected'].setValue(True)
        except Exception:
            pass

        oNode.setXYpos(int(xpos), int(ypos))

        # step for next (your new spacing values)
        if sMode == "horizontal":
            xpos += 220
        elif sMode == "vertical":
            ypos += 144
        elif sMode == "zigzag":
            xpos += 100
            ypos -= 100
            if ypos < (yposStart - 300):
                ypos = yposStart
