import bpy
import bgl
import mathutils
import math
from .misc import get_mouse_pointing_node_index


class FastSketchGizmo(bpy.types.Gizmo):
    bl_idname = "fast_sketch.gizmo"
    bl_label = "Fast Sketch Gizmo"

    _select_index = -1
    _circle_shape = None
    _line_shape = None

    def _make_circle_verts(self, radius, segments):
        circle_verts = []
        theta = 2 * math.pi / segments
        cos = math.cos(theta)
        sin = math.sin(theta)
        cx = radius
        cy = 0
        for i in range(segments + 1):
            circle_verts.append((cx, cy, 0))
            tmp = cx
            cx = cos * cx - sin * cy
            cy = sin * tmp + cos * cy
        return circle_verts

    def _draw_circle(self, context, location, radius):
        view_mat = context.space_data.region_3d.view_matrix
        view_vec = mathutils.Vector((-view_mat[2][0], -view_mat[2][1], -view_mat[2][2]))
        rot_mat = view_vec.to_track_quat('-Z', 'Y').to_matrix().to_4x4()
        mat = mathutils.Matrix.Translation(location) @ \
              rot_mat @ \
              mathutils.Matrix.Scale(radius, 4)
        self.draw_custom_shape(self._circle_shape, matrix=mat)

    def _begin_line(self):
        self._prev_line_point = None

    def _line_to(self, loc):
        if self._prev_line_point:
            v = loc - self._prev_line_point
            l = v.length
            if l < 1e-7:
                return
            n = v.normalized()
            a = n.angle((1, 0, 0))
            ax = -n.cross((1, 0, 0))
            mat_t = mathutils.Matrix.Translation(self._prev_line_point)
            mat_r = mathutils.Matrix.Rotation(a, 4, ax)
            mat_s = mathutils.Matrix.Scale(l, 4)
            mat = mat_t @ mat_r @ mat_s
            self.draw_custom_shape(self._line_shape, matrix=mat)
        self._prev_line_point = loc

    def setup(self):
        if not hasattr(self, "circle_shape"):
            self._circle_shape = self.new_custom_shape("LINE_STRIP", self._make_circle_verts(1, 32))
        if not hasattr(self, "line_shape"):
            self._line_shape = self.new_custom_shape("LINE_STRIP", ((0, 0, 0), (1, 0, 0)))

    def test_select(self, context, location):
        old_index = self._select_index
        _, self._select_index = get_mouse_pointing_node_index(context, location)

        # force redraw
        if old_index != self._select_index:
            context.region.tag_redraw()

        # don't use blender's default gizmo highlighting here so always return -1
        return -1

    def draw(self, context):
        is_inserting = context.window_manager.fast_sketch.is_inserting
        insert_index = context.window_manager.fast_sketch.insert_index
        insert_loc = mathutils.Vector(context.window_manager.fast_sketch.insert_loc)
        insert_radius = context.window_manager.fast_sketch.insert_radius

        if is_inserting and insert_index == -1:
            self.alpha = 1
            self.color = (1, 0, 1)
            self._draw_circle(context, insert_loc, insert_radius)

        if context.object is not None and context.object.fast_sketch_properties.is_fast_sketch:
            active_index = context.object.fast_sketch_properties.active_index
            tubes = context.object.fast_sketch_properties.tubes
            if active_index >= 0:
                tube = tubes[active_index]
                obj_mat = context.object.matrix_world
                obj_scale = obj_mat.to_scale()
                scale = min(obj_scale.x, obj_scale.y, obj_scale.z)
                self._begin_line()
                for index, node in enumerate(tube.nodes):
                    loc = obj_mat @ node.location

                    # draw circle
                    self.alpha = 1
                    self.color = (1, 1, 1)
                    if index == self._select_index and not is_inserting:
                        self.color = (1, 0, 1)
                    if node.active:
                        self.color = (1, 1, 0)
                    self._draw_circle(context, loc, scale * node.radius)

                    # draw line
                    self.alpha = 0.5
                    self.color = (1, 1, 1)
                    self._line_to(loc)

                    # insert
                    if is_inserting and insert_index == index:
                        self.alpha = 1
                        self.color = (1, 0, 1)
                        self._draw_circle(context, insert_loc, insert_radius)

                        self.alpha = 0.5
                        self.color = (1, 1, 1)
                        self._line_to(insert_loc)


class FastSketchGizmoGroup(bpy.types.GizmoGroup):
    bl_idname = "fast_sketch.gizmo_group"
    bl_label = "Fast Sketch Gizmo Group"
    bl_space_type = "VIEW_3D"
    bl_region_type = "WINDOW"
    bl_options = {"3D", "SCALE", "PERSISTENT"}

    @classmethod
    def poll(cls, context):
        return context.workspace.tools \
            .from_space_view3d_mode(context.mode, create=False).idname == "fast_sketch.fast_sketch_tool"

    def setup(self, context):
        self.gizmo = self.gizmos.new(FastSketchGizmo.bl_idname)

    def refresh(self, context):
        pass
