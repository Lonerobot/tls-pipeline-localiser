import bpy
from .properties import update_view_layers

class OT_VIEWLAYER_switch(bpy.types.Operator):
    bl_idname = "viewlayer.switch"
    bl_label = "Switch View Layer"
    bl_description = "Switch to the selected view layer"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Render Setup'

    index: bpy.props.IntProperty()

    def execute(self, context):
        scene = context.scene
        view_layers = scene.view_layers
        
        if self.index < len(view_layers):
            view_layer_name = scene.view_layer_switcher_collection[self.index].name
            context.window.view_layer = view_layers[view_layer_name]
            return {'FINISHED'}
        else:
            return {'CANCELLED'}
        
# Define the refresh operator
class OT_VIEWLAYER_Refresh(bpy.types.Operator):
    bl_idname = "viewlayer.refresh"
    bl_label = "Refresh View Layers"
    bl_description = "Refresh the list of view layers in the UI"

    def execute(self, context):
        # Trigger a UI redraw by manually updating the view layers
        update_view_layers(context.scene)
        return {'FINISHED'}
    
def register():  
        bpy.utils.register_class(OT_VIEWLAYER_switch)
        bpy.utils.register_class(OT_VIEWLAYER_Refresh)

def unregister():
        bpy.utils.unregister_class(OT_VIEWLAYER_switch)
        bpy.utils.unregister_class(OT_VIEWLAYER_Refresh)



