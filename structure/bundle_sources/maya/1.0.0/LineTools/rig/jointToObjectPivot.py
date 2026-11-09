import pymel.core as pm

def create_joint_at_object_pivot(objs): 
    for geo in objs:        
        sWM = geo.getMatrix(worldSpace=True)    
        pm.select(clear=True)   
        jnt = pm.joint()
        jnt.setMatrix(sWM, worldSpace=True)

def doit():

    if pm.selected():
        create_joint_at_object_pivot(pm.selected())
    else:
        pm.inViewMessage( message=f"Please select an object",
        fade=True, position="midCenter", fontSize=16,
        fadeStayTime=1000, fadeOutTime=100,
        dragKill=True, bkc=0x00154060, alpha=0.7)

if __name__ == "__main__":
    doit()

