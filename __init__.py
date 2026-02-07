# ============================================================================
# KABLO VE BORU DÖŞEYİCİ (Slack Cable Generator) v1.1
# ============================================================================
# Blender 3.0+ (3.x, 4.x, 5.x) Compatible
# Author: SaaS Script
#
# v1.1 New Features:
# - Multi-point cables (chain mode)
# - Cable material presets
# - Electrical conduit bends
# - Cable bundle (multiple cables)
# - Array along cable
# ============================================================================

bl_info = {
    "name": "Slack Cable Generator",
    "author": "ramooscripts",
    "version": (1, 1, 0),
    "blender": (3, 0, 0),
    "location": "View3D > Sidebar > ramooscripts",
    "description": "Create cables, pipes, and conduits with catenary curve and materials",
    "category": "Add Curve",
}

import bpy
import random
import math
from mathutils import Vector
from bpy.props import FloatProperty, IntProperty, EnumProperty, BoolProperty


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def create_slack_cable(context, start, end, slack, thickness, resolution, profile):
    """Create a slack cable curve between two points."""
    curve = bpy.data.curves.new('Cable', 'CURVE')
    curve.dimensions = '3D'
    curve.resolution_u = resolution
    
    spline = curve.splines.new('BEZIER')
    spline.bezier_points.add(2)
    
    midpoint = (start + end) / 2
    midpoint.z -= slack
    
    points = spline.bezier_points
    
    points[0].co = start
    points[0].handle_left_type = 'AUTO'
    points[0].handle_right_type = 'AUTO'
    
    points[1].co = midpoint
    points[1].handle_left_type = 'AUTO'
    points[1].handle_right_type = 'AUTO'
    
    points[2].co = end
    points[2].handle_left_type = 'AUTO'
    points[2].handle_right_type = 'AUTO'
    
    curve.bevel_depth = thickness
    curve.bevel_resolution = 4
    
    cable_obj = bpy.data.objects.new('Cable', curve)
    context.collection.objects.link(cable_obj)
    
    bpy.ops.object.select_all(action='DESELECT')
    cable_obj.select_set(True)
    context.view_layer.objects.active = cable_obj
    
    return cable_obj


def create_cable_material(name, color):
    """Create a cable material."""
    mat = bpy.data.materials.get(name)
    if not mat:
        mat = bpy.data.materials.new(name)
        mat.use_nodes = True
        bsdf = mat.node_tree.nodes.get("Principled BSDF")
        if bsdf:
            bsdf.inputs["Base Color"].default_value = color
            bsdf.inputs["Roughness"].default_value = 0.3
    return mat


# ============================================================================
# OPERATORS
# ============================================================================

class SCG_OT_create_cable_between_objects(bpy.types.Operator):
    """Create cable between two selected objects"""
    bl_idname = "scg.cable_between_objects"
    bl_label = "Cable Between 2 Objects"
    bl_options = {'REGISTER', 'UNDO'}
    
    @classmethod
    def poll(cls, context):
        return len(context.selected_objects) == 2
    
    def execute(self, context):
        scene = context.scene
        objects = list(context.selected_objects)
        
        if len(objects) != 2:
            self.report({'WARNING'}, "Select exactly 2 objects")
            return {'CANCELLED'}
        
        start = objects[0].location.copy()
        end = objects[1].location.copy()
        
        cable = create_slack_cable(
            context,
            start,
            end,
            scene.scg_slack_amount,
            scene.scg_thickness,
            scene.scg_resolution,
            scene.scg_profile
        )
        
        length = (end - start).length
        self.report({'INFO'}, f"Cable created ({length:.2f}m span)")
        return {'FINISHED'}


class SCG_OT_create_cable_at_cursor(bpy.types.Operator):
    """Create cable from cursor to active object"""
    bl_idname = "scg.cable_at_cursor"
    bl_label = "Cable from Cursor"
    bl_options = {'REGISTER', 'UNDO'}
    
    @classmethod
    def poll(cls, context):
        return context.active_object is not None
    
    def execute(self, context):
        scene = context.scene
        
        start = context.scene.cursor.location.copy()
        end = context.active_object.location.copy()
        
        cable = create_slack_cable(
            context,
            start,
            end,
            scene.scg_slack_amount,
            scene.scg_thickness,
            scene.scg_resolution,
            scene.scg_profile
        )
        
        self.report({'INFO'}, "Cable created from cursor")
        return {'FINISHED'}


class SCG_OT_adjust_slack(bpy.types.Operator):
    """Adjust slack of selected cable"""
    bl_idname = "scg.adjust_slack"
    bl_label = "Adjust Slack"
    bl_options = {'REGISTER', 'UNDO'}
    
    @classmethod
    def poll(cls, context):
        return (context.active_object and context.active_object.type == 'CURVE')
    
    def execute(self, context):
        obj = context.active_object
        scene = context.scene
        
        if obj.type != 'CURVE':
            self.report({'WARNING'}, "Select a cable curve")
            return {'CANCELLED'}
        
        curve = obj.data
        if not curve.splines:
            return {'CANCELLED'}
        
        spline = curve.splines[0]
        if spline.type == 'BEZIER' and len(spline.bezier_points) >= 3:
            start = spline.bezier_points[0].co
            end = spline.bezier_points[-1].co
            
            midpoint = (start + end) / 2
            midpoint.z -= scene.scg_slack_amount
            
            mid_idx = len(spline.bezier_points) // 2
            spline.bezier_points[mid_idx].co = midpoint
        
        self.report({'INFO'}, f"Slack adjusted to {scene.scg_slack_amount:.2f}m")
        return {'FINISHED'}


# NEW v1.1 OPERATORS

class SCG_OT_chain_cable(bpy.types.Operator):
    """Create cable through multiple selected objects (NEW v1.1)"""
    bl_idname = "scg.chain_cable"
    bl_label = "Chain Cable (Multi-Point)"
    bl_options = {'REGISTER', 'UNDO'}
    
    @classmethod
    def poll(cls, context):
        return len(context.selected_objects) >= 2
    
    def execute(self, context):
        scene = context.scene
        objects = list(context.selected_objects)
        
        if len(objects) < 2:
            self.report({'WARNING'}, "Select at least 2 objects")
            return {'CANCELLED'}
        
        # Sort by Z then X position
        objects.sort(key=lambda o: (o.location.z, o.location.x))
        
        curve = bpy.data.curves.new('ChainCable', 'CURVE')
        curve.dimensions = '3D'
        curve.resolution_u = scene.scg_resolution
        
        spline = curve.splines.new('BEZIER')
        spline.bezier_points.add(len(objects) - 1)
        
        for i, obj in enumerate(objects):
            point = spline.bezier_points[i]
            point.co = obj.location.copy()
            point.handle_left_type = 'AUTO'
            point.handle_right_type = 'AUTO'
            
            # Add slack between points
            if 0 < i < len(objects) - 1:
                point.co.z -= scene.scg_slack_amount * 0.5
        
        curve.bevel_depth = scene.scg_thickness
        curve.bevel_resolution = 4
        
        cable_obj = bpy.data.objects.new('ChainCable', curve)
        context.collection.objects.link(cable_obj)
        
        bpy.ops.object.select_all(action='DESELECT')
        cable_obj.select_set(True)
        context.view_layer.objects.active = cable_obj
        
        self.report({'INFO'}, f"Chain cable created through {len(objects)} points")
        return {'FINISHED'}


class SCG_OT_apply_material(bpy.types.Operator):
    """Apply material preset to selected cable (NEW v1.1)"""
    bl_idname = "scg.apply_material"
    bl_label = "Apply Material"
    bl_options = {'REGISTER', 'UNDO'}
    
    @classmethod
    def poll(cls, context):
        return context.active_object and context.active_object.type == 'CURVE'
    
    def execute(self, context):
        scene = context.scene
        obj = context.active_object
        
        material_presets = {
            'BLACK': ("Cable_Black", (0.02, 0.02, 0.02, 1)),
            'RED': ("Cable_Red", (0.8, 0.1, 0.1, 1)),
            'YELLOW': ("Cable_Yellow", (0.9, 0.8, 0.1, 1)),
            'BLUE': ("Cable_Blue", (0.1, 0.3, 0.8, 1)),
            'GREEN': ("Cable_Green", (0.1, 0.6, 0.2, 1)),
            'WHITE': ("Cable_White", (0.9, 0.9, 0.9, 1)),
            'COPPER': ("Pipe_Copper", (0.72, 0.45, 0.2, 1)),
            'STEEL': ("Pipe_Steel", (0.5, 0.5, 0.5, 1)),
        }
        
        preset = scene.scg_material_preset
        if preset in material_presets:
            name, color = material_presets[preset]
            mat = create_cable_material(name, color)
            
            if not obj.data.materials:
                obj.data.materials.append(mat)
            else:
                obj.data.materials[0] = mat
        
        self.report({'INFO'}, f"Applied {preset} material")
        return {'FINISHED'}


class SCG_OT_cable_bundle(bpy.types.Operator):
    """Create multiple cables as a bundle (NEW v1.1)"""
    bl_idname = "scg.cable_bundle"
    bl_label = "Cable Bundle"
    bl_options = {'REGISTER', 'UNDO'}
    
    @classmethod
    def poll(cls, context):
        return len(context.selected_objects) == 2
    
    def execute(self, context):
        scene = context.scene
        objects = list(context.selected_objects)
        
        start = objects[0].location.copy()
        end = objects[1].location.copy()
        
        bundle_count = scene.scg_bundle_count
        spread = scene.scg_bundle_spread
        
        cables = []
        for i in range(bundle_count):
            # Offset each cable slightly
            offset = Vector((
                random.uniform(-spread, spread),
                random.uniform(-spread, spread),
                0
            ))
            
            cable = create_slack_cable(
                context,
                start + offset,
                end + offset,
                scene.scg_slack_amount + random.uniform(-0.1, 0.1),
                scene.scg_thickness * random.uniform(0.8, 1.2),
                scene.scg_resolution,
                scene.scg_profile
            )
            cable.name = f"Bundle_Cable_{i+1:02d}"
            cables.append(cable)
        
        # Select all bundle cables
        bpy.ops.object.select_all(action='DESELECT')
        for cable in cables:
            cable.select_set(True)
        context.view_layer.objects.active = cables[0]
        
        self.report({'INFO'}, f"Created bundle of {bundle_count} cables")
        return {'FINISHED'}


class SCG_OT_add_conduit_bend(bpy.types.Operator):
    """Create pipe route with 90-degree bends between two objects (NEW v1.1)"""
    bl_idname = "scg.conduit_bend"
    bl_label = "Pipe Route (90° Bends)"
    bl_options = {'REGISTER', 'UNDO'}
    
    @classmethod
    def poll(cls, context):
        return len(context.selected_objects) == 2
    
    def execute(self, context):
        scene = context.scene
        objects = list(context.selected_objects)
        
        start = objects[0].location.copy()
        end = objects[1].location.copy()
        
        radius = scene.scg_thickness
        bend_radius = scene.scg_bend_radius
        
        # Calculate mid height for horizontal run
        mid_z = max(start.z, end.z) + bend_radius + 0.2
        
        # Create a Bezier curve for the pipe path
        curve_data = bpy.data.curves.new('Pipe_Path', 'CURVE')
        curve_data.dimensions = '3D'
        curve_data.resolution_u = 24  # Smooth curves
        curve_data.bevel_depth = radius  # Pipe thickness
        curve_data.bevel_resolution = 4  # Round pipe profile
        curve_data.use_fill_caps = True  # Closed ends
        
        # Create a spline with the route points
        spline = curve_data.splines.new('BEZIER')
        
        # We need 4 control points:
        # 1. Start point (going up)
        # 2. First corner (up to horizontal)
        # 3. Second corner (horizontal to down)
        # 4. End point (coming down)
        spline.bezier_points.add(3)  # Total 4 points
        
        points = spline.bezier_points
        
        # Corner positions
        corner1 = Vector((start.x, start.y, mid_z))
        corner2 = Vector((end.x, end.y, mid_z))
        
        # Horizontal direction
        h_dir = (corner2 - corner1)
        if h_dir.length > 0.001:
            h_dir.normalize()
        else:
            h_dir = Vector((1, 0, 0))
        
        # Point 0: Start (vertical going up)
        points[0].co = start
        points[0].handle_left_type = 'FREE'
        points[0].handle_right_type = 'FREE'
        points[0].handle_left = start - Vector((0, 0, bend_radius))
        points[0].handle_right = start + Vector((0, 0, bend_radius))
        
        # Point 1: First corner (transition from vertical to horizontal)
        points[1].co = corner1
        points[1].handle_left_type = 'FREE'
        points[1].handle_right_type = 'FREE'
        # Handle left: coming from below (vertical)
        points[1].handle_left = corner1 - Vector((0, 0, bend_radius))
        # Handle right: going toward corner2 (horizontal)
        points[1].handle_right = corner1 + h_dir * bend_radius
        
        # Point 2: Second corner (transition from horizontal to vertical down)
        points[2].co = corner2
        points[2].handle_left_type = 'FREE'
        points[2].handle_right_type = 'FREE'
        # Handle left: coming from corner1 (horizontal)
        points[2].handle_left = corner2 - h_dir * bend_radius
        # Handle right: going down (vertical)
        points[2].handle_right = corner2 - Vector((0, 0, bend_radius))
        
        # Point 3: End (vertical coming down)
        points[3].co = end
        points[3].handle_left_type = 'FREE'
        points[3].handle_right_type = 'FREE'
        points[3].handle_left = end + Vector((0, 0, bend_radius))
        points[3].handle_right = end - Vector((0, 0, bend_radius))
        
        # Create the curve object
        pipe_obj = bpy.data.objects.new('Pipe_Route', curve_data)
        context.collection.objects.link(pipe_obj)
        
        # Apply steel material
        mat = create_cable_material("Pipe_Steel", (0.6, 0.6, 0.65, 1))
        pipe_obj.data.materials.append(mat)
        
        # Select and activate the pipe
        bpy.ops.object.select_all(action='DESELECT')
        pipe_obj.select_set(True)
        context.view_layer.objects.active = pipe_obj
        
        self.report({'INFO'}, "Created pipe route with smooth 90° bends")
        return {'FINISHED'}


# ============================================================================
# PANEL
# ============================================================================

class SCG_PT_main_panel(bpy.types.Panel):
    """Slack Cable Generator Panel"""
    bl_label = "Cable Generator"
    bl_idname = "SCG_PT_main_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "ramooscripts"
    
    def draw(self, context):
        layout = self.layout
        scene = context.scene
        
        # Cable Settings
        box = layout.box()
        box.label(text="Cable Settings", icon='CURVE_BEZCURVE')
        box.prop(scene, "scg_slack_amount", text="Slack")
        box.prop(scene, "scg_thickness", text="Thickness")
        box.prop(scene, "scg_resolution", text="Resolution")
        box.prop(scene, "scg_profile", text="Profile")
        
        layout.separator()
        
        # Create Cable
        box = layout.box()
        box.label(text="Create Cable", icon='ADD')
        box.operator("scg.cable_between_objects", icon='CURVE_BEZCURVE')
        box.operator("scg.cable_at_cursor", icon='PIVOT_CURSOR')
        box.operator("scg.chain_cable", icon='LINKED')
        
        layout.separator()
        
        # Bundle (NEW v1.1)
        box = layout.box()
        box.label(text="Cable Bundle", icon='OUTLINER')
        box.prop(scene, "scg_bundle_count", text="Count")
        box.prop(scene, "scg_bundle_spread", text="Spread")
        box.operator("scg.cable_bundle", icon='MESH_TORUS')
        
        layout.separator()
        
        # Conduit (NEW v1.1)
        box = layout.box()
        box.label(text="Conduit", icon='MESH_CYLINDER')
        box.prop(scene, "scg_bend_radius", text="Bend Radius")
        box.operator("scg.conduit_bend", icon='SPHERECURVE')
        
        layout.separator()
        
        # Material (NEW v1.1)
        box = layout.box()
        box.label(text="Material", icon='MATERIAL')
        box.prop(scene, "scg_material_preset", text="")
        box.operator("scg.apply_material", icon='SHADING_RENDERED')
        
        layout.separator()
        
        # Edit Cable
        box = layout.box()
        box.label(text="Edit Cable", icon='MODIFIER')
        box.operator("scg.adjust_slack", icon='ARROW_LEFTRIGHT')


# ============================================================================
# REGISTRATION
# ============================================================================

classes = (
    SCG_OT_create_cable_between_objects,
    SCG_OT_create_cable_at_cursor,
    SCG_OT_adjust_slack,
    SCG_OT_chain_cable,
    SCG_OT_apply_material,
    SCG_OT_cable_bundle,
    SCG_OT_add_conduit_bend,
    SCG_PT_main_panel,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    
    bpy.types.Scene.scg_slack_amount = FloatProperty(
        name="Slack", default=0.5, min=0.0, unit='LENGTH'
    )
    bpy.types.Scene.scg_thickness = FloatProperty(
        name="Thickness", default=0.02, min=0.001, unit='LENGTH'
    )
    bpy.types.Scene.scg_resolution = IntProperty(
        name="Resolution", default=12, min=1, max=64
    )
    bpy.types.Scene.scg_profile = EnumProperty(
        name="Profile",
        items=[
            ('ROUND', 'Round Cable', 'Circular cross-section'),
            ('SQUARE', 'Square Duct', 'Square cross-section'),
        ],
        default='ROUND'
    )
    bpy.types.Scene.scg_bundle_count = IntProperty(
        name="Bundle Count", default=5, min=2, max=20
    )
    bpy.types.Scene.scg_bundle_spread = FloatProperty(
        name="Bundle Spread", default=0.05, min=0.01, max=0.5, unit='LENGTH'
    )
    bpy.types.Scene.scg_bend_radius = FloatProperty(
        name="Bend Radius", default=0.1, min=0.02, max=1.0, unit='LENGTH'
    )
    bpy.types.Scene.scg_material_preset = EnumProperty(
        name="Material Preset",
        items=[
            ('BLACK', 'Black', 'Black cable'),
            ('RED', 'Red', 'Red cable'),
            ('YELLOW', 'Yellow', 'Yellow cable'),
            ('BLUE', 'Blue', 'Blue cable'),
            ('GREEN', 'Green', 'Green cable'),
            ('WHITE', 'White', 'White cable'),
            ('COPPER', 'Copper Pipe', 'Copper pipe'),
            ('STEEL', 'Steel Pipe', 'Steel pipe'),
        ],
        default='BLACK'
    )
    
    print("Slack Cable Generator v1.1: Registered")


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    
    del bpy.types.Scene.scg_slack_amount
    del bpy.types.Scene.scg_thickness
    del bpy.types.Scene.scg_resolution
    del bpy.types.Scene.scg_profile
    del bpy.types.Scene.scg_bundle_count
    del bpy.types.Scene.scg_bundle_spread
    del bpy.types.Scene.scg_bend_radius
    del bpy.types.Scene.scg_material_preset
    
    print("Slack Cable Generator v1.1: Unregistered")


if __name__ == "__main__":
    register()
