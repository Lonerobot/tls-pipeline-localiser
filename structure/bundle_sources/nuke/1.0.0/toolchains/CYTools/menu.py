import nuke


import CY_Backdrop

ico = 'Cy_logo.png'
m = nuke.toolbar('Nodes')
m.addCommand('CY_Backdrop', 'CY_Backdrop.CY_Backdrop()', shortcut='ctrl+b', icon=ico)