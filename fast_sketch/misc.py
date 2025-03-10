import re

import bpy
import mathutils
from bpy_extras.view3d_utils import region_2d_to_location_3d
from mathutils import Vector


def get_mouse_pointing_node(context, location):
    pointing_tube_index = -1
    pointing_node_index = -1
    if context.object and context.object.fast_sketch_properties.is_fast_sketch:
        active_index = context.object.fast_sketch_properties.active_index
        tubes = context.object.fast_sketch_properties.tubes
        for tube_index, tube in enumerate(tubes):
            if 0 <= active_index != tube_index:
                continue
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
                        pointing_tube_index = tube_index
                        pointing_node_index = index
                        if node.active:
                            active = True

    return pointing_tube_index, pointing_node_index


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


def replace_join_nodes_with_boolean_nodes(merge_meshes):
    obj = bpy.context.object
    geo_nodes = obj.modifiers.get("Fast Sketch Mesh")
    tree = geo_nodes.node_group
    for join_node in tree.nodes:

        if merge_meshes and join_node.name == "Join" \
                or re.match(r'Tube_([0-9]+)', join_node.name):
            bool_node = tree.nodes.new(type="GeometryNodeMeshBoolean")
            bool_node.location.x = join_node.location.x
            bool_node.location.y = join_node.location.y
            bool_node.select = False
            bool_node.operation = "UNION"
            bool_node.solver = "EXACT"
            bool_node.inputs[2].default_value = True
            for link in join_node.inputs[0].links:
                tree.links.new(link.from_socket, bool_node.inputs["Mesh 2"])
            for link in join_node.outputs[0].links:
                tree.links.new(bool_node.outputs["Mesh"], link.to_socket)
            tree.nodes.remove(join_node)
