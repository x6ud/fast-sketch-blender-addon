import time
from pathlib import Path

import bpy
import gpu
import mathutils
from bpy_extras.view3d_utils import region_2d_to_location_3d, location_3d_to_region_2d
from gpu_extras.batch import batch_for_shader

from .misc import get_mouse_pointing_node_index, update_branch
from .update import update_geometry, update_mirror

RADIUS_STEP = 0.02
RADIUS_MAX = 10
RADIUS_MIN = 0.02


class FastSketchToolOperator(bpy.types.Operator):
    bl_idname = "fast_sketch.tool"
    bl_label = "Fast Sketch"
    bl_options = {"REGISTER"}

    _draw_handler = None
    _select_box_start = mathutils.Vector((0, 0, 0))
    _select_box_end = mathutils.Vector((0, 0, 0))

    _clicked_index = -1
    _mouse_moved = False

    _wheel_input_last_timestamp = 0.0

    _drag_move = False
    _drag_input_last_timestamp = 0.0
    _drag_start_loc = mathutils.Vector((0, 0, 0))
    _drag_start_depth = (0, 0, 0)
    _drag_start_mat = mathutils.Matrix()
    _drag_start_inv_mat = mathutils.Matrix()
    _drag_start_state = []

    def invoke(self, context, event):
        if event.type == "LEFTMOUSE" and event.value == 'PRESS':
            if event.alt:
                # ============================ alt + left click ============================
                # ============================ insert node ============================

                # get selected node
                active_obj = None
                active_tube = None
                active_node = None
                insert_index = -1

                if context.object is not None and context.object.fast_sketch_properties.is_fast_sketch:
                    active_obj = context.object

                if active_obj:
                    group = active_obj.fast_sketch_properties
                    if group.active_index >= 0 and group.active_index < len(group.tubes):
                        active_tube = group.tubes[group.active_index]
                        for node_index, node in enumerate(active_tube.nodes):
                            if node.active:
                                active_node = node
                                insert_index = node_index
                                break

                if insert_index < 0 and active_tube:
                    insert_index = len(active_tube.nodes)

                # get mouse clicked location
                depth_loc = (0, 0, 0)
                if active_node:
                    depth_loc = active_obj.matrix_world @ active_node.location
                region = context.region
                r3d = context.space_data.region_3d
                x, y = event.mouse_region_x, event.mouse_region_y
                mouse_location = region_2d_to_location_3d(region, r3d, (x, y), depth_loc)

                # create

                if context.window_manager.fast_sketch.is_branch and active_obj and active_tube \
                        and 0 <= insert_index < len(active_tube.nodes) - 1:
                    parent_node = active_tube.nodes[insert_index]
                    location = mathutils.Vector(parent_node.location)
                    radius = parent_node.radius
                    tubes = active_obj.fast_sketch_properties.tubes
                    sub_tube = tubes.add()
                    sub_tube.name = "Tube"
                    sub_tube.parent_tube_index = active_obj.fast_sketch_properties.active_index
                    sub_tube.parent_node_index = insert_index
                    if active_tube.parent_tube_index >= 0:
                        sub_tube.parent_tube_index = active_tube.parent_tube_index
                        sub_tube.parent_node_index = active_tube.parent_node_index
                    active_obj.fast_sketch_properties.active_index = len(tubes) - 1
                    active_tube = sub_tube
                    insert_index = 0
                    new_node = active_tube.nodes.add()
                    new_node.location = location
                    new_node.radius = radius

                if not active_obj:
                    mesh = bpy.data.meshes.new("Sketch")
                    active_obj = bpy.data.objects.new("Sketch", mesh)
                    active_obj.fast_sketch_properties.is_fast_sketch = True
                    active_obj.matrix_world = mathutils.Matrix.Translation(mouse_location)
                    context.scene.collection.objects.link(active_obj)
                    for obj in bpy.context.selected_objects:
                        obj.select_set(False)
                    bpy.context.view_layer.objects.active = active_obj

                bpy.ops.ed.undo_push()

                if not active_tube:
                    tubes = active_obj.fast_sketch_properties.tubes
                    active_tube = tubes.add()
                    active_obj.fast_sketch_properties.active_index = len(tubes) - 1
                    active_tube.name = "Tube"
                    insert_index = 0

                for node in active_tube.nodes:
                    node.active = False
                new_node = active_tube.nodes.add()
                new_node.location = active_obj.matrix_world.inverted() @ mouse_location
                new_node.radius = context.window_manager.fast_sketch.insert_radius
                new_node.active = True
                for i in range(len(active_tube.nodes) - 1, insert_index, -1):
                    active_tube.nodes.move(i, i + 1)

                update_geometry()
                update_mirror()

                # update gizmo
                bpy.context.region.tag_redraw()

                return {"FINISHED"}

            else:
                # ============================ left click ============================
                # ============================ select ============================

                # get mouse clicked node index
                mouse_location = (event.mouse_region_x, event.mouse_region_y)
                tube, tube_index, pointing_index = get_mouse_pointing_node_index(context, mouse_location)

                # do select when mouse is clicked and released and not moved
                self._clicked_index = pointing_index
                self._mouse_moved = False

                # start select box
                if pointing_index < 0:
                    self._select_box_start = self._select_box_end = mathutils.Vector(
                        (event.mouse_region_x, event.mouse_region_y))
                    self._draw_handler = bpy.types.SpaceView3D.draw_handler_add(
                        self._draw_callback_px, (context,), "WINDOW", "POST_PIXEL"
                    )

                # save drag start state
                self._drag_move = pointing_index >= 0
                self._drag_start_state = []
                if context.object is not None and context.object.fast_sketch_properties.is_fast_sketch:
                    tube_index = context.object.fast_sketch_properties.active_index
                    tubes = context.object.fast_sketch_properties.tubes
                    if tube_index >= 0:
                        tube = tubes[tube_index]
                        for node in tube.nodes:
                            self._drag_start_state.append({
                                "location": mathutils.Vector(node.location),
                                "active": node.active
                            })
                        depth_loc = (0, 0, 0)
                        if pointing_index >= 0:
                            depth_loc = context.object.matrix_world @ tube.nodes[pointing_index].location
                        region = context.region
                        r3d = context.space_data.region_3d
                        x, y = event.mouse_region_x, event.mouse_region_y
                        self._drag_start_depth = depth_loc
                        self._drag_start_loc = region_2d_to_location_3d(region, r3d, (x, y), depth_loc)
                        self._drag_start_mat = context.object.matrix_world
                        self._drag_start_inv_mat = context.object.matrix_world.inverted()

                # start dragging in modal
                context.window_manager.modal_handler_add(self)
                return {"RUNNING_MODAL"}

        if (event.type == "WHEELUPMOUSE" or event.type == "WHEELDOWNMOUSE") and event.value == "PRESS":
            if event.alt:
                # ============================ alt + mouse wheel ============================
                # ============================ change insert radius ============================

                r = context.window_manager.fast_sketch.insert_radius
                if event.type == "WHEELUPMOUSE":
                    r = min(r + RADIUS_STEP, RADIUS_MAX)
                else:
                    r = max(r - RADIUS_STEP, RADIUS_MIN)
                context.window_manager.fast_sketch.insert_radius = r
                # update gizmo
                context.area.tag_redraw()
                return {"FINISHED"}
            else:
                # ============================ mouse wheel ============================
                # ============================ change selected node radius ============================

                # get mouse hovered node index
                tube, tube_index, pointing_index = get_mouse_pointing_node_index(
                    context, (event.mouse_region_x, event.mouse_region_y)
                )
                # resize all selected nodes
                if tube and pointing_index >= 0:
                    node = tube.nodes[pointing_index]
                    if node.active:
                        # limit undo records num
                        now = time.time()
                        if now - FastSketchToolOperator._wheel_input_last_timestamp > 0.3:
                            bpy.ops.ed.undo_push()
                        FastSketchToolOperator._wheel_input_last_timestamp = now

                        for node_index, node in enumerate(tube.nodes):
                            if node.active:
                                r = node.radius
                                if event.type == "WHEELUPMOUSE":
                                    r = min(r + RADIUS_STEP, RADIUS_MAX)
                                else:
                                    r = max(r - RADIUS_STEP, RADIUS_MIN)
                                node.radius = r
                                update_branch(tube_index, node_index)

                        update_geometry()

                        # update gizmo
                        context.area.tag_redraw()
                        return {"FINISHED"}

            return {"PASS_THROUGH"}

        if event.type == "MOUSEMOVE":
            if event.alt:
                # ============================ alt + mouse move ============================
                context.window_manager.fast_sketch.is_inserting = True
                context.window_manager.fast_sketch.is_branch = event.shift
                # update mouse location for gizmo
                self._update_insert_pos(context, event)
            return {"FINISHED"}

        if event.type == "LEFT_ALT" or event.type == "RIGHT_ALT" or event.type == "LEFT_SHIFT" or event.type == "RIGHT_SHIFT":
            # ============================ alt / shift ============================
            # ============================ prepare inserting ============================
            self._update_insert_pos(context, event)
            # set new node radius as the first selected node
            if event.value == "PRESS":
                context.window_manager.fast_sketch.is_inserting = event.alt
                context.window_manager.fast_sketch.is_branch = event.shift
                if event.alt and context.object is not None and context.object.fast_sketch_properties.is_fast_sketch:
                    tube_index = context.object.fast_sketch_properties.active_index
                    tubes = context.object.fast_sketch_properties.tubes
                    if tube_index >= 0:
                        tube = tubes[tube_index]
                        for node in tube.nodes:
                            if node.active:
                                context.window_manager.fast_sketch.insert_radius = node.radius
                                break
            if event.value == "RELEASE":
                context.window_manager.fast_sketch.is_inserting = event.alt
                context.window_manager.fast_sketch.is_branch = event.shift
            return {"FINISHED"}

        if event.type == "DEL":
            # ============================ delete ============================
            # delete all selected nodes
            if context.object is not None and context.object.fast_sketch_properties.is_fast_sketch:
                tube_index = context.object.fast_sketch_properties.active_index
                tubes = context.object.fast_sketch_properties.tubes
                if tube_index >= 0:
                    tube = tubes[tube_index]

                    has_selected = False
                    for node_index in range(len(tube.nodes) - 1, -1, -1):
                        node = tube.nodes[node_index]
                        if node.active:
                            has_selected = True
                            break
                    if has_selected:
                        bpy.ops.ed.undo_push()
                        for node_index in range(len(tube.nodes) - 1, -1, -1):
                            node = tube.nodes[node_index]
                            if node.active:
                                tube.nodes.remove(node_index)

                                # remove branch relationships
                                if node_index == 0:
                                    tube.parent_tube_index = -1
                                    tube.parent_node_index = -1
                                for related_tube in tubes:
                                    if related_tube.parent_tube_index == tube_index \
                                            and related_tube.parent_node_index == node_index:
                                        related_tube.parent_tube_index = -1
                                        related_tube.parent_node_index = -1

                        update_geometry()

                    # update gizmo
                    context.area.tag_redraw()

        if event.type == "ESC":
            if context.object is not None and context.object.fast_sketch_properties.is_fast_sketch:
                context.object.fast_sketch_properties.active_index = -1
                context.area.tag_redraw()

        return {"PASS_THROUGH"}

    def _draw_callback_px(self, context):
        # ============================ draw selection box ============================

        shader = gpu.shader.from_builtin("2D_UNIFORM_COLOR")
        gpu.state.blend_set("ALPHA")
        gpu.state.line_width_set(2.0)

        start = self._select_box_start
        end = self._select_box_end

        box_path = (start, (end.x, start.y), end, (start.x, end.y), start)
        batch = batch_for_shader(shader, "LINE_STRIP", {"pos": box_path})
        shader.bind()
        shader.uniform_float("color", (1.0, 1.0, 1.0, 0.5))
        batch.draw(shader)

        gpu.state.line_width_set(1.0)
        gpu.state.blend_set("NONE")

    def _update_insert_pos(self, context, event):
        # ============================ update mouse position for gizmo ============================

        # get selected node
        active_obj = None
        active_tube = None
        active_node = None

        context.window_manager.fast_sketch.insert_index = -1

        if context.object is not None and context.object.fast_sketch_properties.is_fast_sketch:
            active_obj = context.object

        if active_obj:
            group = active_obj.fast_sketch_properties
            if group.active_index >= 0 and group.active_index < len(group.tubes):
                active_tube = group.tubes[group.active_index]
                for index, node in enumerate(active_tube.nodes):
                    if node.active:
                        active_node = node
                        context.window_manager.fast_sketch.insert_index = index
                        break

        if context.window_manager.fast_sketch.insert_index < 0 and active_tube:
            context.window_manager.fast_sketch.insert_index = len(active_tube.nodes) - 1

        # get mouse clicked location
        depth_loc = (0, 0, 0)
        if active_node:
            depth_loc = active_obj.matrix_world @ active_node.location
        region = context.region
        r3d = context.space_data.region_3d
        x, y = event.mouse_region_x, event.mouse_region_y
        context.window_manager.fast_sketch.insert_loc = region_2d_to_location_3d(region, r3d, (x, y), depth_loc)

        # update gizmo
        context.area.tag_redraw()

    def modal(self, context, event):
        # ============================ dragging ============================

        if event.type in ("RIGHTMOUSE", "ESC"):
            if self._draw_handler is not None:
                # cancel select box
                bpy.types.SpaceView3D.draw_handler_remove(self._draw_handler, "WINDOW")
                self._draw_handler = None
                # clear select box
                context.area.tag_redraw()
            return {"CANCELLED"}

        if event.type == "LEFTMOUSE":
            # mouse released
            if self._draw_handler is not None:
                # end select box
                bpy.types.SpaceView3D.draw_handler_remove(self._draw_handler, "WINDOW")
                self._draw_handler = None

            if not self._mouse_moved:
                # click select
                if context.object is not None and context.object.fast_sketch_properties.is_fast_sketch:
                    tube_index = context.object.fast_sketch_properties.active_index
                    tubes = context.object.fast_sketch_properties.tubes
                    if tube_index >= 0:
                        tube = tubes[tube_index]
                        if event.ctrl:
                            if self._clicked_index >= 0:
                                tube.nodes[self._clicked_index].active = not tube.nodes[self._clicked_index].active
                        else:
                            for index, node in enumerate(tube.nodes):
                                node.active = index == self._clicked_index
            # update gizmo
            context.area.tag_redraw()
            return {"FINISHED"}

        if event.type == "MOUSEMOVE":
            if self._draw_handler is not None:
                # ============================ select box ============================
                self._select_box_end = mathutils.Vector((event.mouse_region_x, event.mouse_region_y))

                # select all nodes inside selection box
                if context.object is not None and context.object.fast_sketch_properties.is_fast_sketch:
                    tube_index = context.object.fast_sketch_properties.active_index
                    tubes = context.object.fast_sketch_properties.tubes
                    if tube_index >= 0:
                        tube = tubes[tube_index]
                        if len(tube.nodes) == len(self._drag_start_state):
                            start = self._select_box_start
                            end = self._select_box_end
                            x0 = min(start.x, end.x)
                            x1 = max(start.x, end.x)
                            y0 = min(start.y, end.y)
                            y1 = max(start.y, end.y)
                            region = context.region
                            r3d = context.space_data.region_3d
                            obj_mat = context.object.matrix_world
                            for node_index in range(0, len(tube.nodes), 1):
                                node = tube.nodes[node_index]
                                node.active = self._drag_start_state[node_index]["active"] if event.ctrl else False
                                p = location_3d_to_region_2d(region, r3d, obj_mat @ node.location)
                                if p.x >= x0 and p.x <= x1 and p.y >= y0 and p.y <= y1:
                                    node.active = True

                # update select box and gizmo
                context.area.tag_redraw()

            elif self._drag_move:
                # ============================ drag move ============================
                if context.object is not None and context.object.fast_sketch_properties.is_fast_sketch:
                    tube_index = context.object.fast_sketch_properties.active_index
                    tubes = context.object.fast_sketch_properties.tubes
                    if tube_index >= 0:
                        tube = tubes[tube_index]

                        # auto select the unselected dragging node
                        if not self._mouse_moved and self._clicked_index >= 0 \
                                and not tube.nodes[self._clicked_index].active:
                            for index, node in enumerate(tube.nodes):
                                node.active = index == self._clicked_index

                        if len(tube.nodes) == len(self._drag_start_state):
                            # limit undo records num
                            now = time.time()
                            if now - FastSketchToolOperator._drag_input_last_timestamp > 0.3:
                                bpy.ops.ed.undo_push()
                            FastSketchToolOperator._drag_input_last_timestamp = now

                            # get mouse drag move vector
                            region = context.region
                            r3d = context.space_data.region_3d
                            x, y = event.mouse_region_x, event.mouse_region_y
                            mouse_loc = region_2d_to_location_3d(region, r3d, (x, y), self._drag_start_depth)
                            det = mouse_loc - self._drag_start_loc

                            for node_index in range(0, len(tube.nodes), 1):
                                node = tube.nodes[node_index]
                                if node.active:
                                    location = self._drag_start_state[node_index]["location"]
                                    location = self._drag_start_mat @ location
                                    location = location + det
                                    location = self._drag_start_inv_mat @ location
                                    node.location = location
                                    update_branch(tube_index, node_index)

                            update_geometry()

                            # update gizmo
                            context.area.tag_redraw()

            self._mouse_moved = True

        return {"RUNNING_MODAL"}


class FastSketchTool(bpy.types.WorkSpaceTool):
    bl_space_type = "VIEW_3D"
    bl_context_mode = "OBJECT"
    bl_idname = "fast_sketch.fast_sketch_tool"
    bl_label = "Fast Sketch"
    bl_description = ""
    bl_icon = (Path(__file__).parent / "tool_icon").as_posix()
    bl_widget = None
    bl_keymap = (
        ("fast_sketch.tool", {"type": "LEFTMOUSE", "value": "PRESS"}, None),
        ("fast_sketch.tool", {"type": "LEFTMOUSE", "value": "PRESS", "alt": True}, None),
        ("fast_sketch.tool", {"type": "LEFTMOUSE", "value": "PRESS", "alt": True, "shift": True}, None),
        ("fast_sketch.tool", {"type": "LEFTMOUSE", "value": "PRESS", "ctrl": True}, None),
        ("fast_sketch.tool", {"type": "WHEELUPMOUSE", "value": "PRESS"}, None),
        ("fast_sketch.tool", {"type": "WHEELDOWNMOUSE", "value": "PRESS"}, None),
        ("fast_sketch.tool", {"type": "WHEELUPMOUSE", "value": "PRESS", "alt": True}, None),
        ("fast_sketch.tool", {"type": "WHEELDOWNMOUSE", "value": "PRESS", "alt": True}, None),
        ("fast_sketch.tool", {"type": "WHEELUPMOUSE", "value": "PRESS", "alt": True, "shift": True}, None),
        ("fast_sketch.tool", {"type": "WHEELDOWNMOUSE", "value": "PRESS", "alt": True, "shift": True}, None),
        ("fast_sketch.tool", {"type": "MOUSEMOVE", "value": "ANY"}, None),
        ("fast_sketch.tool", {"type": "MOUSEMOVE", "value": "ANY", "alt": True}, None),
        ("fast_sketch.tool", {"type": "MOUSEMOVE", "value": "ANY", "alt": True, "shift": True}, None),
        ("fast_sketch.tool", {"type": "LEFT_ALT", "value": "PRESS"}, None),
        ("fast_sketch.tool", {"type": "RIGHT_ALT", "value": "PRESS"}, None),
        ("fast_sketch.tool", {"type": "LEFT_ALT", "value": "RELEASE"}, None),
        ("fast_sketch.tool", {"type": "RIGHT_ALT", "value": "RELEASE"}, None),
        ("fast_sketch.tool", {"type": "LEFT_SHIFT", "value": "PRESS"}, None),
        ("fast_sketch.tool", {"type": "RIGHT_SHIFT", "value": "PRESS"}, None),
        ("fast_sketch.tool", {"type": "LEFT_SHIFT", "value": "RELEASE"}, None),
        ("fast_sketch.tool", {"type": "RIGHT_SHIFT", "value": "RELEASE"}, None),
        ("fast_sketch.tool", {"type": "DEL", "value": "PRESS"}, None),
        ("fast_sketch.tool", {"type": "ESC", "value": "PRESS"}, None),
    )
