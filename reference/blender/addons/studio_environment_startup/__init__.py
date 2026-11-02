'''
  _____ _  _ ___   _	___ _  _ ___			
 |_   _| || | __| | |  |_ _| \| | __|   		
_______________________________________          
   |_| |_||_|___| |____|___|_|\_|___|   		
                                                
    _   _  _ ___ __  __   _ _____ ___ ___  _  _ 
   /_\ | \| |_ _|  \/  | /_\_   _|_ _/ _ \| \| |
  / _ \| .` || || |\/| |/ _ \| |  | | (_) | .` |
 /_/ \_\_|\_|___|_|  |_/_/ \_\_| |___\___/|_|\_|
                                                
Studio Environment Startup

'''

bl_info = {
    "name": "Studio Environment Startup",
    "description": "Performs a number of setup checks and registers pipeline file callback functions",
    "blender": (4, 2, 0),
    "category": "TheLine",
    "author": "Pete.Addington",
    "version": (1, 0, 1),
    "location": "",
    "doc_url": "https://www.thelineanimation.com/",
    "wiki_url":"https://www.thelineanimation.com",
}

import bpy
from bpy.app.handlers import persistent

# import custom modules to be called by the load handler
from .pre_render_checks import PreRenderChecks as PreRenderChecks
from .project_config import ProjectConfig as ProjectConfig

import logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
logger.addHandler(logging.StreamHandler())

@persistent
def scene_load_handler(scene):
    logger.debug(f'The Line - Studio Startup Callback enabled')
    ProjectConfig.enable_startup_addons() 
    PreRenderChecks.check_for_shot_override()
    ProjectConfig.set_asset_library() 
  
def register():
    bpy.app.handlers.load_post.append(scene_load_handler)
   
def unregister():
    bpy.app.handlers.load_post.remove(scene_load_handler)

if __name__ == "__main__":
    register()
    logger.debug(f'The Line - Checking Addons')
    ProjectConfig.enable_startup_addons()   






        
    
    