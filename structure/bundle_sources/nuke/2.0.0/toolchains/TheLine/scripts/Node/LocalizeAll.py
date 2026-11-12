import nuke

for a in nuke.allNodes():
   if a.Class()=='Read':
       a['localizationPolicy'].setValue(0)
   if a.Class()=='ReadGeo2':
       a['localizationPolicy'].setValue(0)