import bpy
from .update import update_geometry_nodes


def property_update_callback(self, context):
    update_geometry_nodes()


class FastSketchNodeProperties(bpy.types.PropertyGroup):
    location: bpy.props.FloatVectorProperty(name="Location", subtype="XYZ", unit="LENGTH")
    radius: bpy.props.FloatProperty(name="Radius", unit="LENGTH", min=0)
    active: bpy.props.BoolProperty(name="Active")


class FastSketchTubeProperties(bpy.types.PropertyGroup):
    name: bpy.props.StringProperty(name="Name")
    nodes: bpy.props.CollectionProperty(type=FastSketchNodeProperties, name="Nodes")


class FastSketchGroupProperties(bpy.types.PropertyGroup):
    is_fast_sketch: bpy.props.BoolProperty()
    active_index: bpy.props.IntProperty(default=-1)
    tubes: bpy.props.CollectionProperty(type=FastSketchTubeProperties, name="Tubes")
    segments: bpy.props.IntProperty(default=4,
                                    min=1,
                                    max=6,
                                    name="Segments",
                                    update=property_update_callback)
    symmetry: bpy.props.EnumProperty(items=[("none", "none", "No Symmetry"),
                                            ("x", "x", "X Axis"),
                                            ("y", "y", "Y Axis"),
                                            ("z", "z", "Z Axis"),
                                            ],
                                     name="Symmetry",
                                     default="none",
                                     update=property_update_callback)
    remesh: bpy.props.BoolProperty(default=True, name="Remesh")
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
