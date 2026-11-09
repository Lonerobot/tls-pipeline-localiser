import nuke


import TL_Backdrop

ico = 'TLBD_logo.png'
m = nuke.toolbar('Nodes')
m.addCommand('TL_Backdrop', 'TL_Backdrop.show_backdrop_maker()', shortcut='ctrl+b', icon=ico)