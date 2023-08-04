import re

import bmesh
import bpy


def update_geometry():
    obj = bpy.context.object
    if obj is None or not obj.fast_sketch_properties.is_fast_sketch:
        return
    method = obj.fast_sketch_properties.method
    if method == "Geometry Node":
        skin = obj.modifiers.get("Fast Sketch Skin")
        if skin:
            obj.modifiers.remove(skin)
        sub_surf = obj.modifiers.get("Fast Sketch Sub Surf")
        if sub_surf:
            obj.modifiers.remove(sub_surf)
        build_geometry_node()
    elif method == "Skin Modifier":
        geo_nodes = obj.modifiers.get("Fast Sketch Mesh")
        if geo_nodes:
            node_group = geo_nodes.node_group
            if node_group:
                bpy.data.node_groups.remove(node_group)
            obj.modifiers.remove(geo_nodes)
        build_skin_modifier()


def remove_link(tree, from_node_name, from_socket_name, to_node_name, to_socket_name):
    for link in tree.links:
        if link.from_node.name == from_node_name \
                and link.from_socket.name == from_socket_name \
                and link.to_node.name == to_node_name \
                and link.to_socket.name == to_socket_name:
            tree.links.remove(link)
            return


def build_geometry_node():
    obj = bpy.context.object

    # create base nodes
    geo_nodes = obj.modifiers.get("Fast Sketch Mesh")
    if not geo_nodes:
        geo_nodes = obj.modifiers.new("Fast Sketch Mesh", "NODES")
        tree = bpy.data.node_groups.new("Geometry Nodes", "GeometryNodeTree")
        geo_nodes.node_group = tree
        tree.outputs.new("NodeSocketGeometry", "Geometry")

        output_node = tree.nodes.new("NodeGroupOutput")
        output_node.name = "Output"
        output_node.is_active_output = True
        output_node.select = False
        output_node.location.x = 800

        sphere_node = tree.nodes.new(type="GeometryNodeMeshUVSphere")
        sphere_node.name = "Sphere"
        sphere_node.select = False
        sphere_node.location.x = -400

        join_node = tree.nodes.new("GeometryNodeJoinGeometry")
        join_node.name = "Join"
        join_node.select = False
        join_node.location.x = 600

        obj.modifiers.move(len(obj.modifiers) - 1, 0)

    tree = geo_nodes.node_group

    # segments
    segments = obj.fast_sketch_properties.segments
    sphere_node = tree.nodes["Sphere"]
    sphere_node.inputs["Segments"].default_value = max(segments * 2, 3)
    sphere_node.inputs["Rings"].default_value = max(segments, 2)

    # output
    output_node = tree.nodes["Output"]
    output_node.location.x = 800
    tree.links.new(tree.nodes["Join"].outputs["Geometry"], output_node.inputs["Geometry"])

    # remove useless nodes
    tubes = obj.fast_sketch_properties.tubes
    tubes_len = len(tubes)
    for node in tree.nodes:
        match_obj = re.match(r'Tube_([0-9]+)', node.name)
        if match_obj:
            tube_index = int(match_obj.group(1))
            if tube_index >= tubes_len:
                tree.nodes.remove(node)
        else:
            match_obj = re.match(r'(Transform|Join|Hull)_([0-9]+)_([0-9]+)', node.name)
            if match_obj:
                tube_index = int(match_obj.group(2))
                if tube_index >= tubes_len:
                    tree.nodes.remove(node)
                else:
                    node_index = int(match_obj.group(3))
                    if node_index >= len(tubes[tube_index].nodes):
                        tree.nodes.remove(node)

    # create nodes
    count = 0
    for tube_index, tube in enumerate(obj.fast_sketch_properties.tubes):
        tube_node_name = "Tube_%d" % tube_index
        tube_node = tree.nodes.get(tube_node_name)
        if not tube_node:
            tube_node = tree.nodes.new(type="GeometryNodeJoinGeometry")
            tube_node.name = tube_node_name
            tube_node.label = "Join / Tube %d" % tube_index
            tube_node.select = False
            tree.links.new(
                tube_node.outputs["Geometry"],
                tree.nodes["Join"].inputs["Geometry"]
            )
        tube_node.location.x = 400
        tube_node.location.y = count * -30

        if len(tube.nodes) > 1:
            remove_link(tree, "Transform_%d_0" % tube_index, "Geometry", "Tube_%d" % tube_index, "Geometry")

        for node_index, node in enumerate(tube.nodes):
            transform_node_name = "Transform_%d_%d" % (tube_index, node_index)
            transform_node = tree.nodes.get(transform_node_name)
            if not transform_node:
                transform_node = tree.nodes.new("GeometryNodeTransform")
                transform_node.name = transform_node_name
                transform_node.label = "Transform / Node %d" % node_index
                transform_node.select = False
                tree.links.new(sphere_node.outputs["Mesh"], transform_node.inputs["Geometry"])
            if len(tube.nodes) == 1:
                tree.links.new(transform_node.outputs["Geometry"], tube_node.inputs["Geometry"])
            else:
                remove_link(tree, transform_node_name, "Geometry", tube_node_name, "Geometry")
            transform_node.inputs["Translation"].default_value = node.location
            transform_node.inputs["Scale"].default_value = (node.radius, node.radius, node.radius)
            transform_node.location.x = -200
            transform_node.location.y = count * -30

            if node_index > 0:
                join_node_name = "Join_%d_%d" % (tube_index, node_index)
                join_node = tree.nodes.get(join_node_name)
                if not join_node:
                    join_node = tree.nodes.new(type="GeometryNodeJoinGeometry")
                    join_node.name = join_node_name
                    join_node.label = "Join / Node %d & %d" % (node_index - 1, node_index)
                    join_node.select = False
                    tree.links.new(
                        tree.nodes["Transform_%d_%d" % (tube_index, node_index - 1)].outputs["Geometry"],
                        join_node.inputs["Geometry"]
                    )
                    tree.links.new(
                        tree.nodes["Transform_%d_%d" % (tube_index, node_index)].outputs["Geometry"],
                        join_node.inputs["Geometry"]
                    )
                join_node.location.x = 0
                join_node.location.y = count * -30 + 30
                hull_node_name = "Hull_%d_%d" % (tube_index, node_index)
                hull_node = tree.nodes.get(hull_node_name)
                if not hull_node:
                    hull_node = tree.nodes.new(type="GeometryNodeConvexHull")
                    hull_node.name = hull_node_name
                    hull_node.select = False
                    tree.links.new(join_node.outputs["Geometry"], hull_node.inputs["Geometry"])
                    tree.links.new(hull_node.outputs["Convex Hull"], tube_node.inputs["Geometry"])
                hull_node.location.x = 200
                hull_node.location.y = join_node.location.y

            count += 1


def build_skin_modifier():
    obj = bpy.context.object

    skin = obj.modifiers.get("Fast Sketch Skin")
    if not skin:
        skin = obj.modifiers.new("Fast Sketch Skin", "SKIN")
        obj.modifiers.move(len(obj.modifiers) - 1, 0)

    sub_surf = obj.modifiers.get("Fast Sketch Sub Surf")
    if not sub_surf:
        sub_surf = obj.modifiers.new("Fast Sketch Sub Surf", "SUBSURF")
        sub_surf.show_only_control_edges = False
        obj.modifiers.move(len(obj.modifiers) - 1, 1)
    sub_surf.levels = obj.fast_sketch_properties.sub_surf_levels

    bm = bmesh.new()

    tubes = obj.fast_sketch_properties.tubes
    tube_vert_index_map = []
    vertex_count = 0
    for tube in tubes:
        node_vert_index_map = []
        tube_vert_index_map.append(node_vert_index_map)
        for node_index, node in enumerate(tube.nodes):
            if node_index == 0 and tube.parent_tube_index >= 0:
                node_vert_index_map.append(tube_vert_index_map[tube.parent_tube_index][tube.parent_node_index])
            else:
                node_vert_index_map.append(vertex_count)
                vertex_count += 1
                bm.verts.new((node.location.x, node.location.y, node.location.z))
    bm.verts.ensure_lookup_table()
    for tube_index, tube in enumerate(tubes):
        for node_index in range(1, len(tube.nodes)):
            i = tube_vert_index_map[tube_index][node_index - 1]
            j = tube_vert_index_map[tube_index][node_index]
            bm.edges.new((bm.verts[i], bm.verts[j]))

    bm.to_mesh(obj.data)

    if not len(obj.data.skin_vertices):
        bpy.ops.mesh.customdata_skin_add()

    skin_verts = obj.data.skin_vertices[0].data
    for tube_index, tube in enumerate(tubes):
        for node_index, node in enumerate(tube.nodes):
            if node_index == 0 and tube.parent_tube_index >= 0:
                continue
            vert_index = tube_vert_index_map[tube_index][node_index]
            skin_vert = skin_verts[vert_index]
            skin_vert.radius[0] = skin_vert.radius[1] = node.radius
            skin_vert.use_root = node_index == 0


def update_mirror():
    obj = bpy.context.object
    if obj is None or not obj.fast_sketch_properties.is_fast_sketch:
        return

    mirror = obj.modifiers.get("Fast Sketch Mirror")
    if not mirror:
        mirror = obj.modifiers.new("Fast Sketch Mirror", "MIRROR")

    mirror.use_axis[0] = obj.fast_sketch_properties.mirror_axis[0]
    mirror.use_axis[1] = obj.fast_sketch_properties.mirror_axis[1]
    mirror.use_axis[2] = obj.fast_sketch_properties.mirror_axis[2]
    mirror.use_mirror_merge = obj.fast_sketch_properties.mirror_merge
    mirror.merge_threshold = obj.fast_sketch_properties.mirror_merge_threshold
    mirror.use_bisect_axis[0] = obj.fast_sketch_properties.bisect_axis[0]
    mirror.use_bisect_axis[1] = obj.fast_sketch_properties.bisect_axis[1]
    mirror.use_bisect_axis[2] = obj.fast_sketch_properties.bisect_axis[2]
