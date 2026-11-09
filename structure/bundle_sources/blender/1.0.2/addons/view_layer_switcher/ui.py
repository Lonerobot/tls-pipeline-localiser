import bpy
from . import bl_info

# Step 2: UIList Class
class VIEWLAYER_UL_list(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        view_layer = item.name
        icon_value = 'RESTRICT_VIEW_OFF' if view_layer == context.view_layer.name else 'RESTRICT_VIEW_ON'
        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            layout.label(text=view_layer, icon=icon_value)
        elif self.layout_type == 'GRID':
            layout.alignment = 'CENTER'
            layout.label(text=view_layer, icon=icon_value)

# Step 4: Panel to hold the UIList
class TL_PT_View_Layer_Switcher(bpy.types.Panel):
    bl_label = f"The Line - View Layer Switcher v{bl_info['version'][0]}.{bl_info['version'][1]}.{bl_info['version'][2]}"    
    bl_idname = "VIEWLAYER_PT_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Render Setup'
    bl_order = 1

    def draw(self, context):
        layout = self.layout
        # layout.scale_y = 1.2
        scene = context.scene

        view_layer_count = len(scene.view_layers)
        num_rows = min(view_layer_count, 7)
        row = layout.box()
        split = row.split(factor=0.7)
        split.label(text="Click to enable the current view layer")

        split.operator("viewlayer.refresh", text="Refresh Layers", icon="FILE_REFRESH")

        # ui experiment
        # row = layout.row()
        # split = row.split(factor=0.2)        
        # split.template_icon(1, scale=1.5)
        # split.label(text="V I E W  L A Y E R S")
        
        layout.template_list("VIEWLAYER_UL_list", "", scene, "view_layer_switcher_collection", scene, "view_layer_switcher_index",type='DEFAULT',columns=1, maxrows=num_rows)       


        

classes = (
    VIEWLAYER_UL_list,
    TL_PT_View_Layer_Switcher,
)

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)

