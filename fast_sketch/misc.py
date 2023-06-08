from bpy_extras.view3d_utils import region_2d_to_location_3d
from mathutils import Vector

def get_mouse_pointing_node_index(context, location):
    tube = None
    pointing_index = -1
    if context.object is not None and context.object.fast_sketch_properties.is_fast_sketch:
        active_index = context.object.fast_sketch_properties.active_index
        tubes = context.object.fast_sketch_properties.tubes
        if active_index >= 0:
            tube = tubes[active_index]
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
    return tube, pointing_index
