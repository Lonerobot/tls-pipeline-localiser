import os
import nuke
import nukescripts
import toolsTK.common as tk


print('chMenu loaded')

if os.getenv('CH_ROOT_MENU'):
    rootMenu=os.getenv('CH_ROOT_MENU')
else:
    rootMenu='toolsTK'
    
menubar=nuke.menu("Nuke")

m=menubar.findItem(rootMenu)
if m:
    m.clearMenu()
    print('Menu refreshed...')
else:
    m=menubar.addMenu(rootMenu)


# AUTO BACKDROP OVERRIDE

import toolsTK.autoBackdrop as autoBackdrop
nukescripts.autoBackdrop = autoBackdrop.autoBackdrop

m.addCommand("Utilities/Backdrop", 'nukescripts.autoBackdrop()','#b')


m.addCommand("Sys/Update menu", "nuke.load('ch_menu.py')")



#m.addCommand("AutoRead", "nuke.load('ch_autoRead.py'),ch_createCompTemplate()")
#m.addCommand("FULLAUTO", "nuke.load('ch_autoRead.py'),ch_fullAuto()")

""" adv IP Menu """
#import toolsTK.chViewerInput as tkViewerInput
#tkViewerInput.menuInit()
