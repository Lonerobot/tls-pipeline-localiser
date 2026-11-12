
import nuke
import os

# create nuke save script pannel 


p = nuke.Panel("Save Shot")

p.addSingleLineInput('sceneNum',"")
p.addSingleLineInput('shotNum',"")

p.addButton('Cancel')
p.addButton('Save')

ret = p.show()


# creat shot variables bassed in input values 


if ret == 1:   

    sceneNum = p.value('sceneNum') 
    shotNum = p.value('shotNum') 

else:
    print("canceled")

#create shot name 

shotName = "sc" + sceneNum + "-" + "sh" + shotNum 
fileName = "SR_" + shotName + "_comp_nk_default_v001.nk"
 

# define directorys 

mainDir = "Y:/SECURE PROJECTS/10111_SRIRACHA/shots/"

#create shot path

shotPath = mainDir + shotName + "/" + "work/comp/comp/nk/default/" 

savePath  = shotPath + fileName
  
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

if ret == 1:  

    if not os.path.exists(shotPath):
        os.makedirs(shotPath)

        nuke.scriptSaveAs(savePath)
                
        removeShotDirs()      
        createShotDirs()  
    else:
        nuke.message("file already exists")


    


    






    


    





























    




























