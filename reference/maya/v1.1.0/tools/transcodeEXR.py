import maya.cmds as cmds
from pathlib import Path
import subprocess
import re

"""
install this - Y:\PIPELINE\development\software\processing\ImageMagick-7.1.1-23-Q16-HDRI-x64-dll.exe
"""

def exr_to_image_sequence(subfolder='ImagePlane_Frames'):   
    
    _MAGICK_PATH = "C:/Program Files/ImageMagick-7.1.1-Q16-HDRI/magick.exe"
    _OUTPUT_FORMAT = 'jpg'
    
    if Path(_MAGICK_PATH).exists():    
 
        singleFilter = 'exr Files (*.exr*)'
        picked_folder = cmds.fileDialog2(fileFilter=singleFilter, cap="Select EXR folder location for Transcoding", fileMode=2, dialogStyle=1)
        
        print (picked_folder)
        
        if picked_folder: 
            pFolder = Path(picked_folder[0])
            print (pFolder)            
            seq = pFolder.glob('*.exr')
            img_start = next(seq)            

            if img_start:
                file_name = img_start.name
                # if name matches a regex pattern with a number of digits
                m = re.search(r"(?<=_|.)\d{4,}(?=\d*\.)", file_name)
                if m :
                    file_sequence_padding = m.group()
                    pad_length = len(file_sequence_padding)
                    exr_input = file_name.replace(file_sequence_padding, 
                                    '*')
                    exr_first_frame = img_start.parent / exr_input       
                    path_root = img_start.parent                                         
                    path_stem = img_start.stem[:-5]                   
                 
                    new_root = path_root / subfolder
 
                    if not new_root.exists():
                        new_root.mkdir(parents=True, exist_ok=True)
                        
                    output_file = new_root / f'{path_stem}_%04d.{_OUTPUT_FORMAT}'
                    
                    magick_cmd = (
                        f'"{_MAGICK_PATH}" '
                        f'-monitor '     
                        f'"{exr_first_frame}" '
                        f'-scene 1 '
                        f'"{output_file}"'
                    )
        
                    print (f'MAGICK COMMAND (Transcode EXR) : {magick_cmd}')
                                        
                    subprocess.run(magick_cmd)
                    
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
    else:
        out_message = f'ImageMagick Not Found - Check with your head of CG about your machine configuration'
        cmds.inViewMessage( message=out_message,
                fade=True, position="midCenter", fontSize=16,
                fadeStayTime=1800, fadeOutTime=100,
                dragKill=True, bkc=0x00154060, alpha=0.7)
            
def doit():
    exr_to_image_sequence()        

if __name__ == "__main__":
    doit()

            



    
