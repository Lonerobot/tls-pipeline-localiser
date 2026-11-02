USERSTARTUP_OUT_STR = '--THE LINE-- Maya 2026 Custom Pipeline Env - (Deferred Execution)'

LINE_LOGO_STR = """
  _____ _  _ ___   _	___ _  _ ___			
 |_   _| || | __| | |  |_ _| \| | __|   		
_______________________________________          
   |_| |_||_|___| |____|___|_|\_|___|   		
                                                
    _   _  _ ___ __  __   _ _____ ___ ___  _  _ 
   /_\ | \| |_ _|  \/  | /_\_   _|_ _/ _ \| \| |
  / _ \| .` || || |\/| |/ _ \| |  | | (_) | .` |
 /_/ \_\_|\_|___|_|  |_/_/ \_\_| |___\___/|_|\_|
 
MAYA 2026 CUSTOM USER SETUP - Check the script editor for deferred code
"""

OP_LOGO_STR = """
                 . .   ..     .    ..
        _oOOP3OPP3Op_. .
     .PPpo~.   ..   ~2p.  ..  ....  .  .
    .Ppo . .pPO3Op.. . O:. . . .
   .3Pp . oP3'. 'P33. . 4 ..   .  .   . .. .  .  .
  .~OP    3PO.  .Op3    : . ..  _____  _____  _____
  .P3O  . oP3oP3O3P' . . .   . /    /./    /./    /
   O3:.   O3p~ .       .:. . ./____/./____/ /____/
   'P .   3p3.  oP3~. ..P:. .  . ..  .   . .. .  .  .
  . ':  . Po'  .Opo'. .3O. .  o[ by Pype Club ]]]==- - - .  .
    . '_ ..  .    . _OP3..  .  .https://openpype.io.. .
         ~P3.OPPPO3OP~ . ..  .
           .  ' '. .  .. . . . ..  .
"""

AYON_LOGO_STR = """
     _ __   _____  _   _ 
    / \\ \ / / _ \| \ | |
   / _ \\ V / | | |  \| |
  / ___ \| || |_| | |\  |
 /_/   \_\_| \___/|_| \_|                                                      
"""

print(f'{LINE_LOGO_STR}')

import maya.utils

def post_load_shot_override ():    
    from ShotOverride import PreRenderChecks
    PreRenderChecks.check_for_shot_override()
    print(f'{USERSTARTUP_OUT_STR} : post_load_shot_override')

def post_load_overrides_script_job ():   
    cmds.scriptJob(e=('SceneOpened',post_load_shot_override ))

def disable_evaluator(evalType):
    import maya.cmds as cmds
    cmds.evaluator(name=evalType, enable=0)
    print(f'{USERSTARTUP_OUT_STR} : disable_evaluator {evalType}')

def get_pipeline_environ ():
    """
    execute Open
    """
    import os
    # https://peps.python.org/pep-0572/
    if pl_version := os.getenv('AYON_VERSION'): 
        print (f'{AYON_LOGO_STR}\nAYON PIPELINE {pl_version} LOADED') 
    elif pl_version := os.getenv('OPENPYPE_VERSION'): 
        print (f'{OP_LOGO_STR}\nOPENPYPE PIPELINE {pl_version} LOADED') 
        maya.utils.executeDeferred("post_load_shot_override()")
        maya.utils.executeDeferred("post_load_overrides_script_job()")
    else:
        print ('No pipeline environment found')
        # Loads any non-pipeline specific code related to Maya startup
    
    maya.utils.executeDeferred("disable_evaluator('invisibility')")

get_pipeline_environ()

