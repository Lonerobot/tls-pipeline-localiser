from pathlib import Path 
import os
import json
import maya.cmds as cmds

import openpype.pipeline as op

class ParsingUtils:
    @staticmethod
    def loadJSONfromFile(file):
        with open(file, 'r') as myfile:
            data=myfile.read()
        return json.loads(data)

class PreRenderChecks():
    @staticmethod
    def check_for_shot_override():
        task =  op.get_current_task_name()
        work_dir = Path(op.context_tools.get_workdir_from_session())

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
            print (f'{task} {override_type} Override Template Found - {override_template}')
            
            override_settings = ParsingUtils.loadJSONfromFile(str(override_template))
            if override_settings['Settings']: 
                print (f'Override Resolution Settings : {override_settings}')
                w = int(override_settings['Settings']['render.resolution_x'])
                h = int(override_settings['Settings']['render.resolution_y'])
                pAx = 1.0
                pAr = float(w)/h
                cmds.setAttr("defaultResolution.aspectLock", 0)
                cmds.setAttr("defaultResolution.width", w)
                cmds.setAttr("defaultResolution.height", h)
                cmds.setAttr("defaultResolution.pixelAspect", pAx)
                cmds.setAttr("defaultResolution.deviceAspectRatio", pAr)

def check():
    PreRenderChecks.check_for_shot_override()
    
if __name__ == '__main__':
     check()