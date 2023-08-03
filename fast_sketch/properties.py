import bpy

from .update import update_geometry, update_mirror


def property_update_callback(self, context):
    update_geometry()
    update_mirror()


class FastSketchNodeProperties(bpy.types.PropertyGroup):
    location: bpy.props.FloatVectorProperty(name="Location", subtype="XYZ", unit="LENGTH")
    radius: bpy.props.FloatProperty(name="Radius", unit="LENGTH", min=0)
    active: bpy.props.BoolProperty(name="Active")
    visited: bpy.props.BoolProperty()


class FastSketchTubeProperties(bpy.types.PropertyGroup):
    name: bpy.props.StringProperty(name="Name")
    nodes: bpy.props.CollectionProperty(type=FastSketchNodeProperties, name="Nodes")
    parent_tube_index: bpy.props.IntProperty(default=-1)
    parent_node_index: bpy.props.IntProperty(default=-1)


class FastSketchGroupProperties(bpy.types.PropertyGroup):
    is_fast_sketch: bpy.props.BoolProperty()
    active_index: bpy.props.IntProperty(default=-1)
    tubes: bpy.props.CollectionProperty(type=FastSketchTubeProperties, name="Tubes")
    segments: bpy.props.IntProperty(default=4,
                                    min=2,
                                    max=12,
                                    name="Segments",
                                    update=property_update_callback)
    mirror_axis: bpy.props.BoolVectorProperty(name="Mirror", update=property_update_callback)
    bisect_axis: bpy.props.BoolVectorProperty(name="Bisect", update=property_update_callback)
    remesh: bpy.props.BoolProperty(default=False, name="Remesh")
    remesh_voxel_size: bpy.props.FloatProperty(default=0.05, min=0.0001, max=100, name="Voxel Size", unit="LENGTH")
    smooth: bpy.props.BoolProperty(default=False, name="Smooth")
    smooth_iterators: bpy.props.IntProperty(default=2, min=1, max=50, name="Smooth Iterators")
    smooth_factor: bpy.props.FloatProperty(default=0.1, min=0.01, max=10, name="Smooth Factor")


# global temporary properties
class FastSketchWmProperties(bpy.types.PropertyGroup):
    is_inserting: bpy.props.BoolProperty()
    insert_loc: bpy.props.FloatVectorProperty()
    insert_index: bpy.props.IntProperty(default=-1)
    insert_radius: bpy.props.FloatProperty(default=.5)
    is_branch: bpy.props.BoolProperty()
