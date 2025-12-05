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
from PIL import Image


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
                    self._ref = dict(kind=obj.name,world_pos=world_pos,screen_pos=screen_pos,rotation_pos=self.rotation.world.position,euler_z=self.world.euler_z)
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
                dir = self._ref['rotation_pos'] - center
                dir = dir / np.linalg.norm(dir)
                dir2 = world_pos - center
                dir2 = dir2 / np.linalg.norm(dir2)
                offset = np.dot(dir,dir2)
                if 1 - offset < 0.001: offset = 0
                elif 1 + offset < 0.001: offset = np.deg2rad(180)
                else: offset = np.arccos(offset)
                aspect = np.cross(dir,dir2)
                aspect = aspect / np.linalg.norm(aspect)
                if aspect[2] < 0: offset = -offset
                self.world.euler_z = self._ref['euler_z'] + offset
                self._object_to_control.world.euler_z = self._ref['euler_z'] + offset
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
    
class Element(gfx.WorldObject):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.params = dict()
        self.params['power'] = 100
        self.params['excutable'] = True
        self.params['light_source'] = '红光'
        self.params['speed'] = 100
        self.params['engraving_mode'] = '填充雕刻'

class Label(Element):
    def __init__(self,text,font_size,family,pixelsize,*args,**kwargs):
        super().__init__(*args,**kwargs)
        
        self.text = text
        self.font_size = font_size
        self.family = family
        
        temp_surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, 1, 1)  # 临时1x1像素表面
        temp_ctx = cairo.Context(temp_surface)
        
        # 配置与最终绘制一致的字体
        temp_ctx.select_font_face(family, cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
        temp_ctx.set_font_size(self.font_size)
        
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
        final_ctx.set_font_size(self.font_size)

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
        tex_map = gfx.TextureMap(tex)
        width = img_width * pixelsize / 1000
        height = img_height * pixelsize / 1000
        
        self.obj = obj = gfx.Mesh(gfx.plane_geometry(width,height),gfx.MeshBasicMaterial(map=tex_map,depth_test=False))
        self.add(obj)

    def get_geometry_bounding_box(self):
        return self.obj.get_geometry_bounding_box()
    
    def get_world_oriented_bounding_box(self):
        aabb = self.obj.get_geometry_bounding_box()
        lb = np.array([aabb[0][0],aabb[0][1],0])
        rb = np.array([aabb[1][0],aabb[0][1],0])
        rt = np.array([aabb[1][0],aabb[1][1],0])
        lt = np.array([aabb[0][0],aabb[1][1],0])    
        lb = la.vec_transform(lb, self.world.matrix, projection=False)
        rb = la.vec_transform(rb, self.world.matrix, projection=False)
        rt = la.vec_transform(rt, self.world.matrix, projection=False)
        lt = la.vec_transform(lt, self.world.matrix, projection=False)
        return (lb,rb,rt,lt)
    
    def get_oriented_bounding_box(self):
        aabb = self.obj.get_geometry_bounding_box()
        lb = np.array([aabb[0][0],aabb[0][1],0])
        rb = np.array([aabb[1][0],aabb[0][1],0])
        rt = np.array([aabb[1][0],aabb[1][1],0])
        lt = np.array([aabb[0][0],aabb[1][1],0])    
        lb = la.vec_transform(lb, self.local.matrix, projection=False)
        rb = la.vec_transform(rb, self.local.matrix, projection=False)
        rt = la.vec_transform(rt, self.local.matrix, projection=False)
        lt = la.vec_transform(lt, self.local.matrix, projection=False)
        return (lb,rb,rt,lt)

class Bitmap(Element):
    def __init__(self,pixelsize,im = None,*args,**kwargs):
        super().__init__(*args,**kwargs)

        if im is None:
            im = (np.indices((10, 10)).sum(axis=0) % 2).astype(np.float32) * 255

        height = im.shape[0] * pixelsize / 1000
        width = im.shape[1] * pixelsize / 1000
        tex = gfx.Texture(im,dim=2)
        tex_map = gfx.TextureMap(tex,filter='nearest')
        self.obj = gfx.Mesh(gfx.plane_geometry(width,height),gfx.MeshBasicMaterial(map=tex_map,depth_test=False)) 
        self.add(self.obj)
        self.im = im

    def get_image(self):
        return self.im.astype(np.uint8)
    
    def get_geometry_bounding_box(self):
        return self.obj.get_geometry_bounding_box()
    
    def get_geometry_bounding_box(self):
        return self.obj.get_geometry_bounding_box()
    
    def get_world_oriented_bounding_box(self):
        aabb = self.obj.get_geometry_bounding_box()
        lb = np.array([aabb[0][0],aabb[0][1],0])
        rb = np.array([aabb[1][0],aabb[0][1],0])
        rt = np.array([aabb[1][0],aabb[1][1],0])
        lt = np.array([aabb[0][0],aabb[1][1],0])    
        lb = la.vec_transform(lb, self.world.matrix, projection=False)
        rb = la.vec_transform(rb, self.world.matrix, projection=False)
        rt = la.vec_transform(rt, self.world.matrix, projection=False)
        lt = la.vec_transform(lt, self.world.matrix, projection=False)
        return (lb,rb,rt,lt)
    
    def get_oriented_bounding_box(self):
        aabb = self.obj.get_geometry_bounding_box()
        lb = np.array([aabb[0][0],aabb[0][1],0])
        rb = np.array([aabb[1][0],aabb[0][1],0])
        rt = np.array([aabb[1][0],aabb[1][1],0])
        lt = np.array([aabb[0][0],aabb[1][1],0])
        lb = la.vec_transform(lb, self.local.matrix, projection=False)
        rb = la.vec_transform(rb, self.local.matrix, projection=False)
        rt = la.vec_transform(rt, self.local.matrix, projection=False)
        lt = la.vec_transform(lt, self.local.matrix, projection=False)
        return (lb,rb,rt,lt)

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
        self.target_area.material.pick_write = True
        self.laser_aperture : gfx.WorldObject = next(tool.iter(lambda o: o.name == '激光'))

        camera : gfx.PerspectiveCamera = next(tool.iter(lambda o: o.name == '摄像头'))
        camera.show_pos(self.target_area.world.position,up=[0,0,1])
        camera.local.scale = 1

        persp_camera : gfx.PerspectiveCamera = next(tool.iter(lambda o: o.name == '观察点'))
        persp_camera.show_pos(self.target_area.world.position,up=[0,0,1],depth=1.0)
        self.persp_camera = persp_camera
        
        self.focus = gfx.Mesh(gfx.sphere_geometry(radius=self.pixelsize * 2/1000 ),gfx.MeshBasicMaterial(color=(1, 0, 0, 1),depth_test=False,flat_shading=True))
        self.focus.render_order = 1
        self.target_area.add(self.focus)

        self.laser = gfx.Line(gfx.Geometry(positions=[self.laser_aperture.local.position,self.focus.local.position]),gfx.LineMaterial(thickness=self.pixelsize/1000,thickness_space='world',color=(1, 0, 0, 0)))
        self.target_area.add(self.laser)

        self.add_event_handler(self._process_event,"pointer_down","pointer_move","pointer_up",'wheel')
        self.transform_helper = None
        self.selected_func = None
        self.transformed_func = None

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
                self.transformed_func(self.transform_helper._object_to_control)
                return
            
        selected_items = []
        
        if event.type == "pointer_down" and event.button == 3:
            for obj in self.target_area.children:
                if Element not in obj.__class__.__mro__:
                    continue
                lb,rb,rt,lt = obj.get_world_oriented_bounding_box()
                
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
                    break
            
            if self.transform_helper:
                self.target_area.remove(self.transform_helper)
                self.transform_helper = None

            if selected_items:
                self.transform_helper = TranformHelper()
                self.transform_helper.set_ref_object(selected_items[0])
                self.target_area.add(self.transform_helper)
                self.transform_helper._process_event(event,world_pos,self.persp_camera)
                self.selected_func(self.transform_helper._object_to_control)
            else:
                self.selected_func(None)
    
    def step(self,dt):
        if self.steps:
            f = self.steps.pop(0)
            f(dt)

        aabb = self.target.get_geometry_bounding_box()
        self.focus.local.z = aabb[1][2] - aabb[0][2]

    def init_params(self):
        self.y_lim = self.x_lim = (0,0.100)
        self.light_spot_size = 0.0000075
        self.pixelsize = 0.1
        self.paths = list()
        self.speed = 100
        self.power = 0
        self.pos = (0,0,0)

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
    
    def get_viewport(self):
        return [self.persp_camera]

    def get_hot_items(self):
        def label():
            aabb = self.target.get_geometry_bounding_box()
            target_height = (aabb[1][2] - aabb[0][2])
            
            element = Label('中国智造',72,'KaiTi',self.pixelsize,name='文本')
            element.local.z = target_height
            self.target_area.add(element)
            return element 

        def bitmap(im):
            target = self.target
            aabb = target.get_geometry_bounding_box()
            target_height = (aabb[1][2] - aabb[0][2])
            element = Bitmap(self.pixelsize,im)
            element.local.z = target_height
            self.target_area.add(element)
            return element 

        return [('文本',label,'format-text-bold'),('图片',bitmap,'image-x-generic-symbolic')]
    
    def get_items(self):
        items = []
        for obj in self.target_area.children:
            if Element not in obj.__class__.__mro__:
                continue
            items.append(obj)
        return items
    
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

                    image = Image.fromarray(obj.get_image())
                    image = image.resize((width,height),resample=Image.Resampling.NEAREST)
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
        lines = line.split('\n')
        for line in lines:
            if not line or line.startswith(';'): continue
            moveable = False
            x = None
            y = None
            power = self.power
            speed = self.speed
            print(line)
            command = line.split(' ')
            for param in command:
                if param == 'G0':
                    moveable = True
                    x = 0
                    y = 0
                elif param == 'M3':
                    power = self.power
                elif param == 'G1': 
                    moveable = True
                elif param == 'M5':
                    power = 0
                elif param.startswith('X'):
                    x = float(param[1:])
                    moveable = True
                elif param.startswith('Y'):
                    y = float(param[1:])
                    moveable = True
                elif param.startswith('F'):
                    speed = float(param[1:])
                elif param.startswith('S'):
                    power = float(param[1:])
                else:
                    pass
                
            if moveable:
                def make_f(*args):
                    return lambda dt: self.move(dt,*args)
                self.steps.append(make_f(x,y,speed))

                self.laser.material.color = (1,0,0,power / 100)
                self.laser.geometry.update()

            self.power = power
            self.speed = speed

    def move(self,dt,x,y,speed):
        start = self.focus.local.position[:2] * 1000
        end = np.array([x,y])
        dir = end - start
        S = np.linalg.norm(dir)
        dir /= S

        v_max=100; v0=0; v1=0; a=100

        # 加速阶段：从v0到v_max
        t1 = (v_max - v0) / a  # 加速时间
        s1 = v0 * t1 + 0.5 * a * t1**2  # 加速距离
            
        # 减速阶段：从v_max到v1
        t3 = (v_max - v1) / a  # 减速时间
        s3 = v_max * t3 - 0.5 * a * t3**2  # 减速距离

        # 匀速阶段：总距离 - 加速距离 - 减速距离
        s2 = S - s1 - s3

        if s2 < 0:
            total_v_sq = a * S
            v_peak = np.sqrt(total_v_sq)  # 三角加速的速度峰值
            t1 = v_peak / a  # 加速时间 = 减速时间
            t3 = t1
            s1 = 0.5 * a * t1**2
            s3 = s1
            s2 = 0  # 无匀速阶段
            v_max = v_peak  # 更新实际峰值速度
        
        t2 = s2 / v_max if v_max != 0 else 0  # 匀速时间
        total_time = t1 + t2 + t3  # 总运动时间

        t = np.linspace(0, total_time, round(total_time / dt))

        delta_move = []

        for ti in t:
            if ti <= t1:
                s = v0 * ti + 0.5 * a * ti**2
            elif ti <= t1 + t2:
                s = s1 + v_max * (ti - t1)
            else:
                delta_t = ti - (t1 + t2)
                s = s1 + s2 + v_max * delta_t - 0.5 * a * delta_t**2

            xy = start + dir * s

            def make_f(x,y):
                def f(dt):
                    self.focus.local.x = x
                    self.focus.local.y = y
                    self.laser.geometry.positions.data[1] = self.focus.local.position
                    self.laser.geometry.positions.update_full()
                return f
                
            delta_move.append(make_f(xy[0]/1000,xy[1]/1000))
        self.steps[0:0] = delta_move
        
    def is_connected(self): return True