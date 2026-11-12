import datetime
import nuke

# Print performance info for the node type specified (eg: "Read")
def performance_timers(node_type='ALL'):
    if node_type == 'ALL':
        nodes = nuke.allNodes(group=nuke.root(), recurseGroups=True)
    else:
        nodes = [node for node in nuke.allNodes(group=nuke.root(), recurseGroups=True) if node.Class() == node_type]
    
    g_callCount = 0
    g_timeTakenWall = 0
    g_timeTakenCPU = 0
    
    for n in nodes:
        callCount = 0
        timeTakenWall = 0
        timeTakenCPU = 0
        print("\n", n.name())
        print("\tStore   ", n.performanceInfo(nuke.PROFILE_STORE))
        print("\tValidate", n.performanceInfo(nuke.PROFILE_VALIDATE))
        print("\tRequest ", n.performanceInfo(nuke.PROFILE_REQUEST))
        print("\tEngine  ", n.performanceInfo(nuke.PROFILE_ENGINE))
        
        p_dict = [n.performanceInfo(nuke.PROFILE_STORE),
                  n.performanceInfo(nuke.PROFILE_VALIDATE),
                  n.performanceInfo(nuke.PROFILE_REQUEST), 
                  n.performanceInfo(nuke.PROFILE_ENGINE)]
        for p in p_dict:
            callCount += p['callCount']
            timeTakenWall += p['timeTakenWall']
            timeTakenCPU += p['timeTakenCPU']
        
        g_callCount += callCount
        g_timeTakenWall += timeTakenWall
        g_timeTakenCPU += timeTakenCPU
        print('  TOTAL     \'callCount\':', callCount, '\'timeTakenWall\':', timeTakenWall, '\'timeTakenCPU:\'', timeTakenCPU)
    print('\nGRAND TOTAL \'callCount\':', g_callCount, '\'timeTakenWall\':', g_timeTakenWall, '\'timeTakenCPU:\'', g_timeTakenCPU)
    
    print('SECONDS     \'callCount\':', str(datetime.timedelta(microseconds=g_callCount).total_seconds()), '\'timeTakenWall\':', str(datetime.timedelta(microseconds=g_timeTakenWall).total_seconds()), '\'timeTakenCPU:\'', str(datetime.timedelta(microseconds=g_timeTakenCPU).total_seconds()))

if __name__ == '__main__' or __name__.find('eclipsePython') != -1:
    performance_timers(node_type='Read')

























