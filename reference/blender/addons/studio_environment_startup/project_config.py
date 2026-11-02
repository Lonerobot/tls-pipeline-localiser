'''
  _____ _  _ ___   _	___ _  _ ___			
 |_   _| || | __| | |  |_ _| \| | __|   		
_______________________________________          
   |_| |_||_|___| |____|___|_|\_|___|   		
                                                
    _   _  _ ___ __  __   _ _____ ___ ___  _  _ 
   /_\ | \| |_ _|  \/  | /_\_   _|_ _/ _ \| \| |
  / _ \| .` || || |\/| |/ _ \| |  | | (_) | .` |
 /_/ \_\_|\_|___|_|  |_/_/ \_\_| |___\___/|_|\_|
                                                
Project Config

A set of classes and functions to handle project specific tasks

'''

import logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
logger.addHandler(logging.StreamHandler())

import os
import bpy
import addon_utils
from pathlib import Path

class ProjectConfig():
    @staticmethod
    def set_asset_library():
        """
        in the project_settings/global/project_environments area 
        there needs to be a path set on the environment variable BLENDER_PROJECT_ASSETLIB
        
        "BLENDER_PROJECT_ASSETLIB": "[path to project library]"

        """
        project_asset_dir = os.getenv("BLENDER_PROJECT_ASSETLIB")
        lib_name = "PROJECT_ASSETS"
        lib_exists = False    

        if project_asset_dir and Path (project_asset_dir).exists():
            for b in bpy.context.preferences.filepaths.asset_libraries:
                if lib_name in b.name:
                    lib_exists = True  
            
            if not lib_exists:        
                bpy.ops.preferences.asset_library_add()
                new_library = bpy.context.preferences.filepaths.asset_libraries[-1]
                new_library.name = lib_name
                new_library.path = project_asset_dir
                new_library.import_method = "LINK"
                logger.debug(f'Project Environment found [BLENDER_PROJECT_ASSETLIB] - Added Project Asset Library : {project_asset_dir}')
            else:
                logger.debug(f'The [PROJECT_ASSETS] Library is already present : {project_asset_dir}')
        else:
            logger.debug(f'The Project Asset Library doesn\'t exist, please set BLENDER_PROJECT_ASSETLIB in OpenPype in order to use the Asset Library : {project_asset_dir}')


    @staticmethod
    def enable_startup_addons():
        """
        Enable Blender addon
        version specific code cold be done with 
            if '3.5' in bpy.app.version_string:
        but we will use env vars to specify the addons    

        there are 2 vars that need to be registered in the OpenPype config - 

            BLENDER_GLOBAL_ADDONS 
            
            In the main blender settings, useful for more global things like Flamenco and Node wrangler

            BLENDER_STARTUP_ADDONS

            If there are specific addons required from a particular version, 
            these are specified in BLENDER_STARTUP_ADDONS on the Blender version.
            Perhaps this could move to the actual project??
        """
        startup_addons = []

        global_addons = os.getenv('BLENDER_GLOBAL_ADDONS')

        if global_addons:
            for sao in global_addons.split(';'):        
                startup_addons.append(sao)
                logger.debug(f'Global Environment - Startup Addon Found : {sao}')

        env_addons = os.getenv('BLENDER_STARTUP_ADDONS')
        if env_addons:
            for eao in env_addons.split(';'):        
                startup_addons.append(eao)
                logger.debug(f'Version Environment - Startup Addon Found : {eao}')

        for ao in startup_addons:
            if addon_utils.check(ao)[0]:
                logger.debug(f'Startup Addon is already enabled : {ao}')
            else:
                try:
                    addon_utils.enable(ao, default_set=True, persistent=True) 
                    logger.debug(f'Startup Addon Loaded : {ao}')         
                except ModuleNotFoundError:
                    logger.error(f'There was a problem enabling the {ao} addon')

