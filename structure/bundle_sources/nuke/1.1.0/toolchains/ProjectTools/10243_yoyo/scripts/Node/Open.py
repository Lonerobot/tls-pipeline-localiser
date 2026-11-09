import nuke
import os
   

# get recent files 


recentFilePaths = []
recentShotNames = []

for i in range(10):
    i += 1
    a = nuke.recentFile(i)
    recentFilePaths.append(a)

for i in recentFilePaths:
    recentShot = i.split("/").pop().split(".").pop(0)  
    recentShotNames.append(recentShot)


# create nuke open script pannel 


p = nuke.Panel("Open Shot")

p.addSingleLineInput('sceneNum',"")
p.addSingleLineInput('shotNum',"")

p.addEnumerationPulldown('Recent', recentShotNames)

p.addBooleanCheckBox('Open new session', False)
p.addBooleanCheckBox('Open Latest Version', True)

p.addButton('Cancel')
p.addButton('Open')
p.addButton('Open Recent')

ret = p.show()


newSession = p.value('Open new session') 
openLatest = p.value('Open Latest Version') 



# creat shot variables bassed in input values 


if ret == 1:   

    sceneNum = p.value('sceneNum') 
    shotNum = p.value('shotNum') 


# creat shot variables bassed on recent file


if ret == 2:

    recentShot = p.value('Recent')  

#create shot name 

shotName = "sc" + sceneNum + "-" + "sh" + shotNum 
fileName = "SR_" + shotName + "_comp_nk_default_v001.nk"
 

# define directorys 

mainDir = "Y:/SECURE PROJECTS/10111_SRIRACHA/shots/"

#create shot path

shotPath = mainDir + shotName + "/" + "work/comp/comp/nk/default/"
  
#create Fav Dir Path and names  

publishDirName = "Publish" 
shotPublishPath = mainDir + shotName + "/publish"

print(shotPublishPath)
print(publishDirName)
     
# define create and remove fav dirs functions

def createShotDirs():
    nuke.addFavoriteDir('-------','')
    nuke.addFavoriteDir(publishDirName,shotPublishPath)

    return;

def removeShotDirs():
    nuke.removeFavoriteDir('-------')
    nuke.removeFavoriteDir(publishDirName)
    return;


# open file 

versions = os.listdir(shotPath)
 
if ret == 0:

    print("cancled")

else:

    if versions == []:

        nuke.message('Such a file duth not exist :(')
          
           
    if openLatest == True:
                           
        newestShot = max(versions)
        stripAutoSave = newestShot.strip( '~' )
        openPath = shotPath + "/" + stripAutoSave

    else:

        versionPanel = nuke.Panel("versions")
        versionPanel.addEnumerationPulldown('versions', versions)
        versionPanel.addButton('Cancel')
        versionPanel.addButton('Open')

        versionPanelRet = versionPanel.show()

        openVersion = versionPanel.value('versions') 
        openVersionStrip = openVersion.strip(",").strip("[").strip("'")
        openPath = shotPath + "/" + openVersionStrip

            
    if newSession == True:

        nuke.scriptOpen(openPath) 
    
                    
    else:

        nuke.scriptClose()
        nuke.scriptOpen(openPath)   
                
    removeShotDirs()      
    createShotDirs()  


    
    


    






    


    




























