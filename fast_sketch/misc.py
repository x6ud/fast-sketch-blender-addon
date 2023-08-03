import bpy
import mathutils
from bpy_extras.view3d_utils import region_2d_to_location_3d
from mathutils import Vector


def get_mouse_pointing_node_index(context, location):
    tube = None
    tube_index = -1
    pointing_index = -1
    if context.object is not None and context.object.fast_sketch_properties.is_fast_sketch:
        active_index = context.object.fast_sketch_properties.active_index
        tubes = context.object.fast_sketch_properties.tubes
        if active_index >= 0:
            tube = tubes[active_index]
            tube_index = active_index
            obj_mat = context.object.matrix_world
            obj_scale = obj_mat.to_scale()
            scale = min(obj_scale.x, obj_scale.y, obj_scale.z)
            active = False
            min_z = float('inf')
            region = context.region
            r3d = context.space_data.region_3d
            perspective_matrix = r3d.perspective_matrix
            for index, node in enumerate(tube.nodes):
                node_loc = obj_mat @ node.location
                mouse_loc = region_2d_to_location_3d(region, r3d, location, node_loc)
                if (node_loc - mouse_loc).length <= scale * node.radius:
                    prj = perspective_matrix @ Vector((mouse_loc.x, mouse_loc.y, mouse_loc.z, 1.0))
                    if (active and node.active or not active) and prj.z < min_z:
                        min_z = prj.z
                        pointing_index = index
                        if node.active:
                            active = True
    return tube, tube_index, pointing_index


def update_branch(target_tube_index, target_node_index):
    tubes = bpy.context.object.fast_sketch_properties.tubes
    target_tube = tubes[target_tube_index]
    target_node = target_tube.nodes[target_node_index]
    radius = target_node.radius
    location = target_node.location
    for tube in tubes:
        for node in tube.nodes:
            node.visited = False

    def update(tube_index, node_index):
        current_tube = tubes[tube_index]
        current_node = current_tube.nodes[node_index]
        if current_node.visited:
            return
        current_node.visited = True
        current_node.radius = radius
        current_node.location = mathutils.Vector(location)
        if node_index == 0 and current_tube.parent_tube_index >= 0:
            update(current_tube.parent_tube_index, current_tube.parent_node_index)
        for (sub_tube_index, sub_tube) in enumerate(tubes):
            if sub_tube.parent_tube_index == tube_index and sub_tube.parent_node_index == node_index \
                    and len(sub_tube.nodes):
                update(sub_tube_index, 0)

    update(target_tube_index, target_node_index)
