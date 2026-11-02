import maya.cmds as cmds
import maya.mel as mel
import maya.OpenMaya as om
import os
import math
#import commonClasses; reload(commonClasses); from commonClasses import common; cc=common()

version = 1.0

#version history:
#1.0 - initial release

##############################################################################################
'''
Author:
Piotr Zyla

Contact:
cganimation57@gmail.com

Website:
www.animpeter.com

Creation date of current version: 
11 April 2019

Installation:
copy pBakery.py into your script folder and run as python command: import pBakery; reload(pBakery); pBakery.run()

Usage Policy:
I created this script with great joy and satisfaction to make my life and all my cg collegues easier. 
This script is completly free for private and commercial usage. Any material profit by further distribution of this 
script is prohibited and would be super unfair. However I encourage all of you to spread it if you think it could help to make anyone's work better!

If you have any suggestions or you spotted any bugs, please contact me via email.
For more cool scripts please visit www.animpeter.com/scripts

So enjoy and have a great day :)

'''
##############################################################################################

############################COMMON CLASSES########################################
class common():

	#CREATE
	def creNamespace(self, namespaceName):

		if cmds.namespace(ex = namespaceName) == False:

			cmds.namespace(add = namespaceName)

	def creAttr(self, objectName , attrName, attrValue, minVal=None, maxVal=None):
	
		if not cmds.objExists(objectName + '.' + attrName):
			
			dataType = type(attrValue)

			if dataType == int:
				cmds.addAttr(objectName, at='short', shortName=attrName, ln=attrName, k=True)
				cmds.setAttr(objectName + '.' + attrName, attrValue)
	 
			if dataType == float:
				cmds.addAttr(objectName, at='float', shortName=attrName, ln=attrName, k=True)
				cmds.setAttr(objectName + '.' + attrName, attrValue)

			if dataType == str and len(attrValue.split(':'))>1:
				cmds.addAttr(objectName, at='enum', ln=attrName, enumName=attrValue, k=True)

			elif dataType == str or dataType == dict:
				cmds.addAttr(objectName, ln = attrName, shortName = attrName, dataType='string', k=True)
				cmds.setAttr(objectName + '.' + attrName, attrValue, type = 'string')
	 
			if dataType == bool:
				cmds.addAttr(objectName, ln = attrName, shortName = attrName, at='bool', k=True)
				cmds.setAttr(objectName + '.' + attrName, attrValue)
	 
			if dataType == tuple:
				cmds.addAttr(objectName, ln = attrName, attributeType = 'float3', k=True)
				cmds.addAttr(objectName, ln = attrName + '1', at='float', p = attrName, k=True)
				cmds.addAttr(objectName, ln = attrName + '2', at='float', p = attrName, k=True)
				cmds.addAttr(objectName, ln = attrName + '3', at='float', p = attrName, k=True)
				cmds.setAttr(objectName + '.' + attrName, attrValue[0], attrValue[1], attrValue[2])

			#add min/max values
			if minVal != None:
				cmds.addAttr(objectName + '.' + attrName, e=True, minValue = minVal)

			if maxVal != None:
				cmds.addAttr(objectName + '.' + attrName, e=True, maxValue = maxVal)

	def creStorage(self, objectName):

		#get initial selection
		initialSelList = cmds.ls(sl = True)

		if cmds.objExists(objectName) == False:

			if objectName.split('_')[-1] == 'NOD':
				cmds.createNode('tweak', n = objectName)

			if objectName.split('_')[-1] == 'SET':
				cmds.createNode('objectSet', n = objectName)
				cmds.setAttr(objectName + '.isLayer', 0)

			if objectName.split('_')[-1] == 'LAY':
				cmds.createDisplayLayer(n = objectName , noRecurse = True, empty=True)

		#back to selection
		cmds.select(initialSelList)

	def creSmartConstraint(self, objSrc, objTrg, attrList, mo=False, name=False):

		if attrList == 't':
			attrList = ['tx', 'ty', 'tz']
		if attrList == 'r':
			attrList = ['rx', 'ry', 'rz']
		if attrList == 's':
			attrList = ['sx', 'sy', 'sz']
		if attrList == 'tr':
			attrList = ['tx', 'ty', 'tz','rx', 'ry', 'rz']
		if attrList == 'trs':
			attrList = ['tx', 'ty', 'tz','rx', 'ry', 'rz','sx', 'sy', 'sz']

		def getSkippedAttrList(attrList):

			transfromFullList = ['x','y','z']
			axisList = map(lambda n: n[1],attrList)
			#remove from fill list
			for axis in axisList:
				
				transfromFullList.remove(axis)

			return transfromFullList

		#get attr list to constraintz
		attrSrcList = map(lambda n: n[0] + n[-1].lower(), self.getAttrInfoList(objTrg, 'keyable'))
		attrTraList = []
		attrRotList = []
		attrSclList = []

		#get available attribute list
		for attrName in attrSrcList:

			if attrName in attrList:
				if attrName in ['tx','ty','tz','rx','ry','rz','sx','sy','sz']:
					transform = attrName[0]
					axis = attrName[1]
					if transform=='t':
						attrTraList.append(attrName)
					if transform=='r':
						attrRotList.append(attrName)
					if transform=='s':
						attrSclList.append(attrName)

		#set name
		if name==False:
			name = objTrg + '_CNS'

		#assign parent constraint
		if attrTraList!=[] and attrRotList !=[]:
			cmds.parentConstraint(objSrc, objTrg, skipTranslate=getSkippedAttrList(attrTraList), skipRotate=getSkippedAttrList(attrRotList), mo=mo, name=name)

		#assign point constraint
		if attrTraList!=[] and attrRotList == []:
			cmds.pointConstraint(objSrc, objTrg, skip=getSkippedAttrList(attrTraList), mo=mo, name=name)

		#assign orient constraint
		if attrTraList==[] and attrRotList != []:
			cmds.orientConstraint(objSrc, objTrg, skip=getSkippedAttrList(attrRotList), mo=mo, name=name)

		#assign scale constraint
		if attrSclList!=[]:
			cmds.scaleConstraint(objSrc, objTrg, skip=getSkippedAttrList(attrSclList), mo=mo, name=name)

	def creNPointGuideLine(self, guideName, objList, close=None):
	
		pointQuant = len(objList)

		if close:
			pointQuant = pointQuant + 1

		pointList = []
		groupName = guideName + '_GRP'
		curveName = guideName + '_CRV'
		curveShapeName = curveName + 'Shape'
		
		#reload
		if cmds.objExists(groupName):
			cmds.delete(groupName)
		
		#create
		cmds.group(n=groupName, em=True)
		
		#get curve points
		for pointIndex in range(pointQuant):
			
			pointList.append((pointIndex,0,0))
			
		#create curve
		cmds.curve(n = curveName, d=1, p=pointList)
		cmds.rename(cmds.listRelatives(curveName, shapes=True)[0], curveShapeName)
		cmds.parent(curveName, groupName)
		cmds.setAttr(curveName + '.inheritsTransform', 0)
		
		#apply ocnstrain on each curve point
		for pointIndex in range(pointQuant):
			
			clusterName = guideName + '_' + str(pointIndex) + '_CLS'
			pointName = curveName + '.cv[' + str(pointIndex) + ']'
			cmds.select(pointName)
			cmds.cluster(n=clusterName)
			
		#make curve template
		cmds.setAttr(curveName + '.overrideEnabled', 1)
		cmds.setAttr(curveName + '.overrideDisplayType', 2)
		
		#constraint to objects
		for pointIndex in range(0, len(objList)):

			clusterName = guideName + '_' + str(pointIndex) + '_CLSHandle'
			constraintName = guideName + '_' + str(pointIndex) + '_CNS'
			cmds.pointConstraint(objList[pointIndex], clusterName, n = constraintName)
			cmds.parent(clusterName, groupName)
			cmds.setAttr(clusterName + '.visibility', 0)

		#close guide
		if close:

			clusterName = guideName + '_' + str(pointQuant-1) + '_CLSHandle'
			constraintName = guideName + '_' + str(pointQuant-1) + '_CNS'
			cmds.pointConstraint(objList[0], clusterName, n = constraintName)
			cmds.parent(clusterName, groupName)
			cmds.setAttr(clusterName + '.visibility', 0)
			
		#deselect
		cmds.select(cl=True)

	def creControl(self, crvName, shape, posList=[0,0,0], rotList=[0,0,0], rotPivot=[0,0,0], sclList=[1,1,1], sclPivot=[0,0,0]):

		#create curve
		if shape == 'cube':

			cmds.curve(n=crvName, d=1, p=[[-0.5, 0.5, -0.5], [-0.5, 0.5, 0.5], [0.5, 0.5, 0.5], [0.5, 0.5, -0.5], [-0.5, 0.5, -0.5], [-0.5, -0.5, -0.5], [-0.5, -0.5, 0.5], [0.5, -0.5, 0.5], [0.5, 0.5, 0.5], [-0.5, 0.5, 0.5], [-0.5, -0.5, 0.5], [-0.5, -0.5, -0.5], [0.5, -0.5, -0.5], [0.5, 0.5, -0.5], [0.5, 0.5, 0.5], [0.5, -0.5, 0.5], [0.5, -0.5, -0.5]])

		if shape == 'arrow3d':

			cmds.curve(n=crvName, d=1, p=[[0.25, -0.25, -1.0], [-0.25, -0.25, -1.0], [-0.25, -0.25, 0.5], [-0.75, -0.25, 0.5], [0.0, -0.25, 2.25], [0.75, -0.25, 0.5], [0.25, -0.25, 0.5], [0.25, -0.25, -1.0], [0.25, 0.25, -1.0], [-0.2500000000000001, 0.25, -1.0], [-0.25, -0.25, -1.0], [-0.2500000000000001, 0.25, -1.0], [-0.25, 0.25, 0.5], [-0.25, -0.25, 0.5], [-0.25, 0.25, 0.5], [-0.75, 0.25, 0.5], [-0.75, -0.25, 0.5], [-0.75, 0.25, 0.5], [0.0, 0.25, 2.25], [0.0, -0.25, 2.25], [0.0, 0.25, 2.25], [0.75, 0.25, 0.5], [0.75, -0.25, 0.5], [0.75, 0.25, 0.5], [0.25, 0.25, 0.49999999999999994], [0.25, -0.25, 0.5], [0.25, 0.25, 0.49999999999999994], [0.25, 0.25, -1.0]])			

		if shape == 'sphere':

			cmds.curve(n=crvName, d=1, p=[[0.0, 0.5, 0.0], [0.0, 0.46194, 0.1913415], [0.0, 0.3535535, 0.3535535], [0.0, 0.1913415, 0.46194], [0.0, 0.0, 0.5], [0.0, -0.1913415, 0.46194], [0.0, -0.3535535, 0.3535535], [0.0, -0.46194, 0.1913415], [0.0, -0.5, 0.0], [0.0, -0.46194, -0.1913415], [0.0, -0.3535535, -0.3535535], [0.0, -0.1913415, -0.46194], [0.0, 0.0, -0.5], [0.0, 0.1913415, -0.46194], [0.0, 0.3535535, -0.3535535], [0.0, 0.46194, -0.1913415], [0.0, 0.5, 0.0], [0.1913415, 0.46194, 0.0], [0.3535535, 0.3535535, 0.0], [0.46194, 0.1913415, 0.0], [0.5, 0.0, 0.0], [0.46194, -0.1913415, 0.0], [0.3535535, -0.3535535, 0.0], [0.1913415, -0.46194, 0.0], [0.0, -0.5, 0.0], [-0.1913415, -0.46194, 0.0], [-0.3535535, -0.3535535, 0.0], [-0.46194, -0.1913415, 0.0], [-0.5, 0.0, 0.0], [-0.46194, 0.1913415, 0.0], [-0.3535535, 0.3535535, 0.0], [-0.1913415, 0.46194, 0.0], [0.0, 0.5, 0.0], [0.0, 0.46194, -0.1913415], [0.0, 0.3535535, -0.3535535], [0.0, 0.1913415, -0.46194], [0.0, 0.0, -0.5], [-0.1913415, 0.0, -0.46194], [-0.3535535, 0.0, -0.3535535], [-0.46194, 0.0, -0.1913415], [-0.5, 0.0, 0.0], [-0.46194, 0.0, 0.1913415], [-0.3535535, 0.0, 0.3535535], [-0.1913415, 0.0, 0.46194], [0.0, 0.0, 0.5], [0.1913415, 0.0, 0.46194], [0.3535535, 0.0, 0.3535535], [0.46194, 0.0, 0.1913415], [0.5, 0.0, 0.0], [0.46194, 0.0, -0.1913415], [0.3535535, 0.0, -0.3535535], [0.1913415, 0.0, -0.46194], [0.0, 0.0, -0.5]])

		#rename shape
		shpList = cmds.listRelatives(crvName, shapes=True)

		for shpName in shpList:

			cmds.rename(shpName, crvName + 'Shape')

		#adjust shape
		cvList = cmds.ls(crvName + '.cv[*]')

		#pos
		cmds.move(posList[0], posList[1], posList[2], cvList, r=True)

		#rotate
		cmds.rotate(rotList[0], rotList[1], rotList[2], cvList, p=rotPivot)

		#scale
		cmds.scale(sclList[0], sclList[1], sclList[2], cvList, p=sclPivot)

	def creFollicle(self, objName, folName,  uValue, vValue):

		fol = cmds.createNode('transform', n = folName, ss=True)
		folShape = cmds.createNode('follicle', n = folName +'Shape', p = fol, ss=True)

		cmds.connectAttr(objName + '.local', folShape + '.inputSurface')
		cmds.connectAttr(objName + '.worldMatrix[0]', folShape + '.inputWorldMatrix')
		cmds.connectAttr(folShape + '.outRotate', fol + '.rotate')
		cmds.connectAttr(folShape + '.outTranslate', fol + '.translate')

		cmds.setAttr(fol + '.inheritsTransform', False)
		cmds.setAttr(fol + '.parameterU', uValue)
		cmds.setAttr(fol + '.parameterV', vValue)

	def creMotionPath(self, objName, crvName, mphName,follow=None, fractionMode=None, followAxis=None, upAxis=None, worldUpType=None, worldUpObject=None, uVal=None):

		#create node
		if cmds.objExists(mphName):

			cmds.delete(mphName)

		cmds.createNode('motionPath', n=mphName)

		#connect curve to motion path
		crvShpName = cmds.listRelatives(crvName, s=True)[0]
		cmds.connectAttr(crvShpName + '.worldSpace', mphName + '.geometryPath')

		#connect object
		cmds.connectAttr(mphName + '.allCoordinates.xCoordinate', objName + '.translate.translateX')
		cmds.connectAttr(mphName + '.allCoordinates.yCoordinate', objName + '.translate.translateY')
		cmds.connectAttr(mphName + '.allCoordinates.zCoordinate', objName + '.translate.translateZ')

		#fraction
		if fractionMode != None:
			cmds.setAttr(mphName + '.fractionMode', fractionMode)
		else:
			cmds.setAttr(mphName + '.fractionMode', False)

		#set axis values to avoid error
		cmds.pathAnimation(mphName, e=True, followAxis='y')
		cmds.pathAnimation(mphName, e=True, upAxis='x')

		#follow axis
		if followAxis != None:
			cmds.pathAnimation(mphName, e=True, followAxis=followAxis)
		else:
			cmds.pathAnimation(mphName, e=True, followAxis='z')

		#up axis
		if upAxis != None:
			cmds.pathAnimation(mphName, e=True, upAxis=upAxis)
		else:
			cmds.pathAnimation(mphName, e=True, upAxis='y')

		#world up type
		if worldUpType != None:
			cmds.pathAnimation(mphName, e=True, worldUpType=worldUpType)
		else:
			cmds.pathAnimation(mphName, e=True, worldUpType='scene')

		#world up object
		if worldUpObject != None:
			cmds.pathAnimation(mphName, e=True, worldUpObject=worldUpObject)

		#follow
		if follow != None:
			cmds.pathAnimation(mphName, e=True, follow=follow)
		else:
			cmds.pathAnimation(mphName, e=True, follow=True)

		#uValue
		if uVal != None:

			cmds.setAttr(mphName + '.uValue', uVal)

	def creSmartDuplicate(self, objName, cns=False, cnn = False):

		#get duplicated control name
		if ':' in objName:
			ctlDupName = objName.replace(':', '__NMSP__') + '_CTL'
			locName = objName.replace(':', '__NMSP__') + '_LOC'

		else:
			ctlDupName = objName + '_CTL'
			locName = objName + '_LOC'

		#delete if exists
		if cmds.objExists(ctlDupName):
			cmds.delete(ctlDupName)

		#duplicate transform and change rot order
		cmds.duplicate(objName, n = ctlDupName,  parentOnly=True)
		cmds.setAttr(ctlDupName + '.rotateOrder', 2)

		#unparent
		if cmds.listRelatives(ctlDupName, parent=True) != None:
			cmds.parent(ctlDupName, w=True)

		#reset position of duplicated transfrom node
		cmds.makeIdentity(ctlDupName, apply=False ,t=1,r=1, s=1)

		#unlock and unhide basic attributes
		cmds.setAttr(ctlDupName + '.tx', lock=False, keyable=True)
		cmds.setAttr(ctlDupName + '.ty', lock=False, keyable=True)
		cmds.setAttr(ctlDupName + '.tz', lock=False, keyable=True)

		cmds.setAttr(ctlDupName + '.rx', lock=False, keyable=True)
		cmds.setAttr(ctlDupName + '.ry', lock=False, keyable=True)
		cmds.setAttr(ctlDupName + '.rz', lock=False, keyable=True)

		cmds.setAttr(ctlDupName + '.sx', lock=False, keyable=True)
		cmds.setAttr(ctlDupName + '.sy', lock=False, keyable=True)
		cmds.setAttr(ctlDupName + '.sz', lock=False, keyable=True)

		#get bounding box average
		avg = self.getBBXAverage(objName)/2

		#create control
		ctlTmpName = ctlDupName + 'tmp'

		if cmds.objExists(ctlTmpName):
			cmds.delete(ctlTmpName)

		self.creControl(ctlTmpName, 'cube', dimensionList = [avg, avg, avg])

		#create locator and snap to control
		if cmds.objExists(locName):
			cmds.delete(locName)

		cmds.spaceLocator(n=locName)
		cmds.parentConstraint(objName, locName, n='tmp_CNS')
		cmds.delete('tmp_CNS')
		
		#parent shape
		cmds.parent(ctlTmpName + 'Shape', ctlDupName, s=True, r=True)

		#delete tmp
		cmds.delete(ctlTmpName)

		cmds.parent(ctlDupName, locName)
		cmds.makeIdentity(ctlDupName, apply=False ,t=1,r=1, s=1)

		#color control
		self.setColor(ctlDupName, (.4,.3,.5))
		cmds.select(cl=True)

		#constraint orignal control to duplicated control
		if cns:
			self.creSmartConstraint(ctlDupName, objName, 'trs')

		#connect rest attributes
		if cnn:
			attrList = self.getAttrInfoList(ctlDupName, 'custom')

			if attrList != None:

				for attrName in attrList:

					cmds.connectAttr(ctlDupName + '.' + attrName, objName + '.' + attrName, f=True)

	def creMaterial(self, materialType, colorName, colorList, transparent = None):

		#make basic names
		materialName = colorName
		shadingGroupName = colorName + '_MATSG'
		
		#create material
		if cmds.objExists(materialName) == False:
		
			cmds.shadingNode(materialType,asShader=True, n = materialName)
			
			#create shading group
		if cmds.objExists(shadingGroupName) == False:

			cmds.sets(renderable = True, noSurfaceShader = True, empty = True, name = shadingGroupName)

		#change color
		if materialType == 'lambert':

			cmds.setAttr(materialName + '.color', colorList[0], colorList[1], colorList[2], type = 'double3')

		#make transparent
		if transparent == 'transparent':

			cmds.setAttr(materialName + '.outTransparency', 1, 1, 1, type = 'double3')

		cmds.select(cl = True)

	def creCluster(self, clsName, cvName):

		cmds.cluster(cvName, n = clsName)
		cmds.rename(clsName + 'Handle', 'tmp_CLS')
		cmds.rename('tmp_CLS', clsName)

	def creGroup(self, grpName):

		if cmds.objExists(grpName):
			cmds.delete(grpName)
	
		cmds.group(n=grpName, em=True)

	#GET
	def getCurrentPanel(self):

		selectedPanel = cmds.getPanel(wf = True)
		allPanelList = cmds.getPanel(visiblePanels = True)
		firstPanel = allPanelList[0]
		
		if 'modelPanel' not in selectedPanel:
			return firstPanel
		else:
			return selectedPanel

	def getAttrInfoList(self, objectName, function):

		attrKeyableList = []
		attrKeyedList = []

		#get keyable attributes

		#get all attributes in channelBox
		attributeList = cmds.listAttr(objectName, keyable = True, unlocked = True)

		if attributeList:

			#add only not connected attributes
			for attributeName in attributeList:

					if cmds.listConnections(objectName + '.' + attributeName, destination = False) == None:

						attrKeyableList.append(attributeName)

			#add non keyable attributes
			unkeyableattrKeyableList = cmds.listAttr(objectName, channelBox = True)

			if unkeyableattrKeyableList != None:

				attrKeyableList = attrKeyableList + cmds.listAttr(objectName, channelBox = True)

			#add keyed attributes
			for attributeName in attributeList:

				keyframeList = cmds.keyframe(objectName, at = attributeName, q = True)

				if keyframeList != None:

					attrKeyableList = attrKeyableList + [attributeName]

			attrKeyableList = sorted(self.funRemoveDuplicates(attrKeyableList))

			#get keyed addributes
			for attrKeyable in attrKeyableList:

				if cmds.keyframe(objectName, q = True, at= attrKeyable, name = True) != None:

					attrKeyedList.append(attrKeyable)

			#return
			if function == 'keyable':

				return attrKeyableList

			if function == 'keyed':

				return attrKeyedList

			if function == 'custom':

				return  cmds.listAttr(objectName, ud = True)

	def getColorPicker(self, initialColor):
	
		cmds.colorEditor(rgb = initialColor)
		
		if cmds.colorEditor(query=True, result=True):
				
			return cmds.colorEditor(query=True, rgb=True)

		else:

			return None

	def getPromptDialog(self, title, textValue):

		result = cmds.promptDialog(
				title = title,
				message='Enter Value:',
				button=['OK', 'Cancel'],
				defaultButton='OK',
				cancelButton='Cancel',
				dismissString='Cancel',
				text = textValue)

		if result == 'OK':
			
			return str(cmds.promptDialog(query=True, text=True))

		else:

			return None

	def getData(self, objectName, attrName):

		extName = objectName.split('_')[-1]
		returnValue = None
	 
		if extName == 'NOD' or extName == 'SET':
			returnValue = cmds.getAttr(objectName + '.' + attrName)

		if  extName == 'WIGbtn':
			returnValue = cmds.button(objectName, **{'q':True, attrName:True})

		if  extName == 'WIGchb':
			returnValue = cmds.checkBox(objectName, **{'q':True, attrName:True})

		if  extName == 'WIGtxt':
			returnValue = cmds.textField(objectName, **{'q':True, attrName:True})

		if extName == 'WIGfrm':
			returnValue = cmds.frameLayout(objectName, **{'q':True, attrName:True})

		if extName == 'WIGrad':
			returnValue = cmds.radioCollection(objectName, **{'q':True, attrName:True})

		return returnValue

	def getObjTypeDict(self, objList):   

			transformList = []
			shapeList = []
			faceList = []
			auxList = []

			if objList:

				for objectName in objList:

					inheritList = cmds.nodeType(objectName, inherited=True)

					#DAG objects
					if 'dagNode' in inheritList:

						#transform
						if 'transform' in inheritList:
							transformList.append(objectName)
						 
						#shape
						elif 'shape' in inheritList and len(objectName.split('.')) == 1:
							shapeList.append(objectName)

						#control point
						elif 'controlPoint' in inheritList:
							#face
							if len(objectName.split('.')) == 2 and objectName.split('.')[1][0] == 'f':
								facList.append(objectName)
	 
							#aux
							else:
								auxList.append(objectName)
					#aux
					else:
						auxList.append(objectName)

				#return
				returnDict = {}

				familyLists = ['transform', 'shape', 'face', 'aux']

				for familyName in familyLists:

					familyList = vars()[familyName + 'List']
					 
					if familyList != []:
						returnDict[familyName] = familyList
					else:
						returnDict[familyName] = None
				 
				return returnDict

	def getViewportVis(self):

		currentPanel = self.getCurrentPanel()

		visDict = {}

		visTypeList = ['nurbsCurves', 
					  'nurbsSurfaces', 
					  'cv',
					  'hulls',
					  'polymeshes',
					  'subdivSurfaces',
					  'planes',
					  'lights',
					  'cameras',
					  'imagePlane',
					  'joints',
					  'ikHandles',
					  'deformers',
					  'dynamics',
					  'particleInstancers',
					  'fluids',
					  'hairSystems',
					  'follicles',
					  'nCloths',
					  'nParticles',
					  'nRigids',
					  'dynamicConstraints',
					  'locators',
					  'dimensions',
					  'pivots',
					  'handles',
					  'textures',
					  'strokes',
					  'motionTrails',
					  'pluginShapes',
					  'clipGhosts',
					  'greasePencils',
					  'gpuCacheDisplayFilter']

		for visTypeName in visTypeList:

			visTypeDict = {}
			visTypeDict[visTypeName] = True

			
			if visTypeName != 'gpuCacheDisplayFilter':

				visDict[visTypeName] = cmds.modelEditor(currentPanel, q = True, **visTypeDict)

			else:

				visDict[visTypeName] =  cmds.modelEditor(currentPanel, q = True, queryPluginObjects = 'gpuCacheDisplayFilter')

		return visDict

	def getTimeRange(self):

		aPlayBackSliderPython = mel.eval('$tmpVar=$gPlayBackSlider')

		range=cmds.timeControl(aPlayBackSliderPython, rangeArray=True, q=True)

		if range[1] - range[0] == 1.0:

			startFrame = cmds.playbackOptions(minTime=True, q=True)
			endFrame = cmds.playbackOptions(maxTime=True, q=True)
			
			return [startFrame, endFrame]

		else:

			return range

	def getChannelboxInfo(self, function):

		if function == 'attr':

			return cmds.channelBox('mainChannelBox', q = True, sma = True)

	def getClosestPointOnSurfaceList(self, surfaceName, pointTranslation, projectionXY = False, uv = False, position = False):

		surfaceShapeName = cmds.listRelatives(surfaceName, shapes = True)[0]
		closestNodeName = 'closestPointOnSurface_NOD'
		
		#create locator in given position
		tmpLocAName = 'tmpA_LOC'
		cmds.group(n = tmpLocAName, em = True)
		cmds.xform(tmpLocAName, t = pointTranslation)

		#if surface is nurbsSurface
		if cmds.objectType(surfaceShapeName) == 'nurbsSurface':

			#create closest point on furface node
			cmds.createNode('closestPointOnSurface', n = closestNodeName)
			#connect
			cmds.connectAttr(surfaceShapeName + '.worldSpace[0]', closestNodeName + '.inputSurface')
			cmds.connectAttr(tmpLocAName + '.translate', closestNodeName + '.inPosition')

		#if surface is mesh
		if cmds.objectType(surfaceShapeName) == 'mesh':

			#create closest point on furface node
			cmds.createNode('closestPointOnMesh', n = closestNodeName)
			#connect
			cmds.connectAttr(surfaceShapeName + '.worldMatrix[0]', closestNodeName + '.inputMatrix')
			cmds.connectAttr(surfaceShapeName + '.worldMesh[0]', closestNodeName + '.inMesh')
			cmds.connectAttr(tmpLocAName + '.translate', closestNodeName + '.inPosition')

		#create temp locator and align to translateY of close node
		tmpLocBName = 'tmpB_LOC'
		cmds.group(n = tmpLocBName, em = True)
		pointTranslationValueList = cmds.xform(tmpLocAName, t = True, q = True)
		cmds.xform(tmpLocBName, t = pointTranslationValueList)
		
		#reconnect to temp locator
		cmds.connectAttr(tmpLocBName + '.translate', closestNodeName + '.inPosition', f = True)

		#iterate position by closing in translate Y
		if projectionXY == True:

			for each in range(2):
				
				cmds.setAttr(tmpLocBName + '.translateY', cmds.getAttr(closestNodeName + '.position')[0][1]) 

		#get values
		uvValues = [cmds.getAttr(closestNodeName + '.parameterU'), cmds.getAttr(closestNodeName + '.parameterV')]
		positionValue = cmds.getAttr(closestNodeName + '.position')[0]

		#delete nodes
		cmds.delete(closestNodeName)
		cmds.delete(tmpLocAName)
		cmds.delete(tmpLocBName)

		#return
		if uv == True:

			return uvValues

		if position == True:

			return positionValue

	def getClosestOnCurve(self, objName, crvName, function):

		returnVal = None

		#uValue
		if function == 'uVal':

			#basic
			mphNode = 'node_MPH_TMP'
			locName = 'locator_LOC_TMP'
			uValAnimCurveName = 'node_MPH_TMP_uValue'

			precition = .001
			uVal = 0.0
			valDict = {}

			#create locator and attach it to courve
			cmds.spaceLocator(n=locName)
			cmds.pathAnimation(locName, c=crvName, n=mphNode, fm=True, follow=True)
			cmds.delete(uValAnimCurveName)
			
			#find uValue
			while uVal <= 1:

				#move
				cmds.setAttr(mphNode + '.uValue', uVal)

				#current values
				distCurrent = self.getDistance(locName, objName)

				#save in dictionary
				valDict[distCurrent] = uVal

				#increment
				uVal = uVal + precition

			#return
			returnVal = valDict[min(valDict.keys())]

			#delete
			cmds.delete(locName)

		#parametric and position
		if function == 'parametric' or function == 'position':

			#general info
			crvShapeName = cmds.listRelatives(crvName, s=True)[0]
			crvCvQuant = cmds.getAttr(crvShapeName + '.cp', s=1)

			#create node
			nodeName = 'NOD_TMP'
			cmds.createNode('nearestPointOnCurve', n = nodeName)

			#connect
			cmds.connectAttr(crvShapeName + '.worldSpace', nodeName + '.inputCurve')
			cmds.connectAttr(objName + '.translate', nodeName + '.inPosition')

			#return
			if function == 'parametric':

				returnVal = cmds.getAttr(nodeName + '.parameter')

			if function == 'position':

				returnVal = cmds.getAttr(nodeName + '.position')[0]

			#delete node
			cmds.delete(nodeName)

		return returnVal

	def getBBXAverage(self, objName):

		bbox = cmds.exactWorldBoundingBox(objName)

		xVal = abs(bbox[0]-bbox[3])
		yVal = abs(bbox[1]-bbox[4])
		zVal = abs(bbox[2]-bbox[5])

		average = (xVal + yVal + zVal)/3

		return average

	def getSceneInfoDict(self, company):

		mayaFolder = os.environ['MAYA_APP_DIR']
		scenePath = cmds.file(sn=True, q=True)
		sceneName = scenePath.split('.')[0].split('/')[-1]

		returnDict = {'mayaFolder':mayaFolder,
					  'scenePath':scenePath,
					  'sceneName':sceneName,
					  'project':None,
					  'sequence':None,
					  'shot':None,
					  'version':None
					 }


		if company == 'custom':

			returnDict['version'] = sceneName.split('_')[-1][1:]

		if company == 'rod':

			returnDict['project'] = scenePath.split('/')[3]
			returnDict['sequence'] = scenePath.split('/')[4]
			returnDict['shot'] = scenePath.split('/')[5]
			returnDict['version'] = sceneName.split('_')[-1][1:]

		return returnDict

	def getNamespace(self, objName = None):

		#take namespace from given object
		if objName:

			splitLen = len(objName.split(':'))

			if splitLen == 2:

				return objName.split(':')[0]

			if splitLen == 1:

				return None

		#take namespace form selection
		else:

			selList = cmds.ls(sl=True)
			namespaceList = []

			if selList:

				for selName in selList:

					if ':' in selName:

						namespaceList.append(selName.split(':')[0])
			
			namespaceList = self.funRemoveDuplicates(namespaceList)
			
			return namespaceList

	def getNoNamespace(self, objName):

		returnVal = None

		if objName:

			returnVal = objName.split(':')[-1]

		return returnVal

	def getDistance(self, objA, objB):

		traAlist = cmds.xform(objA, q=True, t=True, ws=True)
		traBlist = cmds.xform(objB, q=True, t=True, ws=True)

		return math.sqrt((traBlist[0] - traAlist[0])**2 + (traBlist[1] - traAlist[1])**2 + (traBlist[2] - traAlist[2])**2)

	def getPointPositionList(self, obj):

		returnList = []

		#LISTS
		if type(obj) == list:

			for objName in obj:

				locTmpName = 'LOC_TMP'
				cmds.spaceLocator(n=locTmpName)
				self.funSnap(objName, locTmpName, 't')
				returnList.append(cmds.xform(locTmpName, q=True, ws=True, t=True))
				cmds.delete(locTmpName)


		#STRINGS
		if type(obj) == str:

			shpList =  cmds.listRelatives(obj, s=True)

			for shpName in shpList:

				if cmds.objectType(shpName) == 'nurbsCurve':

					cvQuant = cmds.getAttr(shpName + '.cp',s=1)

					for cvIndex in range(0, cvQuant):

						returnList.append(cmds.pointPosition(shpName + '.cv[' + str(cvIndex) + ']'))

		return returnList

	#SET
	def setData(self, objectName, attrName, value):

		extName = objectName.split('_')[-1]

		if extName == 'NOD' or extName == 'SET':
			
			if type(value) == int:
				cmds.setAttr(objectName + '.' + attrName, value)
			
			if type(value) == str or type(value) == dict or type(value) == list:
				cmds.setAttr(objectName + '.' + attrName, value, type = 'string')

			if type(value) == unicode:
				cmds.setAttr(objectName + '.' + attrName, value, type = 'string')

			if type(value) == tuple:
				cmds.setAttr(objectName + '.' + attrName, value[0], value[1], value[2])

			if type(value) == bool:
				cmds.setAttr(objectName + '.' + attrName, value)

			if type(value) == float:
				cmds.setAttr(objectName + '.' + attrName, value)

		if extName == 'WIGbtn':
			cmds.button(objectName, **{'e':True, attrName:value})

		if extName == 'WIGchb':
			cmds.checkBox(objectName, **{'e':True, attrName:value})

		if extName == 'WIGfrm':
			cmds.frameLayout(objectName, **{'e':True, attrName:value})

		if extName == 'WIGrad':
			cmds.radioCollection(objectName, **{'e':True, attrName:value})

	def setPromptDialog(self, title, text):

		result = cmds.promptDialog(
				title = '',
				message=title,
				button=['OK', 'Cancel'],
				defaultButton='OK',
				cancelButton='Cancel',
				dismissString='Cancel',
				text = text)

		if result == 'OK':
			
			return str(cmds.promptDialog(query=True, text=True))

		else:

			return None

	def setViewportVis(self, visTypeDict):

		for visTypeName in visTypeDict:

			value = visTypeDict[visTypeName]
			
			visTypeCurrentDict = {}
			visTypeCurrentDict[visTypeName] = value

			if visTypeName != 'gpuCacheDisplayFilter':

				cmds.modelEditor(self.getCurrentPanel(), e = True, **visTypeCurrentDict)

			else:

				string = 'modelEditor -e -pluginObjects gpuCacheDisplayFilter ' + str(value).lower() + ' ' + self.getCurrentPanel()
				mel.eval(string)

	def setShapeVis(self, objectName, function):

		#selList = cmds.ls(sl=True)w
		transformList = self.getObjTypeDict([objectName])['transform']

		if transformList:
			
			for selName in transformList:
				
				for shapeName in cmds.listRelatives(selName, s=True):
					
					if shapeName:

						if function == 'show':

							cmds.setAttr(shapeName+'.visibility', 1)

						if function == 'hide':

							cmds.setAttr(shapeName+'.visibility', 0)

	def setColor(self, objectName, value):

		for shapeName in cmds.listRelatives(objectName, shapes=True):

			cmds.setAttr(shapeName + '.overrideEnabled', 1)
			cmds.setAttr(shapeName + '.overrideRGBColors', 1)
			cmds.setAttr(shapeName + '.overrideColorR', value[0])
			cmds.setAttr(shapeName + '.overrideColorG', value[1])
			cmds.setAttr(shapeName + '.overrideColorB', value[2])

	def setAttr(self, objName, at, function):

		if function == 'lockHide':

			if type(at) == str:

				if at == 't':

					cmds.setAttr(objName + '.tx', l=False, cb = False, k=False)
					cmds.setAttr(objName + '.ty', l=False, cb = False, k=False)
					cmds.setAttr(objName + '.tz', l=False, cb = False, k=False)

				elif at == 'r':

					cmds.setAttr(objName + '.rx', l=False, cb = False, k=False)
					cmds.setAttr(objName + '.ry', l=False, cb = False, k=False)
					cmds.setAttr(objName + '.rz', l=False, cb = False, k=False)

				elif at == 's':

					cmds.setAttr(objName + '.sx', l=False, cb = False, k=False)
					cmds.setAttr(objName + '.sy', l=False, cb = False, k=False)
					cmds.setAttr(objName + '.sz', l=False, cb = False, k=False)

				elif at == 'tr':

					cmds.setAttr(objName + '.tx', l=False, cb = False, k=False)
					cmds.setAttr(objName + '.ty', l=False, cb = False, k=False)
					cmds.setAttr(objName + '.tz', l=False, cb = False, k=False)

					cmds.setAttr(objName + '.rx', l=False, cb = False, k=False)
					cmds.setAttr(objName + '.ry', l=False, cb = False, k=False)
					cmds.setAttr(objName + '.rz', l=False, cb = False, k=False)

				elif at == 'trs':

					cmds.setAttr(objName + '.tx', l=False, cb = False, k=False)
					cmds.setAttr(objName + '.ty', l=False, cb = False, k=False)
					cmds.setAttr(objName + '.tz', l=False, cb = False, k=False)

					cmds.setAttr(objName + '.rx', l=False, cb = False, k=False)
					cmds.setAttr(objName + '.ry', l=False, cb = False, k=False)
					cmds.setAttr(objName + '.rz', l=False, cb = False, k=False)

					cmds.setAttr(objName + '.sx', l=False, cb = False, k=False)
					cmds.setAttr(objName + '.sy', l=False, cb = False, k=False)
					cmds.setAttr(objName + '.sz', l=False, cb = False, k=False)

				else:

					cmds.setAttr(objName + '.' + at, l=False, cb = False, k=False)

			if type(at) == list:

				for attrName in at:

					cmds.setAttr(objName + '.' + attrName, l=False, cb = False, k=False)

	#FUNCTIONS
	def funMute(self, objList, onOff, zeroCurrent=None, attrList=None):

		zeroFrame = -1000
		currentFrame = cmds.currentTime(q = True)
		
		#go to zero frame
		cmds.currentTime(zeroFrame, e = True, u = False)

		if objList != '' and objList != [] and objList != ['']:

			for objectName in objList:

				#only when transform 
				if cmds.objectType(objectName, isType='transform') == True:

					#get attr list
					if attrList == 'all':

						attrMuteList = self.getAttrInfoList(objectName, 'keyed')

					else:

						attrMuteList = attrList

					#mute
					if onOff == 1: 
										
						for attrName in attrMuteList:

							#current position
							if zeroCurrent == 'current':
								cmds.mute(objectName + '.' + attrName)

							#zero out attributes
							elif zeroCurrent == 'zero':
								
								if cmds.keyframe(objectName + '.' + attrName, q = True) != None:

									if attrName == 'visibility' or 'scale' in attrName:
										cmds.setAttr(objectName + '.' + attrName, 1)
									else:
										cmds.setAttr(objectName + '.' + attrName, 0)
									
									cmds.mute(objectName + '.' + attrName)
									cmds.cutKey(objectName, at = attrName, t = (zeroFrame, zeroFrame))

					#unmute
					if onOff == 0: 
											
						for attrName in self.getAttrInfoList(objectName, 'keyed'):

							cmds.mute(objectName + '.' + attrName, d = True)

		#back to current frame
		cmds.currentTime(currentFrame, e = True)

	def funRemoveDuplicates(self, listName):
	
		outputList = []
			
		for item in listName:

			if item not in outputList:

				outputList.append(item)

		return outputList

	def funKeyKeyedAttr(self, selList=None):
		
		if selList == None:

			selList = cmds.ls(sl = True)

		if selList:

			traList = self.getObjTypeDict(selList)['transform']

			if traList:

				for objName in traList:

					keyedAttributeList = []

					#get keyable attribute list
					attributeList = cmds.listAttr(objName, keyable = True)

					#get attributes with keys
					if attributeList:

						for attributeName in attributeList:

							keyList = cmds.keyframe(objName, query=True, valueChange=True, timeChange=True, at = attributeName, shape=False)
							
							if keyList != None:

								keyedAttributeList.append(attributeName)

					#set key for selection
					cmds.setKeyframe(objName, at = keyedAttributeList, shape=False)

	def funSnap(self, objSource, objTarget, function):

		cnsName = 'tmp_CNS'
		self.creSmartConstraint(objSource, objTarget, function, name=cnsName)

		#set keyframes if exists
		if 't' in function:

			if cmds.keyframe(objTarget, q=True, at='tx'):
				cmds.setKeyframe(objTarget, at='tx')

			if cmds.keyframe(objTarget, q=True, at='ty'):
				cmds.setKeyframe(objTarget, at='ty')

			if cmds.keyframe(objTarget, q=True, at='tz'):
				cmds.setKeyframe(objTarget, at='tz')

		if 'r' in function:

			if cmds.keyframe(objTarget, q=True, at='rx'):
				cmds.setKeyframe(objTarget, at='rx')

			if cmds.keyframe(objTarget, q=True, at='ry'):
				cmds.setKeyframe(objTarget, at='ry')

			if cmds.keyframe(objTarget, q=True, at='rz'):
				cmds.setKeyframe(objTarget, at='rz')

		if 's' in function:

			if cmds.keyframe(objTarget, q=True, at='sx'):
				cmds.setKeyframe(objTarget, at='sx')

			if cmds.keyframe(objTarget, q=True, at='sy'):
				cmds.setKeyframe(objTarget, at='sy')

			if cmds.keyframe(objTarget, q=True, at='sz'):
				cmds.setKeyframe(objTarget, at='sz')

		#delete constraint
		cmds.delete(cnsName)

	def funSimplifyCurve(self,objectName, timeTol):

		animCurveList = cmds.listConnections(objectName, t='animCurve')
		cmds.filterCurve(animCurveList, filter = 'simplify', tto =timeTol)

	def funFilterObjType(self, objList, objType):

		transformList = []
		shapeList = []
		faceList = []
		auxList = []

		for objectName in objList:

			inheritList = cmds.nodeType(objectName, inherited=True)

			#DAG objects
			if 'dagNode' in inheritList:

				#transform
				if 'transform' in inheritList:
					transformList.append(objectName)
				 
				#shape
				elif 'shape' in inheritList and len(objectName.split('.')) == 1:
					shapeList.append(objectName)

				#control point
				elif 'controlPoint' in inheritList:
					#face
					if len(objectName.split('.')) == 2 and objectName.split('.')[1][0] == 'f':
						facList.append(objectName)

					#aux
					else:
						auxList.append(objectName)
			#aux
			else:
				auxList.append(objectName)

		#return
		returnDict = {}

		familyLists = ['transform', 'shape', 'face', 'aux']

		for familyName in familyLists:

			familyList = vars()[familyName + 'List']

			if familyList != []:
				returnDict[familyName] = familyList
			else:
				returnDict[familyName] = None

		return returnDict[objType]

	def	funFilterEuler(self, objName):

		#get rotation curves
		animRotateCurveList = []
		animCurveList = cmds.listConnections(objName, t='animCurve')

		if animCurveList:

			for animCurve in animCurveList:

				if 'rotate' in animCurve:

					animRotateCurveList.append(animCurve)

			#apply euler filter
			if animRotateCurveList:

				cmds.filterCurve(animRotateCurveList)

	def funReloadHoldouts(self):

		if cmds.modelEditor(self.getCurrentPanel(), q = True, hos = True):

			cmds.modelEditor(self.getCurrentPanel(), e = True, hos = False)
			cmds.modelEditor(self.getCurrentPanel(), e = True, hos = True)

		else:

			cmds.modelEditor(self.getCurrentPanel(), e = True, hos = True)
			cmds.modelEditor(self.getCurrentPanel(), e = True, hos = False)

cc = common()
##############################################################################################
def res(function):

	returnVal = ''

	#GENERAL
	if function == 'selList':

		returnVal = cmds.ls(sl=True)

	if function == 'frameStart':

		returnVal = cc.getTimeRange()[0]

	if function == 'frameEnd':

		returnVal = cc.getTimeRange()[1]	

	if function == 'frameCurrent':

		returnVal = cmds.currentTime(q=True)

	#BAKE TO WORLD
	if function == 'bakeToWorldAttr':

		attrList = []

		if cmds.checkBox('bakeToWorldTra_WIGchb', q=True, v=True):
			attrList.extend(['tx','ty','tz'])
		if cmds.checkBox('bakeToWorldRot_WIGchb', q=True, v=True):
			attrList.extend(['rx','ry','rz'])

		returnVal = attrList

	if function == 'bakeToWorldCustom':

		returnVal = cmds.checkBox('bakeToWorldCustom_WIGchb', q=True, v=True)

	if function == 'bakeToWorldRotOrder':

		returnVal = cmds.optionMenu('world_WIGopt', q=True, sl=True)-1

	#BAKE TO AIM
	if function == 'bakeToAimCustom':

		returnVal = cmds.checkBox('bakeToAimCustom_WIGchb', q=True, v=True)

	#PIN TO WORLD
	if function == 'pinToWorldAttr':

		attrStr = ''

		if cmds.checkBox('pinToWorldTra_WIGchb', q=True, v=True):
			attrStr = 't'
		if cmds.checkBox('pinToWorldRot_WIGchb', q=True, v=True):
			attrStr = attrStr + 'r'

		returnVal = attrStr

	#SNAP TO OBJECT
	if function == 'snapToObjectAttr':

		attrStr = ''

		if cmds.checkBox('snapToObjectTra_WIGchb', q=True, v=True):
			attrStr = 't'
		if cmds.checkBox('snapToObjectRot_WIGchb', q=True, v=True):
			attrStr = attrStr + 'r'

		returnVal = attrStr

	if function == 'snapToObjectMo':

		returnVal = cmds.checkBox('snapToObjectMo_WIGchb', q=True, v=True)

	return returnVal

def funBakeToWorld():

	#getGeneralInfo()
	selList = res('selList')
	attrList = res('bakeToWorldAttr')
	
	if selList and attrList:

		#gather lists
		locList = []
		cnsList = []
		
		#custom on
		if res('bakeToWorldCustom'):

			if len(selList) == 2:

				selName = selList[1]
				locName = selList[1] + '_bakeToWorld_LOC'
				cnsName = selList[1] + '_bakeToWorld_CNS'

				# #delete constraints if exist
				# cmds.delete(selName, constraints=True)

				#delete locator if exists
				if cmds.objExists(locName):
					cmds.delete(locName)

				#rename custom locator
				cmds.rename(selList[0], locName)

				#parent to control
				cmds.parentConstraint(selName, locName, n = cnsName, mo=True)

				#append to loc and cns list
				locList.append(locName)
				cnsList.append(cnsName)

				#repopulate selection list
				selList = [selName]

		#custom off
		else:

			for selName in selList:

				locName = selName + '_bakeToWorld_LOC'
				cnsName = selName + '_bakeToWorld_CNS'

				# #delete constraints if exist
				# cmds.delete(selName, constraints=True)

				#delete loc if exists
				if cmds.objExists(locName):
					cmds.delete(locName)

				#create locator
				cmds.spaceLocator(n = locName)

				#change locator's rotation order
				cmds.setAttr(locName + '.rotateOrder', res('bakeToWorldRotOrder'))

				#parent to control
				cmds.parentConstraint(selName, locName, n = cnsName)

				#append to loc and cns list
				locList.append(locName)
				cnsList.append(cnsName)

		#check if anything in the list
		if locList:

			#save viewpoert vis
			viewportVit = cc.getViewportVis()

			#turn off everything
			cmds.modelEditor(cc.getCurrentPanel(), e=True, allObjects=False)

			#bake locators
			cmds.bakeResults(locList, at=attrList, t = (res('frameStart'),res('frameEnd')), simulation=True)
			
			#delete constrains
			cmds.delete(cnsList)

			#constraint controls to locators
			for selName in selList:

				index = selList.index(selName)

				locName = locList[index]
				
				if res('bakeToWorldCustom'):

					cc.creSmartConstraint(locName, selName, attrList, mo=True)

				else:

					cc.creSmartConstraint(locName, selName, attrList)

				#apply euler filter
				cc.funFilterEuler(locName)

			#load visibility stuff
			cc.setViewportVis(viewportVit)

			#select
			cmds.select(locList)

			#reload holdouts
			cc.funReloadHoldouts()

def funBakeToCam(function):

	selList = res('selList')

	if function == 'pickCam':

		if selList:

			if len(selList) == 1:

				selName = selList[0]

				if cmds.objectType(cmds.listRelatives(selName, shapes=True)[0]) == 'camera':

					cmds.button('pickCam_WIGbtn', l = selName, bgc=(.6,.4,.8), e=True)

	if function == 'bake':

		
		#getGeneralInfo()
		camName = cmds.button('pickCam_WIGbtn', q=True, l = True)

		#create camera locator
		if cmds.objExists(camName):

			camLocName = camName + '_bakeToCam_cns_LOC'
			camCnsName = camName + '_bakeToCam_cns_CNS'

			if not cmds.objExists(camLocName):
				
				cmds.spaceLocator(n =camLocName)
				cmds.parentConstraint(camName, camLocName, n=camCnsName)

			#create offset locators
			if selList:

				#save viewpoert vis
				viewportVit = cc.getViewportVis()

				#turn off everything
				cmds.modelEditor(cc.getCurrentPanel(), e=True, allObjects=False)

				locList = []
				cnsList = []
				
				for selName in selList:

					#delete constraints if exist
					cmds.delete(selName, constraints=True)

					locName = selName + '_bakeToCam_LOC'
					cnsName = selName + '_bakeToCam_CNS'

					if not cmds.objExists(locName):

						cmds.spaceLocator(n = locName)
						cmds.setAttr(locName + '.rotateOrder', 2)
						cmds.parentConstraint(selName, locName, n=cnsName)
						cmds.parent(locName, camLocName)

					#append to loc and cns list
					locList.append(locName)
					cnsList.append(cnsName)

				#bake locators
				cmds.bakeResults(locList, at=['tx','ty','tz','rx','ry','rz'], t = (res('frameStart'), res('frameEnd')), simulation=True)

				#constraint controls to locators
				for selName in selList:

					locName = selName + '_bakeToCam_LOC'
					cc.creSmartConstraint(locName, selName, 'tr')

					#apply euler filter and simplify
					cc.funFilterEuler(locName)

				#load visibility stuff
				cc.setViewportVis(viewportVit)

				#reload holdouts
				cc.funReloadHoldouts()

def funBakeToAim():

	def getVector(axis):

		if axis == 'X+':
			return (1,0,0)
		if axis == 'Y+':
			return (0,1,0)
		if axis == 'Z+':
			return (0,0,1)
		if axis == 'X-':
			return (-1,0,0)
		if axis == 'Y-':
			return (0,-1,0)
		if axis == 'Z-':
			return (0,0,-1)

	selList = res('selList')

	if selList:

		#save viewpoert vis
		viewportVit = cc.getViewportVis()

		#turn off everything
		cmds.modelEditor(cc.getCurrentPanel(), e=True, allObjects=False)

		locList = []
		cnsList = []

		#custom off
		if selList and len(selList) != 0:

			sourceLocName = ''

			if len(selList) == 2 and res('bakeToAimCustom'):

				sourceLocName = selList[0]
				selList = [selList[1]]
				
			for selName in selList:

				aimAxis = cmds.optionMenu('aim_WIGopt', q=True, v=True)
				pvAxis = cmds.optionMenu('pv_WIGopt', q=True, v=True)

				aimDist = int(cmds.textField('aim_WIGopt', q=True, tx=True))
				pvDist = int(cmds.textField('pv_WIGopt', q=True, tx=True))

				if '-' in aimAxis:
					aimDist = -aimDist

				if '-' in pvAxis:
					pvDist = -pvDist
				
				locAimName = selName + '_bakeToAim_aim_LOC'
				locPvName = selName + '_bakeToAim_pv_LOC'
				
				cnsName = selName + '_bakeToAim_CNS'
				cnsAimName = selName + '_bakeToAim_aim_CNS'
				cnsPvName = selName + '_bakeToAim_pv_CNS'

				guideName = selName + '_guideLine'

				#delete constraints if exist
				cmds.delete(selName, constraints=True)

				#delete if aim exists
				if cmds.objExists(locAimName):
					cmds.delete(locAimName)

				if cmds.objExists(locPvName):
					cmds.delete(locPvName)

				#create aim locator and reposition
				if res('bakeToAimCustom'):

					cmds.spaceLocator(n = locAimName)
					cc.funSnap(sourceLocName, locAimName, 'tr')
					cmds.delete(sourceLocName)
					
				else:

					cmds.spaceLocator(n = locAimName)
					cmds.parent(locAimName, selName)
					cmds.xform(locAimName, t=[0,0,0])
					cmds.xform(locAimName, ro=[0,0,0])
					argAxisAim = {}; argAxisAim[str(aimAxis[0].lower())] = True
					cmds.move(aimDist, locAimName, os=True, r=True, **argAxisAim)
					cmds.parent(locAimName, world=True)
				


				#create pv locator and reposition
				cmds.spaceLocator(n = locPvName)
				cmds.parent(locPvName, locAimName)
				cmds.xform(locPvName, t=[0,0,0])
				cmds.xform(locPvName, ro=[0,0,0])
				
				argAxisPv = {}; argAxisPv[str(pvAxis[0].lower())] = True
				cmds.move(pvDist, locPvName, os=True, r=True, **argAxisPv)

				cmds.parent(locPvName, world=True)
				
				#zero rotations
				cmds.xform(locAimName, ro=[0,0,0])
				cmds.xform(locPvName, ro=[0,0,0])
				
				#constraint locators
				cmds.parentConstraint(selName, locAimName, mo=True, n = cnsAimName)
				cmds.parentConstraint(selName, locPvName, mo=True, n = cnsPvName)
				
				#append to list
				locList.append(locAimName)
				locList.append(locPvName)
				cnsList.append(cnsAimName)
				cnsList.append(cnsPvName)

				#create guide lines between control and aim ans pv locators
				cc.creNPointGuideLine(guideName, [selName, locAimName, locPvName], True)
				cmds.parent(guideName + '_GRP', locAimName)

				#select control
				cmds.select(selName)
				
			#bake locators
			cmds.bakeResults(locList, at=['tx','ty','tz'], t = (res('frameStart'), res('frameEnd')), simulation=True)

			#delete constrains
			cmds.delete(cnsList)
			
			#create aim constraint on control
			for selName in selList:

				locAimName = selName + '_bakeToAim_aim_LOC'
				locPvName = selName + '_bakeToAim_pv_LOC'
				cnsName = selName + '_bakeToAim_CNS'
				maitainOffset = False

				if res('bakeToAimCustom'):

					maitainOffset = True

				cmds.aimConstraint(locAimName, selName, n = cnsName, aimVector = getVector(aimAxis), upVector=getVector(pvAxis), worldUpObject = locPvName, worldUpType = 'object', mo=maitainOffset)

		#load visibility stuff
		cc.setViewportVis(viewportVit)

		#reload holdouts
		cc.funReloadHoldouts()

def funPinToWorld(function):

	selList = res('selList')
	attrStr = res('pinToWorldAttr')

	#bake
	if selList and attrStr:

		#key checked attributes
		cmds.setKeyframe(selList, at = list(attrStr))

		if function == 'range':

			#save viewpoert vis
			viewportVis = cc.getViewportVis()

			#turn off everything
			cmds.modelEditor(cc.getCurrentPanel(), e=True, allObjects=False)

			#iterate
			for frame in range(int(res('frameStart')-1), int(res('frameEnd'))):

				cmds.currentTime(frame)

				for selName in selList:

					#create temp group
					tmpName = 'TMP'
					if cmds.objExists(tmpName):
						cmds.delete(tmpName)
					cmds.group(n=tmpName, em=True)
					cc.funSnap(selName, tmpName, attrStr)

					#go frame forward and snap to tmp
					cmds.currentTime(frame+1)
					cc.funSnap(tmpName, selName, attrStr)
					cmds.currentTime(frame)

					#delete tmp
					cmds.delete(tmpName)

			#load visibility stuff
			cc.setViewportVis(viewportVis)

		if function == 'left' or function == 'right':

			#get current frame
			frame = res('frameCurrent')

			#get next frame
			if function == 'left':
				frameNext = frame-1	
			if function == 'right':		
				frameNext = frame+1	

			#snap for all selection
			for selName in selList:

				#create temp group
				tmpName = 'TMP'
				cc.creGroup(tmpName)
				cc.funSnap(selName, tmpName, attrStr)
				cmds.currentTime(frameNext)

				cc.funSnap(tmpName, selName, attrStr)
				cmds.currentTime(frame)

				#delete tmp
				cmds.delete(tmpName)

			#move to next frame
			cmds.currentTime(frameNext)

		#select
		cmds.select(selList)

		#reload holdouts
		cc.funReloadHoldouts()

def funSnapToObject(function):

	selList = res('selList')
	attrStr = res('snapToObjectAttr')
	frame = res('frameCurrent')

	if selList and len(selList) >= 2 and attrStr:

		#get source name
		sourceName = selList[0]

		#create pivot group
		grpPivotName = 'pivot_TMP'
		cc.creGroup(grpPivotName)
		cc.creSmartConstraint(sourceName, grpPivotName, attrStr)
		
		if function == 'range':

			#save viewpoert vis
			viewportVis = cc.getViewportVis()

			#turn off everything
			cmds.modelEditor(cc.getCurrentPanel(), e=True, allObjects=False)

			#create offset group if checked
			if res('snapToObjectMo'):

				for selName in selList:

					if selName != sourceName:		

						grpOffsetName = selName + '_offset_TMP'
						cc.creGroup(grpOffsetName)
						cmds.parent(grpOffsetName, grpPivotName)
						cc.funSnap(selName, grpOffsetName, 'tr')

			#bake
			for frameCounter in range(int(res('frameStart')), int(res('frameEnd'))+1):

				cmds.currentTime(frameCounter)

				#iterate for every target
				for selName in selList:

					if selName != sourceName:

						#key checked attributes
						cmds.setKeyframe(selName, at = list(attrStr))
				
						#maintain offset on
						if res('snapToObjectMo'):

							#snap target to offset group
							grpOffsetName = selName + '_offset_TMP'
							cc.funSnap(grpOffsetName, selName, attrStr)

						else:

							#snap target to pivot group
							cc.funSnap(grpPivotName, selName, attrStr)

						cmds.currentTime(frameCounter)

			#delete temp group
			cmds.delete(grpPivotName)

			#back to frame
			cmds.currentTime(frame)

			#load visibility stuff
			cc.setViewportVis(viewportVis)


		if function == 'left' or function == 'right':

			#get current frame
			frame = res('frameCurrent')

			#get next frame
			if function == 'left':
				frameNext = frame-1	
			if function == 'right':		
				frameNext = frame+1	

			#iterate for every target
			for selName in selList:

				if selName != sourceName:

					#maintain offset on
					if res('snapToObjectMo'):

						grpOffsetName = 'offset_TMP'
						cc.creGroup(grpOffsetName)
						cmds.parent(grpOffsetName, grpPivotName)
						cc.funSnap(selName, grpOffsetName, attrStr)

						#move to next frame
						cmds.currentTime(frameNext)

						#snap target to offset group
						cc.funSnap(grpOffsetName, selName, attrStr)

					else:

						#move to next frame
						cmds.currentTime(frameNext)

						#snap target to pivot group
						cc.funSnap(grpPivotName, selName, attrStr)

					cmds.currentTime(frame)

					#key checked attributes
					cmds.setKeyframe(selName, at = list(attrStr))

			#move to next frame
			cmds.currentTime(frameNext)

			#delete temp group
			cmds.delete(grpPivotName)

		#back to selection
		cmds.select(selList)

		#reload holdouts
		cc.funReloadHoldouts()

def bakeAndCleanup():

	selList = res('selList')

	#get bake selection list and locator list
	bakeList = []
	selLocList = []
	delList = []

	if selList:

		for selName in selList:

			#selected control
			
			#world space
			if cmds.objExists(selName + '_bakeToWorld_LOC'):
				
				bakeList.append(selName)
				delList.extend(cmds.ls(selName + '_bakeToWorld_LOC'))

			#camera space
			if cmds.objExists(selName + '_bakeToCam_LOC'):
				
				bakeList.append(selName)
				delList.extend(cmds.ls(selName + '_bakeToCam_LOC'))

			#aim
			if cmds.objExists(selName + '_bakeToAim_aim_LOC'):

				bakeList.append(selName)
				delList.extend(cmds.ls(selName + '_bakeToAim_*_LOC'))

			#selected locator

			#world space
			if len(selName.split('_bakeToWorld_LOC')) == 2:

				bakeList.append(selName.split('_bakeToWorld_LOC')[0])
				delList.append(selName)

			#camera space locator
			if len(selName.split('_bakeToCam_LOC')) == 2:

				bakeList.append(selName.split('_bakeToCam_LOC')[0])
				delList.append(selName)

			#camera space constraint loc
			if len(selName.split('_bakeToCam_cns_LOC')) == 2:

				childrenList = cmds.listRelatives(selName, children=True, type= 'transform')

				for childrenName in childrenList:
					if '_CNS' not in childrenName:
						bakeList.append(childrenName.split('_bakeToCam_LOC')[0])

				delList.append(selName)

			#aim
			if len(selName.split('_bakeToAim_aim_LOC')) == 2:
			
				bakeList.append(selName.split('_bakeToAim_aim_LOC')[0])
				delList.append(selName)
				delList.append(selName.replace('_aim_', '_pv_'))

			if len(selName.split('_bakeToAim_pv_LOC')) == 2:
			
				bakeList.append(selName.split('_bakeToAim_pv_LOC')[0])
				delList.append(selName)
				delList.append(selName.replace('_pv_', '_aim_'))
			
	bakeList = cc.funRemoveDuplicates(bakeList)
	delList = cc.funRemoveDuplicates(delList)
	camSpaceLocList = cmds.ls()

	if bakeList and delList:

		#save viewpoert vis
		viewportVis = cc.getViewportVis()

		#turn off everything
		cmds.modelEditor(cc.getCurrentPanel(), e=True, allObjects=False)

		#bake
		cmds.bakeResults(bakeList, at=['tx','ty','tz','rx','ry','rz'], t = (res('frameStart'), res('frameEnd')), simulation=True, preserveOutsideKeys=True)

		#delete locator if exists
		cmds.delete(delList)

		#load visibility stuff
		cc.setViewportVis(viewportVis)

		#apply euler filter and simplify
		for ctlName in bakeList:

			cc.funFilterEuler(ctlName)

	#delete camera contraint locator
	camSpaceLocList = []
	camSpaceLocList.extend(cmds.ls('*bakeToCam_cns_LOC'))
	camSpaceLocList.extend(cmds.ls('*:*bakeToCam_cns_LOC'))

	for camSpaceLocName in camSpaceLocList:

		if len(cmds.listRelatives(camSpaceLocName, children=True, type= 'transform')) == 1:

			cmds.delete(camSpaceLocName)

	#select controls
	cmds.select(bakeList)

	#reload holdouts
	cc.funReloadHoldouts()

def selectAll():

	bakeLocList = cmds.ls('*_bakeTo*_LOC') + cmds.ls('*:*_bakeTo*_LOC')

	if bakeLocList:

		cmds.select(bakeLocList)

def run():

	if (cmds.window('pBakery_WIGwin', exists=True)):
		cmds.deleteUI('pBakery_WIGwin')
	window = cmds.window('pBakery_WIGwin', title='pBakery v' + str(version), sizeable = 1, menuBar=True)

	#create main layout
	cmds.rowColumnLayout('pBakery_WIGlay')

	#BAKE TO WORLD
	def bakeToWorldCustomTgl():

		if cmds.checkBox('bakeToWorldCustom_WIGchb', q=True, v=True):
			cmds.optionMenu('world_WIGopt', e=True, en=False)
		else:
			cmds.optionMenu('world_WIGopt', e=True, en=True)

	cmds.separator(style='in', h=20, p = 'pBakery_WIGlay')

	#main
	cmds.rowColumnLayout('bakeWorld_WIGlay', nc = 4, cs=[(2,10), (3,10), (4,5)], p = 'pBakery_WIGlay')
	cmds.button(l = 'bake to WORLD', c=lambda *_:funBakeToWorld(), w=220)
	cmds.separator(style='in', horizontal=False)
	cmds.checkBox('bakeToWorldTra_WIGchb', v=True, l='t')
	cmds.checkBox('bakeToWorldRot_WIGchb', v=True, l='r')

	cmds.separator(style='none', h=3, p = 'pBakery_WIGlay')
	
	cmds.rowColumnLayout(nc = 2, p = 'pBakery_WIGlay', cs=[(1,10),(2,170)])
	cmds.checkBox('bakeToWorldCustom_WIGchb', v=False, l='custom', cc = lambda *_:bakeToWorldCustomTgl())
	cmds.optionMenu('world_WIGopt', label='')
	cmds.menuItem( label='xyz' )
	cmds.menuItem( label='yzx' )
	cmds.menuItem( label='zxy' )
	cmds.menuItem( label='xzy' )
	cmds.menuItem( label='yxz' )
	cmds.menuItem( label='zyx' )
	cmds.optionMenu('world_WIGopt', e=True, select = 3)

	cmds.separator(style='in', h=10, p = 'pBakery_WIGlay')

	#BAKE TO CAMERA
	cmds.rowColumnLayout('bakeToCam_WIGlay', nc = 2, cs=[(2,20)], p = 'pBakery_WIGlay')

	cmds.button(l = 'bake to CAMERA', c=lambda *_:funBakeToCam('bake'), w=100, h=30, p = 'bakeToCam_WIGlay')
	cmds.button('pickCam_WIGbtn', l = 'pick camera!', c=lambda *_:funBakeToCam('pickCam'), w=180, p = 'bakeToCam_WIGlay', bgc=(.1,.1,.1))

	cmds.separator(style='in', h=10, p = 'pBakery_WIGlay')

	#BAKE TO AIM
	cmds.rowColumnLayout('bakeAim_WIGlay', nc = 2, cs=[(2,20)], p = 'pBakery_WIGlay')
	cmds.rowColumnLayout('bakeAimBtn_WIGlay', nc = 1, p = 'bakeAim_WIGlay')
	cmds.rowColumnLayout('bakeAimOptions_WIGlay', nc = 3, p = 'bakeAim_WIGlay', cs=[(2,10), (3,10)])

	cmds.button(l = 'bake to AIM', c=lambda *_:funBakeToAim(), w=140, h=40, p = 'bakeAimBtn_WIGlay')

	#aim
	cmds.text(l = 'aim:', p = 'bakeAimOptions_WIGlay')
	cmds.optionMenu('aim_WIGopt', label='')
	cmds.menuItem( label='X+' )
	cmds.menuItem( label='Y+' )
	cmds.menuItem( label='Z+' )
	cmds.menuItem( label='X-' )
	cmds.menuItem( label='Y-' )
	cmds.menuItem( label='Z-' )
	cmds.textField('aim_WIGopt', tx = 5, w=40, p = 'bakeAimOptions_WIGlay')
	cmds.optionMenu('aim_WIGopt', e=True, select = 3)

	#pv
	cmds.text(l = 'pv:', p = 'bakeAimOptions_WIGlay')
	cmds.optionMenu('pv_WIGopt', label='')
	cmds.menuItem( label='X+' )
	cmds.menuItem( label='Y+' )
	cmds.menuItem( label='Z+' )
	cmds.menuItem( label='X-' )
	cmds.menuItem( label='Y-' )
	cmds.menuItem( label='Z-' )
	cmds.textField('pv_WIGopt', tx = 10, w=40, p = 'bakeAimOptions_WIGlay')
	cmds.optionMenu('pv_WIGopt', e=True, select = 2)
	cmds.separator(style='none', h=3, p = 'pBakery_WIGlay')

	#custom
	def bakeToAimCustomTgl():

		if cmds.checkBox('bakeToAimCustom_WIGchb', q=True, v=True):
			cmds.optionMenu('aim_WIGopt', e=True, en=False)
			cmds.textField('aim_WIGopt', e=True, en=False)
		else:
			cmds.optionMenu('aim_WIGopt', e=True, en=True)
			cmds.textField('aim_WIGopt', e=True, en=True)

	cmds.rowColumnLayout(nc = 1, p = 'pBakery_WIGlay', cs=[(1,10)])
	cmds.checkBox('bakeToAimCustom_WIGchb', v=False, l='custom', cc=lambda *_:bakeToAimCustomTgl())

	cmds.separator(style='in', h=10, p = 'pBakery_WIGlay')

	#PIN TO WORLD
	cmds.rowColumnLayout('pinToWorldlay', nc=6, cs=[(2,10), (3,10), (4,10), (5,10), (6,5)], p = 'pBakery_WIGlay')

	cmds.button(l = '<-', w=50, c=lambda *_:funPinToWorld('left'))
	cmds.button(l = 'pin to world', w=100, c=lambda *_:funPinToWorld('range'))
	cmds.button(l = '->', w=50, c=lambda *_:funPinToWorld('right'))
	cmds.separator(style='in', h=20, horizontal=False)
	cmds.checkBox('pinToWorldTra_WIGchb', v=True, l='t')
	cmds.checkBox('pinToWorldRot_WIGchb', v=True, l='r')
	cmds.separator(style='in', h=20, p = 'pBakery_WIGlay')

	#SNAP TO OBJECT
	cmds.rowColumnLayout(nc=6, cs=[(2,10), (3,10), (4,10), (5,10), (6,5)], p = 'pBakery_WIGlay')

	cmds.button(l = '<-', w=50, c=lambda *_:funSnapToObject('left'))
	cmds.button(l = 'snap to object', w=100, c=lambda *_:funSnapToObject('range'))
	cmds.button(l = '->', w=50, c=lambda *_:funSnapToObject('right'))
	cmds.separator(style='in', h=20, horizontal=False)
	cmds.checkBox('snapToObjectTra_WIGchb', v=True, l='t')
	cmds.checkBox('snapToObjectRot_WIGchb', v=True, l='r')

	cmds.rowColumnLayout(nc=1, cs=[(1,10)], p = 'pBakery_WIGlay')
	cmds.separator(style='none', h=5)
	cmds.checkBox('snapToObjectMo_WIGchb', v=True, l='maintain offset')

	cmds.separator(style='in', h=20, p = 'pBakery_WIGlay')

	#BAKE CONTROL AND CLEANUP LOCATORS
	cmds.rowColumnLayout('bake_WIGlay', nc=2, p = 'pBakery_WIGlay', cs=[(1,10), (2,10)])

	cmds.button(l = 'bake control(s) and delete locator(s)', w = 230, h = 30, p = 'bake_WIGlay', bgc=(.3,.6,.3), c=lambda *_:bakeAndCleanup())
	cmds.button(l = 'select all', w=50, c=lambda *_:selectAll())

	cmds.separator(style='none', h=10, p = 'pBakery_WIGlay')

	#show
	cmds.showWindow(window)
    
    
if __name__ == '__main__':
    run()