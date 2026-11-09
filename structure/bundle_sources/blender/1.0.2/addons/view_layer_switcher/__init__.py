'''
  _____ _  _ ___   _	___ _  _ ___			
 |_   _| || | __| | |  |_ _| \| | __|   		
_______________________________________          
   |_| |_||_|___| |____|___|_|\_|___|   		
                                                
    _   _  _ ___ __  __   _ _____ ___ ___  _  _ 
   /_\ | \| |_ _|  \/  | /_\_   _|_ _/ _ \| \| |
  / _ \| .` || || |\/| |/ _ \| |  | | (_) | .` |
 /_/ \_\_|\_|___|_|  |_/_/ \_\_| |___\___/|_|\_|
                                                
View Layer Switcher

'''

bl_info = {
    "name": "View Layer Switcher",
    "description": "Easy navigation of view layers from the 3d view",
    "blender": (4, 2, 0),
    "category": "TheLine",
    "author": "Pete.Addington",
    "version": (1, 0, 2),
    "location": "3d View > N panel > Render Setup",
    "doc_url": "https://www.thelineanimation.com/",
    "wiki_url":"https://www.thelineanimation.com",
}

if "bpy" in locals():
    import importlib
    importlib.reload(properties)
    importlib.reload(op)
    importlib.reload(ui)
else:
    import bpy
    from . import properties
    from . import op
    from . import ui

def register():  
    properties.register()
    op.register()
    ui.register()

def unregister(): 
    ui.unregister() 
    op.unregister() 
    properties.unregister()
