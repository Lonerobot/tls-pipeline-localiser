import bpy

from bpy.app.handlers import persistent

class ViewLayerItem(bpy.types.PropertyGroup):
    name: bpy.props.StringProperty(name="View Layer Name")

# Property group collection and index for storing view layers

def update_view_layers(scene=None):
    if scene is None:
        if bpy.context and hasattr(bpy.context, 'scene'):            
            scene = bpy.context.scene
        else:
            return

    if hasattr(scene, 'view_layer_switcher_collection'):
        scene.view_layer_switcher_collection.clear()
        for vl in scene.view_layers:
            item = scene.view_layer_switcher_collection.add()
            item.name = vl.name

    # Force an update of the panel to ensure UIList is refreshed
    for window in bpy.context.window_manager.windows:
        for area in window.screen.areas:
            if area.type == 'VIEW_3D':
                for space in area.spaces:
                    if space.type == 'VIEW_3D':
                        area.tag_redraw()

    # for window in bpy.context.window_manager.windows:
    #     for area in window.screen.areas:
    #         if area.type == 'VIEW_3D':
    #             area.tag_redraw()

def update_active_view_layer(self, context):
    scene = context.scene
    if self.view_layer_switcher_index < len(scene.view_layer_switcher_collection):
        view_layer_name = scene.view_layer_switcher_collection[self.view_layer_switcher_index].name
        context.window.view_layer = scene.view_layers[view_layer_name]

@persistent
def depsgraph_update_handler(scene):
    # Update view layers in a safe context
    print ("depsgraph_update_handler")
    if scene and hasattr(scene, 'view_layer_switcher_collection'):
        update_view_layers(scene)

@persistent
def depsgraph_update_pre_handler(scene, depsgraph):
    # Store the previous count in a custom property
    if not hasattr(scene, '_prev_view_layer_count'):
        scene['_prev_view_layer_count'] = len(scene.view_layers)
    else:
        scene['_prev_view_layer_count'] = len(scene.view_layers)

@persistent
def depsgraph_update_post_handler(scene, depsgraph):
    # Update view layers if the count has changed
    # if hasattr(scene, '_prev_view_layer_count') and scene._prev_view_layer_count != len(scene.view_layers):
    update_view_layers(scene)

@persistent
def load_post_handler(dummy):
    update_view_layers()

# Custom function to check for view layer count changes
def check_view_layer_changes(scene):
    # context = bpy.context
    # scene = context.scene
    
    if not hasattr(scene, "_prev_view_layer_count"):
        scene["_prev_view_layer_count"] = len(scene.view_layers)
    if len(scene.view_layers) != scene["_prev_view_layer_count"]:
        print ("TIMER FUNC CALL - update_view_layers")
        update_view_layers(scene)
        scene["_prev_view_layer_count"] = len(scene.view_layers)
    # return

def update_active_view_layer(self, context):
    scene = context.scene
    if self.view_layer_switcher_index < len(scene.view_layer_switcher_collection):
        view_layer_name = scene.view_layer_switcher_collection[self.view_layer_switcher_index].name
        context.window.view_layer = scene.view_layers[view_layer_name]

def register():
    bpy.utils.register_class(ViewLayerItem)
    bpy.types.Scene.view_layer_switcher_collection = bpy.props.CollectionProperty(type=ViewLayerItem)
    bpy.types.Scene.view_layer_switcher_index = bpy.props.IntProperty(update=update_active_view_layer)

    # bpy.app.handlers.depsgraph_update_pre.append(depsgraph_update_pre_handler)
    bpy.app.handlers.depsgraph_update_post.append(depsgraph_update_post_handler)

    bpy.app.handlers.load_post.append(load_post_handler)
    bpy.app.handlers.save_pre.append(load_post_handler)

def unregister():
    del bpy.types.Scene.view_layer_switcher_collection
    del bpy.types.Scene.view_layer_switcher_index
    bpy.utils.unregister_class(ViewLayerItem)

    # bpy.app.handlers.depsgraph_update_pre.remove(depsgraph_update_pre_handler)
    bpy.app.handlers.depsgraph_update_post.remove(depsgraph_update_post_handler)
    bpy.app.handlers.load_post.remove(load_post_handler)
    bpy.app.handlers.save_pre.remove(load_post_handler)
