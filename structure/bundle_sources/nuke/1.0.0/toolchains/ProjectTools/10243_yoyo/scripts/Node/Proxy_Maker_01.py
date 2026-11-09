'''
import os

Developed by Daniel Mark Miller at Molinare 05th June 2015
'''

import nuke, os
# import YourRenderFarmGui as farmGui

class ProxyMaker():
	''' class to create and render out proxies'''

	def __init__(self):
	    ''' Make proxies for all or selected read and write nodes'''
	    print('initializing...')
	    self.toRender=[]
	    self.selection=nuke.selectedNodes()
	    if self.selection==[]:
	        print('boya!')
	        self.selection=nuke.allNodes()
	    self.reads=self.grab_reads(self.selection)
	    self.writes=self.grab_writes(self.selection)
	    self.nodes=self.reads+self.writes
	    for node in self.nodes:
		self.make_proxy(node)
	    [n['selected'].setValue(False) for n in self.selection]
	    [n['selected'].setValue(True) for n in self.toRender]
	    print(nuke.selectedNodes()) ## remove print and send selected nodes to your launcher
	    ## farmGui.farmScriptExec(nuke.selectedNodes())


	def grab_reads(self, nodes):
	    '''grab every or every selected read node in the script'''
	    if nodes==[]:
		reads=[node for node in nuke.allNodes() if node.Class()=='Read']
	    else:
		reads=[node for node in nodes if node.Class()=='Read']
	    return reads

	def grab_writes(self, nodes):
	    '''grab every or every selected write node in the script'''
	    if nodes==[]:
		writes=[node for node in nuke.allNodes() if node.Class()=='Write']
	    else:
		writes=[node for node in nodes if node.Class()=='Write']

	    return writes


	def make_proxy(self, readorwrite):
	    ''' Check if proxy has value assigned and if not render proxy then assign value based on file path '''
	    proxy=readorwrite.knob('proxy')
	    proxypath=proxy.value()
	    filepath=readorwrite.knob('file').value()

	    # assign missing proxy paths
	    if not proxypath:
		proxypath=filepath.replace('plate', 'proxyPlate').replace('element', 'proxyElement')
		if proxypath==filepath:
		    path, name = os.path.split(filepath)
		    pName='proxy_'+name
		    pFolder=os.path.splitext(path)[0].replace('plate', 'proxy')
		    proxypath=os.path.join(path,pFolder, pName)
		proxy.setValue(proxypath)
		# we want to creat write nodes to render out proxy versions of Read nodes, but just assign a proxy path to Writes
	    if readorwrite.Class()==('Read'):
	    # Yes we are checking for frames even if the proxy path in the node was left blank
		allFrames, someFrames, type=self.check_for_frames(proxypath)
		if not allFrames and type=='sequence':
		    self.write_proxy(proxypath, readorwrite)

	def write_proxy(self, proxypath, read):
	    ''' Create write for each read and render out proxies'''
	    print('proxypath is %s') % proxypath
	    writename='WriteProxy'+read.knob('name').value()
	    if nuke.toNode(writename):
		return
	    proxyformat=nuke.nodes.Reformat(type='scale',scale='0.5', inputs=[read], label='[value type] [value scale]')
	    write=nuke.nodes.Write(name=writename,file=proxypath, colorspace=read.knob('colorspace').value(), inputs=[proxyformat])
	    self.toRender.append(write)


	def check_for_frames(self, path):
	    '''check for any rendered frames '''
	    first= int(nuke.root().knob('first_frame').value())
	    last = int(nuke.root().knob('last_frame').value())
	    frame=first
	    someFrames=False
	    allFrames=True
	    while frame<=last:
		framepath=''
		try:
		    framepath=path % frame
		    type='sequence'
		except:
		    isfile=os.path.isfile(path)
		    isdir=os.path.isdir(path)
		    if isfile==True:
		        someFrames=True; allFrames=True; type='file'
		        return someFrames, allFrames, type
		    elif isdir==True:
		        someFrames=False; allFrames=False; type='dir'
		        return someFrames, allFrames, type
		    else:
		        someFrames=False; allFrames=False; type='nothing'
		    return someFrames, allFrames, type
		isfile=os.path.isfile(framepath)
		if isfile==True:
		    someFrames=True
		else:
		    allFrames=False
		frame+=1
	    return someFrames, allFrames, type

def make_proxies():
    pm=ProxyMaker()




