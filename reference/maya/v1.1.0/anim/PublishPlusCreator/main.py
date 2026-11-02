"""
  _____ _  _ ___   _	___ _  _ ___			
 |_   _| || | __| | |  |_ _| \| | __|   		
_______________________________________          
   |_| |_||_|___| |____|___|_|\_|___|   		
                                                
    _   _  _ ___ __  __   _ _____ ___ ___  _  _ 
   /_\ | \| |_ _|  \/  | /_\_   _|_ _/ _ \| \| |
  / _ \| .` || || |\/| |/ _ \| |  | | (_) | .` |
 /_/ \_\_|\_|___|_|  |_/_/ \_\_| |___\___/|_|\_|
 
Playblast Plus Creator

A script to automate the review pipeline in Maya (And others potentially)
This creates foreground frames with alpha, and a composited MP4 for ftrack review

This leans on classes and method from Playblast PLus, so you can't run this without it.

TO PUBLISH

import subprocess 
from openpype.lib import get_openpype_execute_args

pb_path = r"Y:\PIPELINE\config\maya\2023\scripts\PublishPlusCreator\publishReview.py"
args = get_openpype_execute_args("run", pb_path)
subprocess.run(args)



"""

from playblast_plus.lib import dcc, utils, preset, settings, logger
from playblast_plus import PLAYBLAST_PLUS_MODULE_ROOT as module_root



from . import (
    PUBLISH_PLUS_MODULE_ROOT,
    PUBLISH_PLUS_REVIEWABLE,
    PUBLISH_PLUS_REPRESENTATION,
    PUBLISH_PLUS_VARIANT
)

from pathlib import Path
from maya import cmds
import subprocess
import copy
import json




class PublishPlusLogger(logger.Logger):
    LOGGER_NAME = "PlayBlastPlusLogger - Publish"

class PublishPlus():  
    PBP_PUBLISH_NAME = 'pbp_publish'
    BG_LAYER_NAME = 'pbp_background'
    FG_LAYER_NAME = 'pbp_foreground'

    def __init__(self) -> None:
        self.host = dcc.Host()
        self.output_root = Path (self.host.scene.get_output_dir(), 'composite')
        if not self.output_root.exists():
            self.output_root.mkdir()

        settings_file = Path(__file__).parent.absolute() / 'settings.json'
        with open(settings_file) as f:
            publish_plus_settings = json.load(f)

        self.variant = publish_plus_settings["variant"]  
        self.review_prefix = publish_plus_settings["review_prefix"]
        self.representation_prefix = publish_plus_settings["representation_prefix"]

        self.publish_output = f'{self.review_prefix}_Anim_playblast.mp4'

        self.json_file = "_preview_override.json"
        self.get_ayon_context()

        self.preview_override_data = []

        if self.json_template_path.exists():
            PublishPlusLogger.info  (f'Override Template Found : {self.json_template_path}')
            with open(self.json_template_path, 'r') as f:
                self.preview_override_data = json.load(f)
                PublishPlusLogger.info  (f'Override Template Data : {self.preview_override_data }')

        self.ffmpeg_path = settings.get_ffmpeg_path()    

    def set_exists(self, set_name):
        return cmds.objExists(set_name)
    
    def open_output_folder(self):
        utils.FolderOps.explore(self.output_root)   
    
    def get_ayon_context(self):
        from ayon_core.pipeline import context_tools 

        context = context_tools.get_current_context()
        self.project_name = context["project_name"]       
        self.task_name =  context["task_name"]       
        self.folder_path = context["folder_path"]
        import os
        self.work_dir = Path(os.environ["AYON_WORKDIR"])  
        self.json_template_path = self.work_dir / self.json_file   

    def get_playblast_camera(self):
        set_list = [self.PBP_PUBLISH_NAME, self.BG_LAYER_NAME, self.FG_LAYER_NAME]        
        for set_name in set_list: 
            if self.set_exists(set_name):       
                objects = cmds.sets(set_name, q=True)
                if objects:    
                    for obj in objects:
                        obj_type = cmds.nodeType(obj)
                        if obj_type == 'camera':
                            PublishPlusLogger.info (f'Camera Found - {set_name} {obj}')
                            return obj
                        elif cmds.objectType(obj, isType='transform'):
                            # Check if the transform represents a camera
                            shapes = cmds.listRelatives(obj, shapes=True, fullPath=True) or []
                            for shape in shapes:
                                if cmds.nodeType(shape) == 'camera':
                                    PublishPlusLogger.info  (f'Camera Found - {set_name} {obj}')
                                    return obj
                else:
                   self.notify_user("Please add some objects to preview into the pbp_publish sets. Check the help if you're unsure")
                                 
                    
    def notify_user(self, msg):
        cmds.inViewMessage( message=msg,
        fade=True, position="midCenter", fontSize=16,
        fadeStayTime=2000, fadeOutTime=100,
        dragKill=True, bkc=0x00154060, alpha=0.7)

    def create_sets(self):  
        
        cmds.select( clear=True )
        
        pbp_publish_set = self.PBP_PUBLISH_NAME
        background_set = self.BG_LAYER_NAME
        foreground_set = self.FG_LAYER_NAME
        
        if self.set_exists(self.PBP_PUBLISH_NAME) and self.set_exists(self.BG_LAYER_NAME) and self.set_exists(self.FG_LAYER_NAME):
            return pbp_publish_set, background_set, foreground_set

        # Create the main set if it doesn't exist
        if not self.set_exists(self.PBP_PUBLISH_NAME):
            self.pbp_publish_set = cmds.sets(name=self.PBP_PUBLISH_NAME)
            # Create sub-sets inside the main set if they don't exist
            if not self.set_exists(self.BG_LAYER_NAME):
                self.background_set = cmds.sets(name=self.BG_LAYER_NAME, empty=True)
                cmds.sets(background_set, add=pbp_publish_set)
            if not self.set_exists(self.FG_LAYER_NAME):
                self.foreground_set = cmds.sets(name=self.FG_LAYER_NAME, empty=True)
                cmds.sets(foreground_set, add=pbp_publish_set)

        return self.pbp_publish_set, self.background_set, self.foreground_set

    def add_objects_to_set(self,objects, set_name):
        cmds.sets(objects, add=set_name)

    def get_objects_in_set(self,set_name):
        objects = cmds.sets(set_name, q=True) or []
        #geometry_objects = [obj for obj in objects if cmds.objectType(obj, isType='geometryShape')]
        return objects

    def delete_background_layer_images(self, file_sequence):
        # Create a Path object for the folder
        file_sequence = Path(file_sequence)
        output_folder = file_sequence.parent 
        pattern = file_sequence.name
        pattern = pattern.replace(r'%04d', r'*')
        # Use glob to match files with the given pattern
        utils.FolderOps.purge_contents(output_folder,pattern)

    def mp4_from_image_sequence(self, image_seq_path: str, 
                                output_path: str, 
                                framerate: int = 24,
                                start_frame: int = 0, 
                                end_frame: int = 0,
                                add_burnin: bool = False,
                                burnin_text: str = "",
                                burnin_font_size: int = 24
                            ):

        if add_burnin:
            burnin = (
                f'-vf "drawtext=font=Consolas: fontsize={burnin_font_size}: '
                f'fontcolor=black@0.5: text=\'{burnin_text} | %{{eif\:n\:d\:4}}\': '
                f'start_number={start_frame}: r=24: x=(w-tw-20): y=20: '
                f'box=1: boxcolor=orange@0.5: boxborderw=2"'
            )
        else:
            burnin = ''        

        ffmpeg_cmd = (
            f'"{self.ffmpeg_path}" '
            f'-framerate {framerate} '
            f'-y ' # overwrite
            f'-start_number {start_frame} '
            # f'-loglevel quiet ' 
            f'-i "{image_seq_path}" '
            f'{burnin} '
            f'{settings.get_ffmpeg_input_args()} '
            f'-frames:v {end_frame} '
            f'"{output_path}"'
        )

        PublishPlusLogger.info(f'FFMPEG COMMAND (mp4_from_image_sequence) : {ffmpeg_cmd}')
        subprocess.call(ffmpeg_cmd)


    def composite_images(self,fg_sequence, bg_sequence, start_frame, framerate, output_file, cleanup):
        
        
        
        output_folder = Path(fg_sequence).parent
        output_path = output_folder / output_file        
        sf = str(int(start_frame))       
        
        PublishPlusLogger.debug (f'{self.ffmpeg_path} Output {output_path}')

        # could use '-vsync', 'vfr' ref command that works acceptably
        '''
        ffmpeg_cmd = ['C:\\Program Files\\ffmpeg\\bin\\ffmpeg.exe', '-y', '-framerate', '24', '-start_number', '1',  '-i', 'C:\\Users\\petea\\Documents\\maya\\2024\\playblasts\\composite\\LAYER_pbp_background.%04d.png', '-framerate', '24', '-start_number', '1', '-i', 'C:\\Users\\petea\\Documents\\maya\\2024\\playblasts\\composite\\PUBLISH_pbp_foreground.%04d.png', '-filter_complex', '[0:v]setpts=PTS-STARTPTS[v0]; [1:v]setpts=PTS-STARTPTS[v1]; [v0][v1]overlay[v]',  '-map', '[v]',  '-vsync', 'passthrough', '-r', '24','-c:v', 'libx264', '-crf', '18', '-preset', 'slow', '-movflags', '+faststart', '-pix_fmt', 'yuv420p', 'C:\\Users\\petea\\Documents\\maya\\2024\\playblasts\\composite\\_REVIEWABLE_Anim_playblast_v2.mp4']
        '''
    
        ffmpeg_cmd = [
            f'{self.ffmpeg_path}',
            '-y',
            '-framerate', str(framerate),
            '-start_number', sf,
            '-i', bg_sequence,
            '-framerate', str(framerate), 
            '-start_number', sf,
            '-i', fg_sequence,
            '-filter_complex', '[0:v]setpts=PTS-STARTPTS[v0]; [1:v]setpts=PTS-STARTPTS[v1]; [v0][v1]overlay[v]',   
            '-map', '[v]',
            '-vsync', 'passthrough', 
            '-r', str(framerate),
            '-c:v', 'libx264',
            '-crf', '18',
            '-preset', 'slow',
            '-movflags', '+faststart',
            '-pix_fmt', 'yuv420p',
            str(output_path)
        ]



        PublishPlusLogger.info (ffmpeg_cmd)        
        subprocess.run(ffmpeg_cmd) 
        if cleanup: 
            self.delete_background_layer_images(bg_sequence)
        utils.FolderOps.explore(output_folder)          

    def pre_publish(self):
        self.create_sets() 

    def create_media_from_task_override(self, purge_directory=False, cleanup=False):
        # self.create_sets() 

        if self.json_template_path.exists():

            with open(self.json_template_path, 'r') as f:
                self.preview_override_data = json.load(f)

            preview_width = int(self.preview_override_data["Preview"]["preview.resolution_x"])
            preview_height =int(self.preview_override_data["Preview"]["preview.resolution_y"])

            scene_width, scene_height = self.host.scene.get_render_resolution()

            cmds.select( clear=True )   
            scene_start, scene_end = self.host.scene.getFrameRange()
            scene_frame_rate = self.host.scene.getFrameRate()

            
            self.STUDIO_PRESET = {}            
            template_list = preset.load_templates ( [str(module_root / 'templates' / 'studio' )] )
            
            # get FG set objects
            camera_name = self.get_playblast_camera()
            if camera_name:    

                if purge_directory:
                    utils.FolderOps.purge_contents(self.output_root)             
            
                for template in template_list:
                    if 'studio_default' in template:
                        # RENDER THE FOREGROUND LAYER 
                        
                        # make a copy of the dictionary
                        REVIEW_FG = copy.deepcopy(template['studio_default'] )
                        REVIEW_BG = copy.deepcopy(template['studio_default'] )
                                                            
                        fg_meshes =  self.get_objects_in_set(self.FG_LAYER_NAME) 
                        # output_name = f'{self.review_prefix}_{self.FG_LAYER_NAME}'
                        output_name = f'{self.representation_prefix}_{self.FG_LAYER_NAME}'

                        # STUDIO_PRESET = template['studio_default']                     
                        # REVIEW_FG['isolate'] = []                        
                        REVIEW_FG['width'] = scene_width
                        REVIEW_FG['height'] = scene_height
                        REVIEW_FG['viewport_options']['imagePlane'] = False

                        REVIEW_FG["filename"] = str(self.output_root / output_name)
                        REVIEW_FG['camera'] = camera_name

                        if fg_meshes:                    
                            REVIEW_FG['isolate'] = fg_meshes
                            
                        PublishPlusLogger.info (f'Foreground Preset Settings :{REVIEW_FG}')
                        fg_output = self.host.preview.create(template=REVIEW_FG)
                
                        # RENDER THE PREVIEW OVERRIDE

                        

                        bg_meshes = self.get_objects_in_set(self.BG_LAYER_NAME)                                            
                        override_meshes = fg_meshes + bg_meshes

                        REVIEW_BG['viewport_options']['imagePlane'] = True
                        # REVIEW_BG['isolate'] = []  
                        REVIEW_BG['width'] = preview_width
                        REVIEW_BG['height'] = preview_height  
                        REVIEW_BG['camera'] = camera_name                                              
                        REVIEW_BG["filename"] = str(self.output_root / f'LAYER_{self.BG_LAYER_NAME}')
                
                        if override_meshes:
                            if camera_name not in override_meshes: 
                                override_meshes.append(camera_name)       
                            REVIEW_BG['isolate'] = override_meshes
                            
                        
                        PublishPlusLogger.info (f'OVERRIDE MESHES :{REVIEW_BG["isolate"]}')
                                    
                
                        # PublishPlusLogger.info (f'Background Preset Settings :{STUDIO_PRESET}')
                        bg_output = self.host.preview.create(template=REVIEW_BG)                    
                        #PublishPlusLogger.info (fg_output, bg_output)
                        output_path = self.output_root  / self.publish_output

                        if bg_output:        
                            self.mp4_from_image_sequence( image_seq_path=bg_output, 
                                                         output_path=output_path, 
                                                         start_frame=scene_start, 
                                                         end_frame=scene_end ,
                                                         framerate=scene_frame_rate , 
                                                         add_burnin=True ,
                                                         burnin_text=f'{preview_width} x {preview_height}'
                                                        )
                            
                        if cleanup: 
                            self.delete_background_layer_images(bg_output)
                            utils.FolderOps.explore(self.output_root)   

            else:
                cmds.inViewMessage( message=f"Please put a camera into the pbp_background set",
                        fade=True, position="midCenter", fontSize=16,
                        fadeStayTime=2000, fadeOutTime=100,
                        dragKill=True, bkc=0x00154060, alpha=0.7)
        

    def create_publish_media(self, purge_directory=False, cleanup=False):
        # self.create_sets() 
        
        cmds.select( clear=True )
        
        scene_width, scene_height = self.host.scene.get_render_resolution()
        scene_start, scene_end = self.host.scene.getFrameRange()
        scene_frame_rate = self.host.scene.getFrameRate()

        
        self.STUDIO_PRESET = {}            
        template_list = preset.load_templates ( [str(module_root / 'templates' / 'studio' )] )
        
        # get FG set objects
        camera_name = self.get_playblast_camera()
        if camera_name:    

            if purge_directory:
                utils.FolderOps.purge_contents(self.output_root)             
        
            for template in template_list:
                if 'studio_default' in template:
                    # RENDER THE FOREGROUND LAYER 
                    
                    # make a copy of the dictionary
                    REVIEW_FG = copy.deepcopy(template['studio_default'] )
                    REVIEW_BG = copy.deepcopy(template['studio_default'] )
                                                           
                    fg_meshes =  self.get_objects_in_set(self.FG_LAYER_NAME) 
                    # output_name = f'{self.review_prefix}_{self.FG_LAYER_NAME}'
                    output_name = f'{self.representation_prefix}_{self.FG_LAYER_NAME}'

                    # STUDIO_PRESET = template['studio_default']                     
                    # REVIEW_FG['isolate'] = []                        
                    REVIEW_FG['width'] = scene_width
                    REVIEW_FG['height'] = scene_height
                    REVIEW_FG['viewport_options']['imagePlane'] = False

                    REVIEW_FG["filename"] = str(self.output_root / output_name)
                    REVIEW_FG['camera'] = camera_name

                    if fg_meshes:                    
                        REVIEW_FG['isolate'] = fg_meshes
                        
                    PublishPlusLogger.info (f'Foreground Preset Settings :{REVIEW_FG}')
                    fg_output = self.host.preview.create(template=REVIEW_FG)
            
                    # RENDER THE BACKGROUND LAYER 
                    bg_meshes = self.get_objects_in_set(self.BG_LAYER_NAME)
                                        

                    REVIEW_BG['viewport_options']['imagePlane'] = True
                    # REVIEW_BG['isolate'] = []  
                    REVIEW_BG['width'] = scene_width
                    REVIEW_BG['height'] = scene_height  
                    REVIEW_BG['camera'] = camera_name                                              
                    REVIEW_BG["filename"] = str(self.output_root / f'LAYER_{self.BG_LAYER_NAME}')
            
                    if bg_meshes:
                        if camera_name not in bg_meshes: 
                            bg_meshes.append(camera_name)       
                        REVIEW_BG['isolate'] = bg_meshes
                        
                    PublishPlusLogger.info (f'FOREGROUND MESHES :{REVIEW_FG["isolate"]}')
                    PublishPlusLogger.info (f'BACKGROUND MESHES :{REVIEW_BG["isolate"]}')
                                
            
                    # PublishPlusLogger.info (f'Background Preset Settings :{STUDIO_PRESET}')
                    bg_output = self.host.preview.create(template=REVIEW_BG)                    
                    #PublishPlusLogger.info (fg_output, bg_output)

                    # if self.pbp_output_override:
                    #     self.PBP_PUBLISH_OUTPUT = self.pbp_output_override
                    
                    if fg_output and bg_output:        
                        self.composite_images(fg_output, bg_output, scene_start, scene_frame_rate, self.publish_output, cleanup)

        else:
            cmds.inViewMessage( message=f"Please put a camera into the pbp_background set",
                    fade=True, position="midCenter", fontSize=16,
                    fadeStayTime=2000, fadeOutTime=100,
                    dragKill=True, bkc=0x00154060, alpha=0.7)

if __name__ == '__main__':
    pass
 
    # pbPublish = PublishPlus() 
    # creates the sets needed in the outliner
    # pbPublish.pre_publish()
    #renders the layers and compiles the video
    # pbPublish.open_output_folder()
    # pbPublish.create_publish_media(purge_directory=True, cleanup=False)
