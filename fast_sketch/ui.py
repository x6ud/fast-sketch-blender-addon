import bpy

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
        layout = self.layout
        fast_sketch = context.object.fast_sketch_properties

        layout.prop(fast_sketch, "segments")
        row = layout.row(align=True)
        row.label(text="Mirror")
        row.prop(fast_sketch, "mirror_axis", index=0, toggle=True, text="X")
        row.prop(fast_sketch, "mirror_axis", index=1, toggle=True, text="Y")
        row.prop(fast_sketch, "mirror_axis", index=2, toggle=True, text="Z")
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

        layout.prop(fast_sketch, "remesh")
        layout.prop(fast_sketch, "remesh_voxel_size")
        layout.prop(fast_sketch, "smooth")
        layout.prop(fast_sketch, "smooth_iterators")
        layout.prop(fast_sketch, "smooth_factor")
        layout.operator("fast_sketch.bake", text="Bake!")


class FastSketchBakeOperator(bpy.types.Operator):
    bl_idname = "fast_sketch.bake"
    bl_label = "Fast Sketch Bake"

    def execute(self, context):
        bpy.ops.ed.undo_push()
        context.object.fast_sketch_properties.is_fast_sketch = False

        # apply geometry nodes
        geo_nodes = context.object.modifiers.get("Fast Sketch Mesh")
        if geo_nodes:
            bpy.ops.object.modifier_apply(modifier="Fast Sketch Mesh")

        # apply mirror
        if context.object.modifiers.get("Fast Sketch Mirror"):
            bpy.ops.object.modifier_apply(modifier="Fast Sketch Mirror")

        if context.object.fast_sketch_properties.remesh:
            # apply remesh
            context.object.data.remesh_voxel_size = context.object.fast_sketch_properties.remesh_voxel_size
            bpy.ops.object.voxel_remesh()
        else:
            # remove internal vertices
            geo_nodes = context.object.modifiers.new("Fast Sketch Boolean Union", "NODES")
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

        # apply smooth
        if context.object.fast_sketch_properties.smooth:
            bpy.ops.object.modifier_add(type="LAPLACIANSMOOTH")
            bpy.context.object.modifiers["LaplacianSmooth"].iterations = \
                context.object.fast_sketch_properties.smooth_iterators
            bpy.context.object.modifiers["LaplacianSmooth"].lambda_factor = \
                context.object.fast_sketch_properties.smooth_factor
            bpy.context.object.modifiers["LaplacianSmooth"].use_volume_preserve = False
            bpy.context.object.modifiers["LaplacianSmooth"].use_normalized = False
            bpy.ops.object.modifier_apply(modifier="LaplacianSmooth")

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
