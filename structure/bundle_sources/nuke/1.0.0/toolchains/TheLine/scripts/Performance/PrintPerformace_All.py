import nuke

for n in nuke.allNodes(recurseGroups = True):
  print(n.fullName())
  print(n.performanceInfo())

