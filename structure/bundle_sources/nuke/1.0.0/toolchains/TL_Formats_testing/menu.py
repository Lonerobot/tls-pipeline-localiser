import nuke

#nuke.addFormat('3072 1728 3K')   # width height name

# "w h left bottom right top pixelAspect name"
nuke.addFormat('3072 1728 0 0 3072 1728 1.0 3K')

# Set the default label for all newly created TimeClips
nuke.knobDefault('TimeClip.label', '[value first]-[value last]')

# shuffle dynamic input1 displays
nuke.knobDefault('Shuffle2.label', '[value in1]')


print ("TL_Formats_testing")



