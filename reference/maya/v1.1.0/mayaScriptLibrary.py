
"""
  _____ _  _ ___   _	___ _  _ ___			
 |_   _| || | __| | |  |_ _| \| | __|   		
_______________________________________          
   |_| |_||_|___| |____|___|_|\_|___|   		
                                                
    _   _  _ ___ __  __   _ _____ ___ ___  _  _ 
   /_\ | \| |_ _|  \/  | /_\_   _|_ _/ _ \| \| |
  / _ \| .` || || |\/| |/ _ \| |  | | (_) | .` |
 /_/ \_\_|\_|___|_|  |_/_/ \_\_| |___\___/|_|\_|
 
MAYA SCRIPT LIBRARY

A useful function to scan and create a hierarchical tools menu within Maya. 

This saves time having to update the scripts menu definition manually.

How to use this class - 

Run the following command inside maya

    import mayaScriptLibrary
    mayaScriptLibrary.generate_pype_menu()

You'll find a generated menu for Pype that collects all scripts inside the 
sub folders. I keep this to one level deep on each discipline. 

    {
        "type": "action",
        "command": "from mayaScriptLibrary import run_script ; run_script (\"_global\",\"playblastPlus.py\")",
        "sourcetype": "python",
        "tags": [],
        "title": "Playblast Plus",
        "tooltip": ""
    },

The script execution is done via a call wrapper - mayaScriptLibrary.run_script

It calls the __main__ method. 

If you have a script with specific setups (like a 3rd party script or module inside these folders)

you can create a script that runs it and is still picked up by the folder scan

For example - 

File - playblastPlus.py

Contents - 
    if __name__ == "__main__":
        from playblast_plus import launch
        launch.run()
"""

import runpy
import os
from pathlib import Path
import json
import logging

log = logging.getLogger(__name__)

def run_script (section, module, method='__main__'):

    try:
        path = os.path.dirname(os.path.realpath(__file__))
        if path:
            module_path = f'{path}\\{section}\\{module}'
            runpy.run_path(module_path, run_name=method)
            log.info(f'[CORE SCRIPT][{section}] - [Module] {module}')
    except Exception as e:
        log.error(e)
        return

class PypeMenuBuilder:
    def __init__(self, root_dir):
        self.root_dir = Path(root_dir)
        self.folder_names = []
        self.file_data = []

    def collect_folders(self):
        for item in self.root_dir.iterdir():
            if item.is_dir():
                self.folder_names.append(item.name)
        self.folder_names.sort(key=lambda x: (not x.startswith('_'), x.casefold()))

    def scan_folders(self):
        for folder_name in self.folder_names:
            folder_path = self.root_dir / folder_name
            # Check if the folder name starts with an underscore
            if folder_name.startswith('_'):
                for item in folder_path.iterdir():
                    if item.is_file() and item.suffix in ['.py', '.mel'] and item.name != '__init__.py':
                        script_item = self.create_script_item(folder_name, item)
                        self.file_data.append(script_item)
                    # self.file_data.append({"type": "separator"})
            else:
                files = []
                self.file_data.append({"type": "separator"})

                for item in folder_path.iterdir():
                    if item.is_file() and item.suffix in ['.py', '.mel'] and item.name != '__init__.py':
                        script_item = self.create_script_item(folder_name, item)
                        files.append(script_item)
                menu_data = {
                    "type": "menu",
                    "title": folder_name.title(),
                    "items": files
                }
                self.file_data.append(menu_data) 
                self.file_data.append({"type": "separator"})

    def create_script_item(self, folder_name, file_item):
        file_name = file_item.stem
        nice_name = self.make_nice_name(file_name)
        return {
            "type": "action",
            "command": f'from mayaScriptLibrary import run_script ; run_script (\"{folder_name}\",\"{file_item.name}\")',
            "sourcetype": "python",
            "tags": [],
            "title": nice_name,
            "tooltip": ""
        }
    
    def make_nice_name(self,name):
        nice_name = ''
        for i, char in enumerate(name):
            if char.isupper() and i > 0:
                if i < len(name) - 1 and name[i + 1].islower():
                    nice_name += ' ' + char
                else:
                    nice_name += char
            elif char == '_':
                nice_name += ' '
            else:
                nice_name += char
        return nice_name.title()

    def save_to_json(self, file_path):
        with open(file_path, 'w') as json_file:
            json.dump(self.file_data, json_file, indent=4)

def generate_pype_menu():
    # Example usage if you your moudles are in the current directory :
    root_directory = os.path.dirname(os.path.realpath(__file__))
    # or just pass it the location :  
    # root_directory = 'Y:\PIPELINE\config\maya\core'
    builder = PypeMenuBuilder(root_directory)
    builder.collect_folders()
    builder.scan_folders()
    builder.save_to_json(f'{root_directory}/corescripts_template.json')

if __name__ == '__main__':
    generate_pype_menu()