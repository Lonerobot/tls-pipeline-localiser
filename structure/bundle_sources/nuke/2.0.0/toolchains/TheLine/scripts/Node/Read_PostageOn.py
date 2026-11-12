import nuke

for a in nuke.allNodes():
   if a.Class()=='Read':
       a['postage_stamp'].setValue(1)