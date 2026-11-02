bl_info = {
	'name': 'Grease Pencil Surface Baker',
	'author': 'Daniel Salazar <daniel@patazanimation.com>',
	'version': (1, 0),
	'blender': (3, 5, 0),
	'location': 'Operator menu > Bake Grease Pencil Surface Deform',
	'description': 'Bake the selected grease pencil objects to their parent\'s surface deformation',
	'wiki_url': 'https://www.patazanimation.com/',
	'category': 'Animation',
}

import bpy

# --- OPERATORS

class GreasePencilSurfaceBaker (bpy.types.Operator):
	'''Bake the selected grease pencil objects to their parent's surface deformation'''
	bl_idname = 'object.gpencil_surface_baker'
	bl_label = 'Bake Grease Pencil Surface Deform'
	bl_options = {'REGISTER', 'UNDO'}
	
	def execute(self, context):
	
		objs = context.selected_objects

		for obj in objs:
			if obj.type == 'GPENCIL':
				mods = obj.grease_pencil_modifiers
				parent = obj.parent
				
				sdef = None
				
				# Find the sdef modifier if any
				for mod in mods:
					if mod.type == 'GP_SURFACEDEFORM':
						sdef = mod
				
				# Create modifier if it doesn't exist
				if not sdef:
					sdef = obj.grease_pencil_modifiers.new('Surface Deform', 'GP_SURFACEDEFORM')
				
				# Set the GP object's parent as the target
				if sdef.target == None:
					sdef.target = parent
				# Set the binding options
				sdef.curr_frame_or_all_frames = 'CURR_FRAME'
				sdef.curr_layer_or_all_layers = 'ALL_LAYERS'
				
				# Bind the sdef modifier
				context.view_layer.objects.active = obj
				bpy.ops.gpencil.gpencilsurdeform_bind(modifier=sdef.name)
		
		bpy.ops.gpencil.bake_grease_pencil_animation()
			
		return {'FINISHED'}

# --- REGISTER

classes = (
	GreasePencilSurfaceBaker,
)
 
reg_cls, unreg_cls = bpy.utils.register_classes_factory (classes)
 
 
def register():
	reg_cls()
 
def unregister():
	unreg_cls()
 
if __name__ == '__main__':
	register()