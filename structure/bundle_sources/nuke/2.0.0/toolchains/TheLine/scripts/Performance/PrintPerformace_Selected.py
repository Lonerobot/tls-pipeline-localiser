import nuke

for n in nuke.selectedNodes():
  print(n.fullName())
  print(n.performanceInfo())


