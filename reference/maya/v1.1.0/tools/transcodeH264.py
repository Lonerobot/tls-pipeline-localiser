import maya.cmds as cmds

from pathlib import Path
import subprocess
from playblast_plus.lib import settings

def mp4_to_image_sequence(subfolder='ImagePlane_Frames'):   
    
    _FFMPEG_PATH = settings.get_ffmpeg_path()
    _OUTPUT_FORMAT = 'jpg'
    
    if Path(_FFMPEG_PATH).exists():    
        multipleFilters = "MP4 Background Files (*.mp4 *.MP4);;H264 Movie (*.mp4);;H264 Movie (*.MP4);;All Files (*.*)"
        picked_file = cmds.fileDialog2(fileFilter=multipleFilters, cap="Select MP4 file for Transcoding", fileMode=1, dialogStyle=1)
        
        if picked_file:            
            file = picked_file[0]
            file_path = Path(file)
            path_root = file_path.parent
            path_stem = file_path.stem
            
            new_root = path_root / subfolder
            
            if not new_root.exists():
                new_root.mkdir(parents=True, exist_ok=True)
                
            output_file = new_root / f'{path_stem}_%4d.{_OUTPUT_FORMAT}'
            
            ffmpeg_cmd = (
                f'"{_FFMPEG_PATH}" '
                f'-y ' # overwrite
                f'-loglevel quiet ' 
                f'-i "{file}" '
                f'"{output_file}"'
            )

            print (f'FFMPEG COMMAND (Transcode MP4) : {str(new_root)} {ffmpeg_cmd}')
            subprocess.run(ffmpeg_cmd)
            
            from PySide2 import QtGui            
            clipboard = QtGui.QGuiApplication.clipboard()
            clipboard.setText(str(new_root))
            
            out_message = f'Transcode Complete - Output location has been copied to the clipboard'
            cmds.inViewMessage( message=out_message,
                    fade=True, position="midCenter", fontSize=16,
                    fadeStayTime=1800, fadeOutTime=100,
                    dragKill=True, bkc=0x00154060, alpha=0.7)
            
 

        else:
            pass
            
def doit():
    mp4_to_image_sequence()        

if __name__ == "__main__":
    doit()

            



    
