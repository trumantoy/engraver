from trimesh.creation import cylinder
from trimesh.visual import texture
import cairo
import wgpu
import pygfx as gfx
from pygfx.renderers.wgpu import *
from pygfx.objects import WorldObject
from pygfx.materials import Material
from pygfx.utils.transform import AffineTransform
import pylinalg as la
from importlib.resources import files
import numpy as np


class OriginMaterial(Material):
    """最简点材质：统一颜色与尺寸（screen-space）。"""

    uniform_type = dict(
        Material.uniform_type,
        color="4xf4",
        size="f4",
    )

    def __init__(self, *, color='black', size=5.0, **kwargs):
        super().__init__(**kwargs)
        self.color = gfx.Color('orange')
        self.size = float(size)

    @property
    def color(self):
        return tuple(self.uniform_buffer.data["color"])

    @color.setter
    def color(self, rgba):
        self.uniform_buffer.data["color"] = rgba
        self.uniform_buffer.update_full()

    @property
    def size(self):
        return float(self.uniform_buffer.data["size"])

    @size.setter
    def size(self, v):
        self.uniform_buffer.data["size"] = float(v)
        self.uniform_buffer.update_full()

    def _wgpu_get_pick_info(self, pick_value):
        from pygfx.utils import unpack_bitfield
        values = unpack_bitfield(pick_value, wobject_id=20, index=26, x=9, y=9)
        return {
            "vertex_index": values["index"],
            "point_coord": (values["x"] - 256.0, values["y"] - 256.0),
        }


@register_wgpu_render_function(gfx.WorldObject, OriginMaterial)
class OriginShader(BaseShader):
    type = "render"

    def __init__(self, wobject):
        super().__init__(wobject)

    def get_bindings(self, wobject, shared):
        bindings = [
            Binding("u_stdinfo", "buffer/uniform", shared.uniform_buffer),
            Binding("u_wobject", "buffer/uniform", wobject.uniform_buffer),
            Binding("u_material", "buffer/uniform", wobject.material.uniform_buffer),
            Binding("s_positions", "buffer/read_only_storage", wobject.geometry.positions, "VERTEX"),
        ]
        bindings = {i: b for i, b in enumerate(bindings)}
        self.define_bindings(0, bindings)
        return {0: bindings}

    def get_pipeline_info(self, wobject, shared):
        return {
            "primitive_topology": wgpu.PrimitiveTopology.triangle_list,
            "cull_mode": wgpu.CullMode.none,
        }

    def get_render_info(self, wobject, shared):
        offset, size = wobject.geometry.positions.draw_range
        offset, size = offset * 6, size * 6
        return {
            "indices": (size, 1, offset, 0),
            "render_mask": RenderMask.all,
        }

    def get_code(self):

        return """
            {$ include 'pygfx.std.wgsl' $}

            // 顶点着色器输入结构体
            struct VertexInput {
                @builtin(vertex_index) index : u32,  // 当前处理的顶点索引（0, 1, 2, 3, 4, 5...）
            };

            @vertex
            fn vs_main(in: VertexInput) -> Varyings {
                // 获取逻辑屏幕的半尺寸，用于NDC到屏幕坐标的转换
                let screen_factor: vec2<f32> = u_stdinfo.logical_size.xy / 2.0;
                
                // 将顶点索引转换为有符号整数
                let index = i32(in.index);
                
                // 计算逻辑：每个"点"展开为6个顶点（两个三角形组成正方形）
                // node_index: 这是第几个逻辑点（0, 1, 2...）
                // vertex_index: 该点内的第几个顶点（0,1,2,3,4,5）
                let node_index = index / 6;      // 整数除法，得到点索引
                let vertex_index = index % 6;    // 取余，得到点内顶点索引
                
                // 从存储缓冲区读取第node_index个点的模型空间位置
                let pos_m = load_s_positions(node_index);
                
                // 模型空间 -> 世界空间：应用对象的变换矩阵
                let pos_w = u_wobject.world_transform * vec4<f32>(pos_m.xyz, 1.0);
                
                // 世界空间 -> 相机空间：应用相机视图矩阵
                let pos_c = u_stdinfo.cam_transform * pos_w;
                
                // 相机空间 -> 裁剪空间：应用投影矩阵
                let pos_n = u_stdinfo.projection_transform * pos_c;
                
                // 裁剪空间 -> 逻辑屏幕坐标
                // 1. 透视除法：pos_n.xy / pos_n.w 得到NDC坐标 [-1,1]
                // 2. 映射到 [0,1]：+ 1.0
                // 3. 缩放到屏幕尺寸：* screen_factor
                let pos_s = (pos_n.xy / pos_n.w + 1.0) * screen_factor;
                
                // 计算点的大小（半径，逻辑像素）
                let half = 5.0 * u_material.size;
                
                // 定义6个顶点的相对偏移，形成两个三角形组成的正方形
                // 顶点顺序：左下、右下、左上、左上、右下、右上
                // 这样绘制两个三角形：左下-右下-左上 和 左上-右下-右上
                var deltas = array<vec2<f32>, 6>(
                    vec2<f32>(-1.0, -1.0),  // 左下
                    vec2<f32>( 1.0, -1.0),  // 右下  
                    vec2<f32>(-1.0,  1.0),  // 左上
                    vec2<f32>(-1.0,  1.0),  // 左上（重复，第二个三角形的起点）
                    vec2<f32>( 1.0, -1.0),  // 右下（重复，第二个三角形的第二个点）
                    vec2<f32>( 1.0,  1.0),  // 右上
                );
                
                // 根据当前顶点索引，获取对应的偏移量并缩放到点的大小
                let delta = deltas[vertex_index] * half;
                
                // 将偏移量应用到屏幕坐标，得到当前顶点的最终屏幕位置
                let the_pos_s = pos_s + delta;
                
                // 屏幕坐标 -> NDC坐标（保持与中心点相同的深度）
                // 1. 屏幕坐标归一化到 [0,1]：the_pos_s / screen_factor
                // 2. 映射到 [-1,1]：- 1.0
                // 3. 恢复裁剪空间的w分量：* pos_n.w
                // 4. z分量置零，让原点永远在最前面
                let the_pos_n = vec4<f32>((the_pos_s / screen_factor - 1.0) * pos_n.w, 0, pos_n.w);
                
                // 构建传递给片段着色器的插值变量
                var varyings: Varyings;
                
                // 设置裁剪空间位置（GPU需要这个进行光栅化）
                varyings.position = vec4<f32>(the_pos_n);
                
                // 设置世界空间位置（用于后续计算，如光照、深度等）
                varyings.world_pos = vec3<f32>(ndc_to_world_pos(the_pos_n));
                
                // 设置点内坐标（相对于点中心的偏移，物理像素单位）
                // 用于片段着色器中计算SDF和描边
                let l2p = u_stdinfo.physical_size.x / u_stdinfo.logical_size.x;  // 逻辑到物理像素比例
                varyings.pointcoord_p = vec2<f32>(delta * l2p);  // 转换为物理像素
                
                // 设置点的物理像素尺寸
                varyings.size_p = f32(u_material.size * l2p);
                varyings.pick_idx = u32(node_index);
                return varyings;
            }

            @fragment
            fn fs_main(varyings: Varyings) -> FragmentOutput {
                // 构建片段着色器输出
                var out: FragmentOutput;
                
                // 计算圆形SDF：到边缘的有向距离
                // length(pointcoord) 计算到中心的欧几里得距离
                // 0.5 * size_p 是圆的半径
                // 正值：点在圆外部，负值：点在圆内部，0值：点在圆边界上
                var dist_to_edge = length(varyings.pointcoord_p) - 0.5 * varyings.size_p;
                
                // 描边逻辑：判断当前片段是否在描边范围内
                var l2p = u_stdinfo.physical_size.x / u_stdinfo.logical_size.x;
                var edge_width = 0.75 * l2p;  // 描边宽度（物理像素）
                
                // 判断片段类型
                var is_edge = abs(dist_to_edge) < edge_width;    // 是否在描边范围内
                var is_inside = dist_to_edge < 0.0;              // 是否在点内部
                
                // 根据片段位置设置颜色
                var final_color: vec4<f32>;
                if (is_edge) {
                    // 描边颜色：黑色
                    final_color = vec4<f32>(0.0, 0.0, 0.0, 1.0);
                } else if (is_inside) {
                    // 点内部：使用材质颜色
                    let col = u_material.color;
                    // 将sRGB颜色转换为物理线性空间，保持alpha不变
                    final_color = vec4<f32>(srgb2physical(col.rgb), col.a);
                } else {
                    final_color = vec4<f32>(0.0, 0.0, 0.0, 0.0);
                }
                
                let pointcoord: vec2<f32> = varyings.pointcoord_p / l2p;

                // 设置最终输出颜色
                out.color = final_color;

                $$ if write_pick
                out.pick = (
                    pick_pack(u32(u_wobject.id), 20) +
                    pick_pack(varyings.pick_idx, 26) +
                    pick_pack(u32(pointcoord.x + 256.0), 9) +
                    pick_pack(u32(pointcoord.y + 256.0), 9)
                );
                $$ endif
                return out;
            }
        """


class AxisMaterial(Material):
    """坐标轴材质：支持颜色和线宽设置"""
    uniform_type = dict(
        Material.uniform_type,
        color="4xf4",
        size='f4'
    )

    def __init__(self, *, color,size, **kwargs):
        super().__init__(** kwargs)
        self.color = gfx.Color(color)
        self.size = size

    @property
    def color(self):
        return tuple(self.uniform_buffer.data["color"])

    @color.setter
    def color(self, rgba):
        self.uniform_buffer.data["color"] = rgba
        self.uniform_buffer.update_full()

    @property
    def size(self):
        return tuple(self.uniform_buffer.data["color"])

    @size.setter
    def size(self, value):
        self.uniform_buffer.data["size"] = value
        self.uniform_buffer.update_full()

    def _wgpu_get_pick_info(self, pick_value):
        from pygfx.utils import unpack_bitfield
        values = unpack_bitfield(pick_value, wobject_id=20, index=26, x=9, y=9)
        return {
            "vertex_index": values["index"],
            "point_coord": (values["x"] - 256.0, values["y"] - 256.0),
        }

@register_wgpu_render_function(WorldObject, AxisMaterial)
class AxisShader(BaseShader):
    type = "render"

    def __init__(self, wobject):
        super().__init__(wobject)

    def get_bindings(self, wobject, shared):
        bindings = [
            Binding("u_stdinfo", "buffer/uniform", shared.uniform_buffer),
            Binding("u_wobject", "buffer/uniform", wobject.uniform_buffer),
            Binding("u_material", "buffer/uniform", wobject.material.uniform_buffer),
            Binding("s_positions", "buffer/read_only_storage", wobject.geometry.positions, "VERTEX"),
            Binding("s_indices", "buffer/read_only_storage", wobject.geometry.indices, "VERTEX")
        ]
        bindings = {i: b for i, b in enumerate(bindings)}
        self.define_bindings(0, bindings)
        return {0: bindings}

    def get_pipeline_info(self, wobject, shared):
        return {
            "primitive_topology": wgpu.PrimitiveTopology.triangle_list,
            "cull_mode": wgpu.CullMode.none,
        }

    def get_render_info(self, wobject, shared):
        geometry = wobject.geometry
        material = wobject.material
        
        offset, size = geometry.indices.draw_range
        offset, size = 6 * offset, 6 * size

        return {
            "indices": (size, 1, offset, 0),
            "render_mask": RenderMask.all,
        }

    def get_code(self):
        return """
            {$ include 'pygfx.std.wgsl' $}

            struct VertexInput {
                @builtin(vertex_index) index : u32,
            };

            @vertex
            fn vs_main(in: VertexInput) -> Varyings {
                let mvp = u_stdinfo.projection_transform * u_stdinfo.cam_transform * u_wobject.world_transform;
                var origin_screen = mvp * vec4<f32>(0,0,0,1);
                var x_screen = mvp * vec4<f32>(0.01,0,0,1); 
                var y_screen = mvp * vec4<f32>(0,0.01,0,1); 
                var z_screen = mvp * vec4<f32>(0,0,0.01,1); 

                var x_direction = (vec3<f32>(x_screen.xyz / x_screen.w) - vec3<f32>(origin_screen.xyz / origin_screen.w)); 
                var y_direction = (vec3<f32>(y_screen.xyz / y_screen.w) - vec3<f32>(origin_screen.xyz / origin_screen.w));
                var z_direction = (vec3<f32>(z_screen.xyz / z_screen.w) - vec3<f32>(origin_screen.xyz / origin_screen.w));

                var size_1_radius = max(length(x_direction),max(length(y_direction),length(z_direction)));
                var scale = u_material.size / u_stdinfo.logical_size.y / size_1_radius;
                
                let index = i32(in.index);
                let face_index = index / 6;
                var sub_index = index % 6;
                
                let vii = load_s_indices(face_index);
                let i0 = i32(vii[sub_index]);
                var pos_n = mvp * vec4<f32>(load_s_positions(i0) * scale ,1.0);
                pos_n.z = 0;

                var varyings: Varyings;
                varyings.position = vec4<f32>(pos_n);
                
                let l2p = u_stdinfo.physical_size.x / u_stdinfo.logical_size.x;  // 逻辑到物理像素比例
                varyings.pointcoord_p = vec2<f32>(load_s_positions(i0).xy * l2p);  // 转换为物理像素
                
                // 设置点的物理像素尺寸
                varyings.pick_idx = u32(i0);
                return varyings;
            }

            @fragment
            fn fs_main(varyings: Varyings) -> FragmentOutput {
                var out: FragmentOutput; 
                out.color = vec4<f32>(u_material.color.xyz,1);

                var l2p = u_stdinfo.physical_size.x / u_stdinfo.logical_size.x;
                let pointcoord: vec2<f32> = varyings.pointcoord_p / l2p;

                $$ if write_pick
                out.pick = (
                    pick_pack(u32(u_wobject.id), 20) +
                    pick_pack(varyings.pick_idx, 26) +
                    pick_pack(u32(pointcoord.x + 256.0), 9) +
                    pick_pack(u32(pointcoord.y + 256.0), 9)
                );
                $$ endif
                return out;
            }
        """

class TranformHelper(gfx.WorldObject):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def set_ref_object(self,obj : gfx.WorldObject):
        aabb = obj.get_bounding_box()
        
        width,height =  aabb[1][0] - aabb[0][0], aabb[1][1] - aabb[0][1]
        self.local.position = obj.local.position
        self.local.rotation = obj.local.rotation
        self.local.scale = obj.local.scale

        self._ref = None
        self._object_to_control = obj

        self.translation = gfx.Line(gfx.Geometry(positions=[(-width/2,height/2,0),(width/2,height/2,0),(width/2,-height/2,0),(-width/2,-height/2,0),(-width/2,height/2,0)]), gfx.LineMaterial(color='green',thickness=2,depth_test=False))
        self.translation.name = 'translate'
        self.add(self.translation)

        self.rotataion_size = 20
        self.scale_size = 20

        self.rotation = gfx.Mesh(gfx.plane_geometry(1,1), gfx.MeshBasicMaterial(color=(0,0,0,0)))
        self.rotation.local.position = (0,height/2,0)
        self.rotation.name = 'rotate'
        box = gfx.Points(gfx.Geometry(positions=[(0,0,0)]), gfx.PointsMarkerMaterial(size=self.rotataion_size,marker='●',color='red',edge_color='white',depth_test=False))
        self.rotation.add(box)
        self.add(self.rotation)

        self.scale = gfx.Mesh(gfx.plane_geometry(1,1), gfx.MeshBasicMaterial(color=(0,0,0,0)))
        self.scale.local.position = (width/2,-height/2,0)
        self.scale.name = 'scale'
        box = gfx.Points(gfx.Geometry(positions=[(0,0,0)]), gfx.PointsMarkerMaterial(size=self.scale_size,marker='■',color='blue',edge_color='white',depth_test=False))
        self.scale.add(box)
        self.add(self.scale)

    def _update_scale_factor(self,camera : gfx.PerspectiveCamera):
        x_dim, y_dim = camera.logical_size
        screen_space = AffineTransform()
        screen_space.position = (-1, 1, 0)
        screen_space.scale = (2 / x_dim, -2 / y_dim, 1)
        mvp = screen_space.inverse_matrix @ camera.camera_matrix
        mvp_inverse = la.mat_inverse(mvp)
        
        o = self.rotation.world.position
        o_screen = la.vec_transform(o,mvp)
        o_screen[0] -= self.rotataion_size
        o2 = la.vec_transform(o_screen,mvp_inverse)
        size = np.linalg.norm(o - o2)
        self.rotation.world.scale = size

        o = self.scale.world.position
        o_screen = la.vec_transform(o,mvp)
        o_screen[0] -= self.scale_size
        o2 = la.vec_transform(o_screen,mvp_inverse)
        size = np.linalg.norm(o - o2)
        self.scale.world.scale = size

    def _process_event(self, event, world_pos, camera):
        self._update_scale_factor(camera)
        screen_pos = np.array([event.x,event.y])
        
        if event.type == "pointer_down":
            self._ref = None
            
            if event.button != 3 or event.modifiers: return False

            for obj in [self.rotation,self.scale,self.translation]:
                obj : gfx.WorldObject
                aabb = obj.get_geometry_bounding_box()

                lb = np.array([aabb[0][0],aabb[0][1],0])
                rb = np.array([aabb[1][0],aabb[0][1],0])
                rt = np.array([aabb[1][0],aabb[1][1],0])
                lt = np.array([aabb[0][0],aabb[1][1],0])
                lb = la.vec_transform(lb, obj.world.matrix, projection=False)
                rb = la.vec_transform(rb, obj.world.matrix, projection=False)
                rt = la.vec_transform(rt, obj.world.matrix, projection=False)
                lt = la.vec_transform(lt, obj.world.matrix, projection=False)
                
                a = np.cross(rb - lb,world_pos - lb)
                a = a / np.linalg.norm(a)
                b = np.cross(rt - rb,world_pos - rb)
                b = b / np.linalg.norm(b)
                c = np.cross(lt - rt,world_pos - rt)
                c = c / np.linalg.norm(c)
                d = np.cross(lb - lt,world_pos - lt)
                d = d / np.linalg.norm(d)

                intersection = np.dot(a,b) >= 0 and np.dot(b,c) >= 0 and np.dot(c,d) >= 0 and np.dot(d,a) >= 0
                if intersection: 
                    self._ref = dict(kind=obj.name,world_pos=world_pos,screen_pos=screen_pos)
                    break

            if not self._ref:
                return False
            
        elif event.type == "pointer_move":
            if not self._ref:
                return False
            
            if self._ref['kind'] == 'translate':
                offset = world_pos - self._ref['world_pos']
                self.local.position = self.local.position + offset
                self._object_to_control.local.position = self._object_to_control.local.position + offset 
                self._ref['world_pos'] = world_pos
            elif self._ref['kind'] == 'rotate':
                center = self._object_to_control.world.position
                dir = world_pos - center
                dir = dir / np.linalg.norm(dir)
                dir2 = self.rotation.world.position - center
                dir2 = dir2 / np.linalg.norm(dir2)
                dir2[2] = dir[2] = 0
                offset = min(np.dot(dir,dir2),1.000)
                offset = np.arccos(offset)
                aspect = np.cross(dir,dir2)
                aspect = aspect / np.linalg.norm(aspect)
                if aspect[2] > 0: offset = -offset
                self.local.euler_z += offset
                self._object_to_control.local.euler_z += offset
                self._ref['screen_pos'] = screen_pos
            elif self._ref['kind'] == 'scale':
                center = self._object_to_control.world.position
                dir = self._ref['world_pos'] - center
                dir2 = world_pos - center
                scale = np.linalg.norm(dir2) / np.linalg.norm(dir) * self.local.scale
                offset = world_pos - self._ref['world_pos']
                self.local.scale = scale
                self._object_to_control.local.scale = scale
                self._ref['world_pos'] = world_pos
        elif event.type == "pointer_up":
            self._ref = None
        
        return True

class Label(gfx.WorldObject):
    def __init__(self,text,font_size,family,*args,**kwargs):
        super().__init__(*args,**kwargs)

        self.text = text
        self.font_size = font_size
        self.family = family
        
        temp_surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, 1, 1)  # 临时1x1像素表面
        temp_ctx = cairo.Context(temp_surface)
        
        # 配置与最终绘制一致的字体
        temp_ctx.select_font_face(family, cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
        temp_ctx.set_font_size(font_size)
        
        # 获取文字的详细边界信息（核心参数）
        text_info = temp_ctx.text_extents(text)
        text_width = text_info.width          # 文字左边缘到右边缘的实际宽度（无多余）
        text_height = text_info.height        # 文字上边缘到下边缘的实际高度（含上下伸部分）
        text_x_bearing = text_info.x_bearing  # 文字左边缘相对于绘制起点的偏移（通常为0，无需修正）
        text_y_bearing = text_info.y_bearing  # 文字上边缘相对于绘制起点的偏移（负数值，需修正避免顶部裁剪）

        # 2. 图片尺寸=文字实际尺寸（零留白关键）
        img_width = int(text_width)
        img_height = int(text_height)

        # 3. 创建最终零留白图片表面
        final_surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, img_width, img_height)
        final_ctx = cairo.Context(final_surface)

        # 5. 配置字体（与临时上下文一致，确保尺寸匹配）
        final_ctx.select_font_face(family, cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
        final_ctx.set_font_size(font_size)

        # 6. 修正文字位置：抵消y_bearing偏移，确保文字顶部贴合图片上边框
        # x起点：0（文字左边缘=图片左边缘）
        text_x = -text_x_bearing  # 通常x_bearing=0，即text_x=0
        # y起点：-text_y_bearing（抵消上边缘偏移，文字顶部=图片上边缘）
        text_y = -text_y_bearing

        # 7. 绘制文字（黑色，可修改RGB值换颜色）
        final_ctx.set_source_rgb(1, 1, 1)
        final_ctx.move_to(text_x, text_y)
        final_ctx.show_text(text)
        argb_array = np.frombuffer(final_surface.get_data(), dtype=np.uint8).reshape((img_height, img_width, 4))
        tex = gfx.Texture(argb_array[:, :, [1, 2, 3, 0]],dim=2)
        tex_map = gfx.TextureMap(tex,filter='nearest')
        self.obj = obj = gfx.Mesh(gfx.plane_geometry(0.02,0.02),gfx.MeshBasicMaterial(pick_write=True,map=tex_map))
        self.add(obj)

    def get_geometry_bounding_box(self):
        return self.obj.get_geometry_bounding_box()

class Bitmap(gfx.WorldObject):
    def __init__(self):
        super().__init__()
        self.im = (np.indices((10, 10)).sum(axis=0) % 2).astype(np.float32) * 255
        tex = gfx.Texture(self.im,dim=2)
        tex_map = gfx.TextureMap(tex,filter='nearest')
        self.obj = gfx.Mesh(gfx.plane_geometry(0.02,0.02),gfx.MeshBasicMaterial(pick_write=True,map=tex_map)) 
        self.add(self.obj)

    def get_image(self):
        return self.im.astype(np.uint8)
    

    def get_geometry_bounding_box(self):
        return self.obj.get_geometry_bounding_box()


class Engravtor(gfx.WorldObject):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.steps = list()
        self.init_params()

        path = files("simtoy.data.engravtor") / "engravtor.gltf"
        self.scene : gfx.Scene = gfx.load_gltf(path).scene
        self.scene.traverse(lambda o: setattr(o,'cast_shadow',True) or  setattr(o,'receive_shadow',True),True)

        tool : gfx.WorldObject = self.scene.children[0]
        self.add(tool)

        self.target_area : gfx.WorldObject = next(tool.iter(lambda o: o.name == '工作区-内'))
        self.laser_aperture : gfx.WorldObject = next(tool.iter(lambda o: o.name == '激光'))

        camera : gfx.PerspectiveCamera = next(tool.iter(lambda o: o.name == '摄像头'))
        camera.show_pos(self.target_area.world.position,up=[0,0,1])
        camera.local.scale = 1

        persp_camera : gfx.PerspectiveCamera = next(tool.iter(lambda o: o.name == '观察点'))
        persp_camera.show_pos(self.target_area.world.position,up=[0,0,1],depth=1.0)
        self.persp_camera = persp_camera

        # ortho_camera : gfx.OrthographicCamera = next(gltf.scene.iter(lambda o: o.name == '正交相机'))
        # ortho_camera.show_pos(target.world.position,up=[0,0,1])
        
        # self.controller = gfx.OrbitController()
        # self.controller.add_camera(persp_camera)
        # self.controller.add_camera(ortho_camera)

        self.controller = GrblController()
        
        geom = gfx.sphere_geometry(radius=0.0001)
        material = gfx.MeshBasicMaterial(color=(1, 0, 0, 1),flat_shading=True)
        self.focus = gfx.Mesh(geom,material)
        self.target_area.add(self.focus)

        self.add_event_handler(self._process_event,"pointer_down","pointer_move","pointer_up",'wheel')
        self.transform_helper = None
        self.selected_func = None
        self.transformed_func = None

    def set_selected_func(self,func):
        self.selected_func = func

    def set_transformed_func(self,func):
        self.transformed_func = func

    def _process_event(self, event : gfx.Event):
        screen_xy = np.array([event.x,event.y,0,1])
        x_dim, y_dim = self.persp_camera.logical_size
        screen_space = AffineTransform()
        screen_space.position = (-1, 1, 0)
        screen_space.scale = (2 / x_dim, -2 / y_dim, 1)
        screen_to_ndc = screen_space.matrix
        ndc_xy = screen_to_ndc @ screen_xy
        ndc_to_world = la.mat_inverse(self.persp_camera.camera_matrix)
        world_xy = la.vec_transform(ndc_xy[:3],ndc_to_world)[:3]
        O = self.persp_camera.world.position
        D = world_xy - O
        D = D / np.linalg.norm(D)
        aabb = self.target_area.get_bounding_box()
        lb = np.array([aabb[0][0],aabb[0][1],0])
        rb = np.array([aabb[1][0],aabb[0][1],0])
        rt = np.array([aabb[1][0],aabb[1][1],0])
        lt = np.array([aabb[0][0],aabb[1][1],0])
        N = np.cross(rb - lb,rt - lb)
        N = N / np.linalg.norm(N)
        C = self.target_area.world.position
        t = np.dot(N,O - C) / np.dot(N,-D)
        world_pos = O + t * D 

        if self.transform_helper:
            if self.transform_helper._process_event(event,world_pos,self.persp_camera):
                if self.transformed_func: self.transformed_func(self.transform_helper._object_to_control)
                return
            
        selected_items = []
        
        if event.type == "pointer_down" and event.button == 3:
            for obj in self.target_area.children:
                if type(obj) != Label and type(obj) != Bitmap:
                    continue
                aabb = obj.get_geometry_bounding_box()
                lb = np.array([aabb[0][0],aabb[0][1],0])
                rb = np.array([aabb[1][0],aabb[0][1],0])
                rt = np.array([aabb[1][0],aabb[1][1],0])
                lt = np.array([aabb[0][0],aabb[1][1],0])    
                lb = la.vec_transform(lb, obj.world.matrix, projection=False)
                rb = la.vec_transform(rb, obj.world.matrix, projection=False)
                rt = la.vec_transform(rt, obj.world.matrix, projection=False)
                lt = la.vec_transform(lt, obj.world.matrix, projection=False)

                a = np.cross(rb - lb,world_pos - lb)
                a = a / np.linalg.norm(a)
                b = np.cross(rt - rb,world_pos - rb)
                b = b / np.linalg.norm(b)
                c = np.cross(lt - rt,world_pos - rt)
                c = c / np.linalg.norm(c)
                d = np.cross(lb - lt,world_pos - lt)
                d = d / np.linalg.norm(d)

                intersection = np.dot(a,b) > 0 and np.dot(b,c) > 0 and np.dot(c,d) > 0 and np.dot(d,a)
                if intersection:
                    selected_items.append(obj)
                    if self.selected_func: self.selected_func(obj)
                    break
            
            if self.transform_helper:
                self.target_area.remove(self.transform_helper)
                self.transform_helper = None

            if selected_items:
                self.transform_helper = TranformHelper()
                self.transform_helper.set_ref_object(selected_items[0])
                self.target_area.add(self.transform_helper)
                self.transform_helper._process_event(event,world_pos,self.persp_camera)
                    
    def step(self,dt):
        if self.steps:
            self.steps[0]()
            self.steps.pop(0)

        aabb = self.target.get_geometry_bounding_box()
        self.focus.local.z = aabb[1][2] - aabb[0][2]

    def init_params(self):
        self.y_lim = self.x_lim = (0,0.100)
        self.light_spot_size = 0.0000075
        self.pixelsize = 0.1
        self.paths = list()

    def get_view_focus(self):
        return self.camera.local.position,self.target_area.local.position

    def get_consumables(self):
        return ['木板-100x100x1','木板-100x100x10']

    def set_consumable(self,name):
        target : gfx.WorldObject = next(self.scene.iter(lambda o: o.name == name))
        target.material.pick_write = True
        target.cast_shadow = True
        target.receive_shadow=True
        target.local.position = self.target_area.local.position
        aabb = target.get_geometry_bounding_box()
        target_height = (aabb[1][2] - aabb[0][2])
        target.local.z = target_height / 2
        self.target = target
        self.target_area.add(target)
    
    def unselect_all(self,parent : gfx.WorldObject):
        for obj in parent.children:
            if TranformHelper in type(obj).__mro__:
                obj : TranformHelper
                obj.set_object(None)

    def get_viewport(self):
        return [self.persp_camera]

    def get_hot_items(self):
        def label():
            aabb = self.target.get_geometry_bounding_box()
            target_height = (aabb[1][2] - aabb[0][2])
            
            element = Label('中',100 / self.pixelsize,'KaiTi',name='文本')
            element.local.z = target_height + 0.00001
            element._camera = self.persp_camera
            self.target_area.add(element)
            return element 

        def bitmap():
            target = self.target
            aabb = target.get_geometry_bounding_box()
            target_height = (aabb[1][2] - aabb[0][2])
            
            element = Bitmap()
            element.local.z = target_height + 0.00001
            element._camera = self.persp_camera
            self.target_area.add(element)
            return element 

        return [('文本',label,'format-text-bold'),('位图',bitmap,'image-x-generic-symbolic')]

    def export_svg(self,file_name):
        import cairo
        width = int((self.x_lim[1] - self.x_lim[0]) * 1000)
        height = int((self.y_lim[1] - self.y_lim[0]) * 1000)
 
        with cairo.SVGSurface(file_name, width, height) as surface:
            cr = cairo.Context(surface)
            cr.save()
            cr.translate(width / 2,height / 2)
            for obj in self.target_area.children:
                if type(obj) == Label:
                    obj : Label
                    cr.set_source_rgb(1, 0, 0)
                    cr.set_line_width(self.light_spot_size * 1000 / self.pixelsize)
                    cr.set_font_size(obj.font_size * 1000)
                    cr.select_font_face(obj.family)
                    ascent, descent, font_height, max_x_advance, max_y_advance = cr.font_extents()
                    text_extents = cr.text_extents(obj.text)
                    xoffset = 0.
                    yoffset = 0.
                    cr.move_to(obj.local.x * 1000,  
                                -(obj.local.y * 1000))

                    cr.text_path(obj.text)
                    cr.stroke()
                    
                elif type(obj) == Bitmap:
                    obj : Bitmap
                    aabb = obj.get_bounding_box()
                    width = int((aabb[1][0] - aabb[0][0]) * 1000 / self.pixelsize)
                    height = int((aabb[1][1] - aabb[0][1]) * 1000 / self.pixelsize)

                    import PIL.Image
                    image = PIL.Image.fromarray(obj.get_image())
                    image = image.resize((width,height),resample=PIL.Image.Resampling.NEAREST)
                    image = image.convert('RGBA')
                    rgba_array = np.array(image)
                    
                    image_surface = cairo.ImageSurface.create_for_data(rgba_array.data,cairo.Format.ARGB32,width,height)

                    cr.scale(self.pixelsize,self.pixelsize)
                    cr.set_source_surface(image_surface, 
                        obj.local.x * 1000 / self.pixelsize - image_surface.get_width() / 2, 
                        -(obj.local.y * 1000 / self.pixelsize + image_surface.get_height() / 2))
                
                    cr.paint()
                else:
                    pass
            cr.restore()

        return width,height
    
    def excute(self,line : str):
        commands = line.split(' ')
        for cmd in commands:
            if cmd == 'G0':
                self.laser = None
                self.line = None
                self.cutting = False
                self.focus.local.y = self.focus.local.x = 0
            elif cmd == 'M3':
                pos = (self.focus.local.x,self.focus.local.y,0)
                self.line = gfx.Line(gfx.Geometry(positions=[pos]),gfx.LineMaterial(thickness=self.light_spot_size,thickness_space='world',color='red'))

                origin = self.laser_aperture.local.position[:]
                direction = self.focus.local.position[:]
                self.laser = gfx.Line(gfx.Geometry(positions=[origin,direction]),gfx.LineMaterial(thickness=self.light_spot_size,thickness_space='world',color='red'))
                self.target_area.add(self.laser)
            elif cmd == 'G1':
                self.cutting = True
            elif cmd == 'M5':
                self.line = None
                self.cutting = False

                if hasattr(self,'laser') and self.laser:
                    self.target_area.remove(self.laser)
                    self.laser = None
            elif cmd.startswith('X'):
                self.focus.local.x = float(cmd[1:]) / 1000
            elif cmd.startswith('Y'):
                self.focus.local.y = float(cmd[1:]) / 1000
            else:
                pass
        
        if not self.cutting: return 
        pos = (self.focus.local.x,self.focus.local.y,0)
        geometry = gfx.Geometry(positions=np.concatenate([self.line.geometry.positions.data,[pos]],dtype=np.float32))
        self.line.geometry = geometry

        origin = self.laser_aperture.local.position[:]
        direction = self.focus.local.position[:]
        self.laser.geometry = gfx.Geometry(positions=[origin,direction])

        if self.line.geometry.positions.data.shape[0] == 2:
            aabb = self.target.get_geometry_bounding_box()
            self.line.local.z = (aabb[1][2] - aabb[0][2]) / 2
            self.target.add(self.line)

    def preview(self,gcode):
        self.gcode = gcode.splitlines()

        def fun(i):
            if i == len(self.gcode): return
            
            while True:
                line = self.gcode[i].strip()
                if line and not line.startswith(';'): break
                i+=1

            self.excute(line)
            self.steps.append(lambda: fun(i+1))
        self.steps.append(lambda: fun(0))

    def run(self,gcode):
        self.controller.set_axes_invert()
        self.controller.set_process_params()
        self.gcode = gcode.splitlines()
        self.gcode = [line.strip() for line in self.gcode if line and not line.startswith(';')]

        def fun(i):
            if i == len(self.gcode): return

            lines = self.gcode[i:i+100]
            self.controller.excute(lines)

            self.steps.append(lambda: fun(i+len(lines)))
        self.steps.append(lambda: fun(0))
    

import serial

class GrblController:
    def __init__(self):
        """初始化Grbl控制器连接"""
        self.serial = None
        
    def connect(self,port):
        """连接到Grbl控制器"""
        try:
            # 初始化串口（根据实际设备修改参数）
            self.serial = serial.Serial(port=port,baudrate=9600,timeout=1)

            # 检查串口是否打开
            if not self.serial.is_open:
                self.serial = None
                print("串口打开失败") 
                return False
            
        except Exception as e:
            self.serial = None
            print(f"连接失败: {str(e)}")
            return False

        print(f"串口 {self.serial.name} 已打开")
        return True
    
    def disconnect(self):
        """断开与Grbl控制器的连接"""
        if self.serial:
            self.serial.close()
            print("已断开与Grbl控制器的连接")


    def set_axes_invert(self):
        """设置轴 invert"""
        req = f'$240P2P6P5\n'.encode()
        print(req)
        self.serial.write(req)
        res = self.serial.readline()
        print(res)

    def set_process_params(self):
        """
        T：参数识别 F:速度 S:功率 C:频率 D:占空比 E:开光延时
        H:关光延时 U:跳转延时
        单位F:mm/s S[0-100]% Cus Dus EHUms
        1kHz占空比50%  C：1000 D：500
        """

        req = f'T0 C22\n'.encode()
        print(req)
        self.serial.write(req)
        res = self.serial.readline()
        print(res)
    
    def excute(self, lines):
        queue_size = self.get_queue_size()
        print('queue_size',queue_size)   

        for line in lines:
            req = f'{line}\n'.encode()
            self.serial.write(req)
        
        for _ in range(len(lines)):
            self.serial.readline()
    
    def get_queue_size(self):
        """获取Grbl接收缓存队列余量"""
        req = '%\n'.encode()
        print(req)
        self.serial.write(req)
        res = self.serial.readline()
        print(res)
        return int(res.decode().split(':')[1])
    
    def get_status(self):
        """获取Grbl状态信息"""
        if not self.connected:
            print("未连接到控制器，请先连接")
            return None
            
        try:
            # 发送状态请求
            self.serial.write(b'?')
            response = self.serial.readline().decode('utf-8').strip()
            return response
        except Exception as e:
            print(f"获取状态出错: {str(e)}")
            return None
