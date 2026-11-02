'''
  _____ _  _ ___   _	___ _  _ ___			
 |_   _| || | __| | |  |_ _| \| | __|   		
_______________________________________          
   |_| |_||_|___| |____|___|_|\_|___|   		
                                                
    _   _  _ ___ __  __   _ _____ ___ ___  _  _ 
   /_\ | \| |_ _|  \/  | /_\_   _|_ _/ _ \| \| |
  / _ \| .` || || |\/| |/ _ \| |  | | (_) | .` |
 /_/ \_\_|\_|___|_|  |_/_/ \_\_| |___\___/|_|\_|
                                                
Pre Render Checks

A set of classes and functions to make sure the Blender environment 
is configured correctly

Updated to function within Ayon Pipeline 

'''

import logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
logger.addHandler(logging.StreamHandler())

import os
import json
import bpy
from pathlib import Path

def loadJSONfromFile(file) -> dict:
    """
    returns a dict
    """
    with open(file, 'r') as myfile:
        data=myfile.read()
    return json.loads(data)

class PreRenderChecks():
    @staticmethod
    def check_for_shot_override():
        """
        Looks for a JSON template file named _shot_override.json in the OpenPype work directory. 

        THis will usually look like this -
        {
            "Settings": {
                "render.resolution_x": 7472,
                "render.resolution_y": 4494
            }
        }

        But it could have other criteria set here like render samples. The function is
        using setattr to apply the settings
        
        """
        from ayon_core.pipeline import context_tools 

        context = context_tools.get_current_context()     
        task =  context["task_name"]  
        work_dir = Path(os.environ["AYON_WORKDIR"]) 

        task_list = ["anim", "layout", "lookdev", "lighting"]
        
        override_template = None

        if any(x in task for x in task_list):
            task_override_file = work_dir / "_task_override.json"
            if task_override_file.exists():
                override_template = task_override_file
                override_type = "Task"

        if not override_template:    
            override_template = work_dir.parent / "_shot_override.json"
            override_type = "Shot"

        if override_template.exists():
            logger.debug (f'{task} {override_type} Override Template Found - {override_template}')
            override_settings = loadJSONfromFile(str(override_template))
            if override_settings['Settings']: 
                    logger.debug (f'Override Settings : {override_settings}')
                    scene = bpy.context.scene  

                    for key, value in override_settings['Settings'].items():
                        if "." in key:
                            attr1, attr2 = key.split('.')
                            logger.debug (f'Set Override : {attr1}.{attr2} : {value}')
                            setattr(getattr(scene, attr1), attr2, value)
                        else:
                            logger.debug (f'Set Override : {key} : {value} ')
                            setattr(scene, key, value)
        else:
            logger.debug (f'check_for_shot_override - No shot override found - keeping project resolution - {work_dir}') 