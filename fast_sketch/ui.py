import bpy

from .misc import replace_join_nodes_with_boolean_nodes
from .update import update_geometry


class FastSketchTubeList(bpy.types.UIList):
    bl_idname = "FAST_SKETCH_UL_tube_list"

    def draw_item(self, context, layout, data, item, icon, active_data, active_property, index, flt_flag):
        if self.layout_type in {"DEFAULT", "COMPACT"}:
            row = layout.row()
            row.prop(item, "name", text="", emboss=False, translate=False, icon_value=icon)
        elif self.layout_type in {"GRID"}:
            layout.label(text="", icon_value=icon)


class FastSketchPanel(bpy.types.Panel):
    bl_label = "Fast Sketch"
    bl_idname = "FAST_SKETCH_PT_properties"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Fast Sketch"

    @classmethod
    def poll(cls, context):
        return context.object is not None and context.object.fast_sketch_properties.is_fast_sketch

    def draw(self, context):
        fast_sketch = context.object.fast_sketch_properties
        layout = self.layout
        layout.prop(fast_sketch, "method")
        if fast_sketch.method == "Geometry Node":
            layout.prop(fast_sketch, "segments")
        if fast_sketch.method == "Skin Modifier":
            layout.prop(fast_sketch, "sub_surf_levels")
        row = layout.row(align=True)
        row.label(text="Mirror")
        row.prop(fast_sketch, "mirror_axis", index=0, toggle=True, text="X")
        row.prop(fast_sketch, "mirror_axis", index=1, toggle=True, text="Y")
        row.prop(fast_sketch, "mirror_axis", index=2, toggle=True, text="Z")
        row = layout.row(align=True)
        row.label(text="Merge")
        row.prop(fast_sketch, "mirror_merge", text="")
        row.prop(fast_sketch, "mirror_merge_threshold", text="")
        row = layout.row(align=True)
        row.label(text="Bisect")
        row.prop(fast_sketch, "bisect_axis", index=0, toggle=True, text="X")
        row.prop(fast_sketch, "bisect_axis", index=1, toggle=True, text="Y")
        row.prop(fast_sketch, "bisect_axis", index=2, toggle=True, text="Z")
        row = layout.row()
        row.template_list("FAST_SKETCH_UL_tube_list", "", fast_sketch, "tubes", fast_sketch, "active_index")
        col = row.column(align=True)
        col.operator("fast_sketch.add_tube", icon="ADD", text="")
        col.operator("fast_sketch.remove_tube", icon="REMOVE", text="")
        layout.separator()
        layout.operator("fast_sketch.create_armature", text="Create Armature", icon="OUTLINER_OB_ARMATURE")
        layout.prop(fast_sketch, "merge_meshes")
        layout.operator("fast_sketch.bake", text="Bake!", icon="CHECKMARK")


class FastSketchBakeOperator(bpy.types.Operator):
    bl_idname = "fast_sketch.bake"
    bl_label = "Fast Sketch Bake"

    def execute(self, context):
        bpy.ops.ed.undo_push()

        obj = context.object
        obj.fast_sketch_properties.is_fast_sketch = False

        merge_meshes = obj.fast_sketch_properties.merge_meshes

        if obj.modifiers.get("Fast Sketch Mesh"):
            replace_join_nodes_with_boolean_nodes(merge_meshes)
            bpy.ops.object.modifier_apply(modifier="Fast Sketch Mesh")

        if obj.modifiers.get("Fast Sketch Skin"):
            bpy.ops.object.modifier_apply(modifier="Fast Sketch Skin")

        if obj.modifiers.get("Fast Sketch Sub Surf"):
            bpy.ops.object.modifier_apply(modifier="Fast Sketch Sub Surf")

        if merge_meshes and obj.fast_sketch_properties.method == "Skin Modifier":
            # remove internal vertices
            geo_nodes = obj.modifiers.new("Fast Sketch Boolean Union", "NODES")
            obj.modifiers.move(len(obj.modifiers) - 1, 0)
            tree = bpy.data.node_groups.new("Geometry Nodes", "GeometryNodeTree")
            geo_nodes.node_group = tree
            tree.inputs.new("NodeSocketGeometry", "Geometry")
            tree.outputs.new("NodeSocketGeometry", "Geometry")
            input_node = tree.nodes.new("NodeGroupInput")
            output_node = tree.nodes.new("NodeGroupOutput")
            bool_node = tree.nodes.new(type="GeometryNodeMeshBoolean")
            bool_node.operation = "UNION"
            bool_node.inputs[2].default_value = True
            tree.links.new(input_node.outputs[0], bool_node.inputs["Mesh 2"])
            tree.links.new(bool_node.outputs[0], output_node.inputs[0])
            bpy.ops.object.modifier_apply(modifier="Fast Sketch Boolean Union")

        if obj.modifiers.get("Fast Sketch Mirror"):
            bpy.ops.object.modifier_apply(modifier="Fast Sketch Mirror")

        return {'FINISHED'}


class FastSketchAddTubeOperator(bpy.types.Operator):
    bl_idname = "fast_sketch.add_tube"
    bl_label = "Fast Sketch Add Tube"

    def execute(self, context):
        tubes = context.object.fast_sketch_properties.tubes

        bpy.ops.ed.undo_push()
        item = tubes.add()
        item.name = "Tube"
        context.object.fast_sketch_properties.active_index = len(tubes) - 1
        update_geometry()

        # update gizmo
        bpy.context.region.tag_redraw()

        return {'FINISHED'}


class FastSketchRemoveTubeOperator(bpy.types.Operator):
    bl_idname = "fast_sketch.remove_tube"
    bl_label = "Fast Sketch Remove Tube"

    def execute(self, context):
        tubes = context.object.fast_sketch_properties.tubes
        tube_index = context.object.fast_sketch_properties.active_index
        if tube_index >= 0:
            bpy.ops.ed.undo_push()
            tubes.remove(tube_index)
            context.object.fast_sketch_properties.active_index = min(tube_index, len(tubes) - 1)

            # remove branch relationships
            for sub_tube in tubes:
                if sub_tube.parent_tube_index == tube_index:
                    sub_tube.parent_tube_index = -1
                    sub_tube.parent_node_index = -1
                elif sub_tube.parent_tube_index > tube_index:
                    sub_tube.parent_tube_index -= 1

            update_geometry()

            # update gizmo
            bpy.context.region.tag_redraw()

        return {'FINISHED'}


class FastSketchCreateArmatureOperator(bpy.types.Operator):
    bl_idname = "fast_sketch.create_armature"
    bl_label = "Fast Sketch Create Armature"

    def execute(self, context):
        bpy.ops.ed.undo_push()

        armature = bpy.data.armatures.new('Armature')
        obj = bpy.data.objects.new('Armature', armature)
        context.scene.collection.objects.link(obj)
        obj.matrix_world = context.object.matrix_world

        tubes = context.object.fast_sketch_properties.tubes

        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.mode_set(mode='EDIT')

        tube_bones = []
        for tube in tubes:
            bones = []
            tube_bones.append(bones)
            prev_bone = None
            if 0 <= tube.parent_tube_index < len(tube_bones):
                prev_bone = tube_bones[tube.parent_tube_index][tube.parent_node_index]
            for i in range(1, len(tube.nodes)):
                start = tube.nodes[i - 1].location
                end = tube.nodes[i].location
                bone = armature.edit_bones.new("Bone")
                bone.head = start
                bone.tail = end
                if prev_bone:
                    bone.parent = prev_bone
                prev_bone = bone
                bones.append(bone)

        bpy.context.view_layer.update()

        return {'FINISHED'}
