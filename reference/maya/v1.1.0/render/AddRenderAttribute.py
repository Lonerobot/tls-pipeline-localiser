import pymel.core.general as pmc

def addArnoldAttr(sObjs):
    ATTR_LONG_NAME = 'mtoa_constant_card_texture_path'
    if sObjs:
        for obj in sObjs:
            shp = obj.getShape() 
            if not pmc.attributeQuery( ATTR_LONG_NAME , node=shp, exists=True):
                pmc.addAttr(shp, longName=ATTR_LONG_NAME, dt="string" )
            print ("Attribute already exists on {} - Skipping...".format(shp.name()))
        
def doit():
    selectedObjs = pmc.selected()
    if selectedObjs:
        addArnoldAttr(selectedObjs) 
    else:
        print ("Please select some objects!")


