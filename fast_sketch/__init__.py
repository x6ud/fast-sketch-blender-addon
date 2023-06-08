bl_info = {
    "name": "Fast Sketch",
    "description": "",
    "author": "x6ud",
    "version": (1, 0),
    "blender": (3, 5, 0),
    "category": "Object"
}

import bpy

from .properties import FastSketchNodeProperties, FastSketchTubeProperties, FastSketchGroupProperties, \
    FastSketchWmProperties
from .ui import FastSketchTubeList, FastSketchPanel, \
    FastSketchBakeOperator, \
    FastSketchAddTubeOperator, \
    FastSketchRemoveTubeOperator
from .tool import FastSketchToolOperator, FastSketchTool
from .gizmo import FastSketchGizmo, FastSketchGizmoGroup

classes = [
    FastSketchNodeProperties,
    FastSketchTubeProperties,
    FastSketchGroupProperties,
    FastSketchWmProperties,

    FastSketchTubeList,
    FastSketchPanel,
    FastSketchBakeOperator,
    FastSketchAddTubeOperator,
    FastSketchRemoveTubeOperator,

    FastSketchToolOperator,

    FastSketchGizmo,
    FastSketchGizmoGroup,
]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Object.fast_sketch_properties = bpy.props.PointerProperty(type=FastSketchGroupProperties)
    bpy.types.WindowManager.fast_sketch = bpy.props.PointerProperty(type=FastSketchWmProperties)
    bpy.utils.register_tool(FastSketchTool, separator=True, group=False)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    bpy.utils.unregister_tool(FastSketchTool)
