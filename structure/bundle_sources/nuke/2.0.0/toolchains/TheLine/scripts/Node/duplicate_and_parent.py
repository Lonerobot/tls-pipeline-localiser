import nuke

def CopyWithExp():
  sourceNode = nuke.selectedNode().name()
  nuke.nodeCopy("%clipboard%")
  #nuke.nodePaste("%clipboard%")
  destNode = nuke.selectedNode().name()
  for i in nuke.selectedNodes():
      for j in i.knobs():
          i[j].setExpression( sourceNode + '.' + j )
      #i['xpos'].setExpression('')
      #i['ypos'].setExpression('')
      i['selected'].setExpression('')
      i['channels'].setExpression( sourceNode + '.channels' )


nuke.menu('Nuke').addCommand('Edit/Copy with Expressions', "CopyWithExp()", "^#C")

CopyWithExp()