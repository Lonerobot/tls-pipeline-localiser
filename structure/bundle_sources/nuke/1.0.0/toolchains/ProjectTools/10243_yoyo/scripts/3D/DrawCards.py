import nuke

import math

num = 100




for i in range(num):
    a = nuke.nodes.Card2()
    a.autoplace()
    a["rows"].setValue(1)
    a["columns"].setValue(1)
    a["image_aspect"].setValue(0)
    a["display"].setValue("wireframe")
    a["translate"].setValue( (math.sin(i)*300) , 0 )
    a["translate"].setValue( (math.cos(i)*300) , 1 )
    a["translate"].setValue( (math.cos(i)*300) , 2 )
    a["uniform_scale"].setValue(100)     




