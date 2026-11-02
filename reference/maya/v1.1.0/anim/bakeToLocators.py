import maya.cmds as cmds

def bake_to_locators(selected_objects):
    # Get total number of frames in the timeline
    start_frame = int(cmds.playbackOptions(query=True, animationStartTime=True))
    end_frame = int(cmds.playbackOptions(query=True, animationEndTime=True))

    # Iterate through each selected object
    for obj in selected_objects:
        # Create a new locator for the current object
        locator = cmds.spaceLocator(name=obj+"_bakedLocator")[0]

        # Iterate through each frame
        for frame in range(start_frame, end_frame + 1):
            # Go to the current frame
            cmds.currentTime(frame, edit=True)

            # Get world space matrix of the selected object
            world_matrix = cmds.xform(obj, query=True, matrix=True, worldSpace=True)

            # Apply world space matrix to locator
            cmds.xform(locator, matrix=world_matrix, worldSpace=True)

            # Keyframe the locator's transformation
            cmds.setKeyframe(locator, time=frame)

    print("Baking completed successfully.")

def doit():

    # Check if there are selected objects
    selected_objects = cmds.ls(selection=True)
    if selected_objects:
        bake_to_locators(selected_objects)
    else:
        cmds.inViewMessage( message=f"Please select at least one object.",
        fade=True, position="midCenter", fontSize=16,
        fadeStayTime=1000, fadeOutTime=100,
        dragKill=True, bkc=0x00154060, alpha=0.7)

if __name__ == "__main__":
    doit()