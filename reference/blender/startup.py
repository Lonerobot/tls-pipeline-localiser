'''
  _____ _  _ ___   _	___ _  _ ___			
 |_   _| || | __| | |  |_ _| \| | __|   		
_______________________________________          
   |_| |_||_|___| |____|___|_|\_|___|   		
                                                
                                                
Enables the studio environment startup addon

Blender 5.0 Might defer this to adding a script directory instead

'''

# CRITICAL: Set QT_API before any imports that might use qtpy
# This must be done before AYON's code tries to import Qt
import os
os.environ['QT_API'] = 'pyside6'

import pathlib
import bpy 
import addon_utils
import logging
import subprocess
import sys
import tempfile
import shutil
import ctypes
from pathlib import Path

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
logger.addHandler(logging.StreamHandler())

STUDIO_CONFIG_ADDON = 'studio_environment_startup'

# BLENDER_CORE_ADDONS

def is_admin():
    """Check if the current process has admin privileges."""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False


def install_pyside6():
    """
    Check if PySide6 is installed in Blender's Python environment.
    This is needed for AYON to be able to run its Qt based UI.
    If not found, attempt to install with elevated privileges if needed.
    """
    try:
        import PySide6
        # Try to get version from PySide6.QtCore if available
        try:
            from PySide6 import QtCore
            logger.debug(f'PySide6 is already installed: {QtCore.__version__}')
        except (ImportError, AttributeError):
            logger.debug('PySide6 is already installed')
        return True
    except ImportError:
        logger.debug('PySide6 not found. Attempting installation...')
        
        # Get Blender's Python executable and site-packages location
        blender_binary = Path(bpy.app.binary_path)
        blender_install_dir = blender_binary.parent
        version_str = f"{bpy.app.version[0]}.{bpy.app.version[1]}"
        version_folder = blender_install_dir / version_str
        blender_python = version_folder / "python" / "bin" / "python.exe"
        site_packages = version_folder / "python" / "lib" / "site-packages"
        
        if not blender_python.exists():
            logger.error(f'Blender Python executable not found at: {blender_python}')
            return False
        
        try:
            # Try direct installation to Blender's site-packages
            logger.debug(f'Installing PySide6 to: {site_packages}')
            result = subprocess.run([
                str(blender_python),
                "-m", "pip", "install",
                "--target", str(site_packages),
                "PySide6"
            ], capture_output=True, text=True)
            
            if result.returncode == 0:
                logger.debug('PySide6 installed successfully')
                return True
            else:
                # Check if it's a permission error
                if "PermissionError" in result.stderr or "WinError 5" in result.stderr:
                    logger.warning('Permission denied. Attempting elevated installation...')
                    
                    # Request UAC elevation and run the pip install command
                    # This will prompt the user for admin approval
                    ret = ctypes.windll.shell32.ShellExecuteW(
                        None, 
                        "runas",  # Run as administrator
                        str(blender_python),
                        f'-m pip install --target "{site_packages}" PySide6',
                        None,
                        1  # SW_SHOWNORMAL
                    )
                    
                    if ret > 32:  # Success
                        logger.debug('Elevated installation initiated. Please approve the UAC prompt.')
                        logger.warning('Note: You may need to restart Blender after PySide6 installation completes.')
                        return True
                    else:
                        logger.error('Failed to request elevated privileges.')
                        return False
                else:
                    logger.error(f'Failed to install PySide6: {result.stderr}')
                    return False
                    
        except Exception as e:
            logger.error(f'Unexpected error installing PySide6: {e}')
            return False


def set_pipeline_location():
        """
        there needs to be a path set on the environment variable BLENDER_CORE_ADDONS
        
        "BLENDER_CORE_ADDONS": "[path to core addons]"
        """
        pipeline_dir = os.getenv("BLENDER_CORE_ADDONS")
        lib_name = "THELINE_PIPELINE"
        lib_exists = False    

        if pipeline_dir and Path (pipeline_dir).exists():
            for b in bpy.context.preferences.filepaths.script_directories:
                if lib_name in b.name:
                    lib_exists = True  
            
            if not lib_exists:    
                pipeline_location = bpy.context.preferences.filepaths.script_directories.new()
                pipeline_location.name = lib_name
                pipeline_location.directory = pipeline_dir

                logger.debug(f'THE LINE Pipeline environment found [BLENDER_CORE_ADDONS] - Added new script directory : {pipeline_dir}')
            else:
                logger.debug(f'THE LINE Pipeline is already defined, moving on to the startup procedure : {pipeline_dir}')
        else:
            logger.debug(f'THE LINE Pipeline wasn\'t found, please set BLENDER_CORE_ADDONS in AYON in order to use the studio pipeline tools : {pipeline_dir}')


def enable_startup_addon():

    if addon_utils.check(STUDIO_CONFIG_ADDON)[0]:
        logger.debug(f'Startup Addon Loaded : {STUDIO_CONFIG_ADDON} ')
    else:
        try:
            addon_utils.enable(STUDIO_CONFIG_ADDON , default_set=True, persistent=True)          
        except ModuleNotFoundError:
            logger.error(f'There was a problem enabling the {STUDIO_CONFIG_ADDON} addon')

        # When Blender first runs this startup, it will enable the startup script
        # but it won't run the callbacks until the next time Blender is started.
        # To avoid this we call ProjectConfig directly
        logger.debug(f'The Line Animation - Checking Addon status...')
        from studio_environment_startup import ProjectConfig
        ProjectConfig.enable_startup_addons()

if __name__ == "__main__":
    logger.debug(f'The Line Animation - Enabling the studio configuration addon - Blender v{bpy.app.version_string} - {__file__}')
    
    install_pyside6()
    set_pipeline_location()
    # enable_startup_addon()



