
import nuke

nuke.pluginAddPath('./gizmos')
nuke.pluginAddPath('./icons')

toolbar = nuke.toolbar("Nodes")
m = toolbar.addMenu("zDamianBinder", icon="DamianBinderNukeLogo.png")
m.addCommand("HeatWave", "nuke.createNode(\"HeatWave\")", icon="HeatWave_Icon.png")
