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
        self.params['excutable'] = True
        self.params['engraving_mode'] = 'stroke'
        self.params['light_source'] = 'blue'
        self.params['power'] = 30
        self.params['speed'] = 300
        self.params['pixelsize'] = 1
        
        self.obj = None
    def set_excutable(self,state):
        self.params['excutable'] = state

    def set_engraving_mode(self,mode):
        self.params['engraving_mode'] = mode

    def set_light_source(self,source):
        self.params['light_source'] = source

    def set_power(self,power):
        self.params['power'] = power

    def set_speed(self,speed):
        self.params['speed'] = speed

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

class Label(Element):
    def __init__(self,text,font_size,family,*args,**kwargs):
        super().__init__(*args,**kwargs)
        
        self.font_size = font_size
        self.family = family
        
        self.set_text(text)

    def draw_to_surface(self,cr:cairo.Context):
        cr.save()
        if self.params['light_source'] == 'red': cr.set_source_rgb(1, 0, 0)
        else: cr.set_source_rgb(0, 0, 1)

        # 5. 配置字体（与临时上下文一致，确保尺寸匹配）
        cr.select_font_face(self.family, cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
        cr.set_font_size(self.font_size)

        # 7. 绘制文字（黑色，可修改RGB值换颜色）
        cr.move_to(-self.text_info.x_bearing, -self.text_info.y_bearing)
        cr.text_path(self.text)

        if self.params['engraving_mode'] == 'fill': cr.fill()
        else: cr.stroke()
        cr.restore()
    
    def draw_to_image(self):
        temp_surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, 1, 1)  # 临时1x1像素表面
        temp_ctx = cairo.Context(temp_surface)
        
        # 配置与最终绘制一致的字体
        temp_ctx.select_font_face(self.family, cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
        temp_ctx.set_font_size(self.font_size)
        
        # 获取文字的详细边界信息（核心参数）
        self.text_info = temp_ctx.text_extents(self.text)
        text_width = self.text_info.width          # 文字左边缘到右边缘的实际宽度（无多余）
        text_height = self.text_info.height        # 文字上边缘到下边缘的实际高度（含上下伸部分）

        # 2. 图片尺寸=文字实际尺寸（零留白关键）
        img_width = int(text_width)
        img_height = int(text_height)

        surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, img_width, img_height)
        self.draw_to_surface(cairo.Context(surface))

        return surface

    def draw_to_svg(self,cr : cairo.Context):
        cr.save()
        cr.translate(self.local.x * 1000,-self.local.y * 1000)
        cr.rotate(-self.local.euler_z)
        cr.scale(self.local.scale_x,self.local.scale_y)

        if self.params['light_source'] == 'red': cr.set_source_rgb(1, 0, 0)
        else: cr.set_source_rgb(0, 0, 1)

        if self.params['engraving_mode'] == 'fill': 
            surface = self.draw_to_image()
            cr.set_source_surface(surface, -surface.get_width() / 2, -surface.get_height() / 2)
            cr.paint()
        else: 
            cr.select_font_face(self.family, cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
            cr.set_font_size(self.font_size)
            text_extents = cr.text_extents(self.text)
            cr.move_to(-text_extents.x_bearing - text_extents.width / 2,-text_extents.y_bearing - text_extents.height / 2)
            cr.text_path(self.text)
            cr.stroke()
        cr.restore()

    def set_text(self,text):
        self.text = text
        
        surface = self.draw_to_image()
        im = np.frombuffer(surface.get_data(), dtype=np.uint8).reshape((surface.get_height(),surface.get_width(), 4))
        tex = gfx.Texture(im[...,[2,1,0,3]],dim=2)
        tex_map = gfx.TextureMap(tex)
        
        self.remove(self.obj)
        self.obj = gfx.Mesh(gfx.plane_geometry(surface.get_width() / 1000,surface.get_height() / 1000),gfx.MeshBasicMaterial(map=tex_map,depth_test=False))
        self.add(self.obj)

    def set_engraving_mode(self,mode : str):
        self.params['engraving_mode'] = mode
        self.set_text(self.text)

class Bitmap(Element):
    def __init__(self,filepath,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.params['engraving_mode'] = 'fill'

        self.filepath = filepath
        im = Image.open(filepath)
        im = im.convert('RGBA')
        self.im = im
        
        tex = gfx.Texture(np.asarray(im),dim=2)
        tex_map = gfx.TextureMap(tex,filter='nearest')
        self.obj = gfx.Mesh(gfx.plane_geometry(im.size[0] / 1000,im.size[1] / 1000),gfx.MeshBasicMaterial(map=tex_map,depth_test=False))
        self.add(self.obj)
 
        self.draw_to_image()
    
    def set_engraving_mode(self,mode : str):
        self.params['engraving_mode'] = mode

        if mode == 'fill':
            self.remove(self.obj)
            im = Image.open(self.filepath)
            im = im.convert('RGBA')
            self.im = im
            
            tex = gfx.Texture(np.asarray(im),dim=2)
            tex_map = gfx.TextureMap(tex,filter='nearest')
            self.obj = gfx.Mesh(gfx.plane_geometry(im.size[0] / 1000,im.size[1] / 1000),gfx.MeshBasicMaterial(map=tex_map,depth_test=False))
            self.add(self.obj)
        elif mode == 'threed':
            # self.obj.material = gfx.MeshBasicMaterial(map=tex_map,depth_test=False)
            pass

    def get_image(self):
        return self.im.astype(np.uint8)
    
    def draw_to_surface(self,surface : cairo.Surface):
        pixel_width,pixel_height = self.im.size

        ctx = cairo.Context(surface)
        stride = cairo.ImageSurface.format_stride_for_width(cairo.FORMAT_ARGB32, pixel_width)
        surface_im = cairo.ImageSurface.create_for_data(np.asarray(self.im)[...,[2,1,0,3]].copy().data, cairo.FORMAT_ARGB32, pixel_width, pixel_height, stride)
        ctx.set_source_surface(surface_im, 0, 0)
        ctx.paint()

    def draw_to_image(self):
        pixel_width,pixel_height = self.im.size
        surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, pixel_width, pixel_height)
        self.draw_to_surface(surface)
        return surface
    
    def draw_to_svg(self,cr : cairo.Context):
        cr.save()

        pixel_width,pixel_height = self.im.size
        cr.translate(self.local.x * 1000,-self.local.y * 1000)
        cr.rotate(-self.local.euler_z)
        cr.scale(self.local.scale_x,self.local.scale_y)

        
        if self.params['engraving_mode'] == 'fill':
            stride = cairo.ImageSurface.format_stride_for_width(cairo.FORMAT_ARGB32, pixel_width)
            surface = cairo.ImageSurface.create_for_data(np.asarray(self.im)[...,[2,1,0,3]].copy().data, cairo.FORMAT_ARGB32, pixel_width, pixel_height, stride)
            cr.set_source_surface(surface, -pixel_width / 2, -pixel_height / 2)
            cr.paint()
        else:
            gray = np.asarray(self.im.convert('L'))
            
            for i in range(255):
                mask = (gray < i+1)
                im = np.full_like(gray,0)
                im[mask] = 255
                im = Image.fromarray(im,'L').convert('RGBA')

                stride = cairo.ImageSurface.format_stride_for_width(cairo.FORMAT_ARGB32, pixel_width)
                surface = cairo.ImageSurface.create_for_data(np.asanyarray(im).copy().data, cairo.FORMAT_ARGB32, pixel_width, pixel_height, stride)
                cr.set_source_surface(surface, -pixel_width / 2, -pixel_height / 2)
                cr.paint()
        
        cr.restore()
        pass
    
class Vectors(Element):
    def __init__(self,lines,*args,**kwargs):
        super().__init__(*args,**kwargs)
        points = np.concatenate(lines,axis=0)
        min_x = points[:,0].min()
        min_y = points[:,1].min()
        max_x = points[:,0].max()
        max_y = points[:,1].max()
        self.phy_width = (max_x - min_x)
        self.phy_height = (max_y - min_y)

        self.obj = gfx.Mesh(gfx.plane_geometry(self.phy_width,self.phy_height))
        self.lines = []
        for line in lines:
            line = gfx.Line(gfx.Geometry(positions=line.astype(np.float32)),gfx.LineMaterial(thickness=1,color=self.params['light_source'],depth_test=False))
            self.lines.append(line)
            self.obj.add(line)
        self.add(self.obj)

    def draw_to_surface(self,surface : cairo.Surface):
        cr = cairo.Context(surface)
        if self.params['light_source'] == 'red': cr.set_source_rgb(1, 0, 0)
        else: cr.set_source_rgb(0, 0, 1)
        
        cr.translate(surface.get_width()/2,surface.get_height()/2)
        for line in self.lines:
            start = line.geometry.positions.data[0]
            start = start * 1000 
            cr.move_to(start[0],-start[1])
            for end in line.geometry.positions.data[1:]:
                end = end * 1000 
                cr.line_to(end[0],-end[1])
            cr.close_path()

            if self.params['engraving_mode'] == 'fill': cr.fill()
            else: cr.stroke()

    def draw_to_image(self) -> cairo.ImageSurface:
        phy_width = int(self.phy_width * 1000)
        phy_height = int(self.phy_height * 1000)
        img_width = int(phy_width)
        img_height = int(phy_height)
        surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, img_width, img_height)
        self.draw_to_surface(surface)
        return surface
    
    def draw_to_svg(self,cr : cairo.Context):
        cr.save()

        cr.translate(self.local.x * 1000,-self.local.y * 1000)
        cr.rotate(-self.local.euler_z)
        if self.params['light_source'] == 'red': cr.set_source_rgb(1, 0, 0)
        else: cr.set_source_rgb(0, 0, 1)

        if self.params['engraving_mode'] == 'fill': 
            surface = self.draw_to_image()
            cr.scale(self.local.scale_x,self.local.scale_y)
            cr.set_source_surface(surface, -surface.get_width() / 2, -surface.get_height() / 2)
            cr.paint()
        else:            
            for line in self.lines:
                start = line.geometry.positions.data[0]
                start = start * self.local.scale[:1]
                cr.move_to(start[0] * 1000,-start[1] * 1000)
                for end in line.geometry.positions.data[1:]:
                    end = end * self.local.scale[:1]
                    cr.line_to(end[0] * 1000,-end[1] * 1000)
                cr.close_path()
            cr.stroke()  
        cr.restore()

    def set_engraving_mode(self,mode : str):
        self.params['engraving_mode'] = mode
        self.remove(self.obj)
        if mode == 'fill':
            surface = self.draw_to_image()
            argb = np.frombuffer(surface.get_data(), dtype=np.uint8).reshape((surface.get_height(),surface.get_width(), 4))
            tex = gfx.Texture(argb[...,[2,1,0,3]],dim=2)
            tex_map = gfx.TextureMap(tex)
            self.obj = gfx.Mesh(gfx.plane_geometry(self.phy_width,self.phy_height),gfx.MeshBasicMaterial(map=tex_map,depth_test=False))
        elif mode == 'stroke':
            self.obj = gfx.Mesh(gfx.plane_geometry(self.phy_width,self.phy_height))
            for line in self.lines:
                self.obj.add(line)

        self.add(self.obj)

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
        
        self.focus = gfx.Mesh(gfx.sphere_geometry(radius=self.lightspotsize /1000 ),gfx.MeshBasicMaterial(color=(1, 0, 0, 1),depth_test=False,flat_shading=True))
        self.focus.render_order = 1
        self.target_area.add(self.focus)

        self.laser = gfx.Line(gfx.Geometry(positions=[self.laser_aperture.local.position,self.focus.local.position]),gfx.LineMaterial(thickness=self.lightspotsize/1000,thickness_space='world',color=(1, 0, 0, 0)))
        self.laser.render_order = 1
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
        self.lightspotsize = 0.1
        self.paths = list()
        self.speed = 100
        self.power = 0

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
    
    def get_items(self):
        items = []
        for obj in self.target_area.children:
            if Element not in obj.__class__.__mro__:
                continue
            items.append(obj)
        return items

    def add_label(self):
        aabb = self.target.get_geometry_bounding_box()
        target_height = (aabb[1][2] - aabb[0][2])
        
        element = Label('中国智造',72,'KaiTi',name='文本')
        element.local.scale = self.lightspotsize
        element.local.z = target_height
        self.target_area.add(element)

    def add_bitmap(self,filepath):
        target = self.target
        aabb = target.get_geometry_bounding_box()
        target_height = (aabb[1][2] - aabb[0][2])
        element = Bitmap(filepath,name='图片')
        element.local.scale = self.lightspotsize

        element.local.z = target_height
        self.target_area.add(element)

    def add_vectors(self,lines):
        target = self.target
        aabb = target.get_geometry_bounding_box()
        target_height = (aabb[1][2] - aabb[0][2])

        points = np.concatenate(lines,axis=0)
        min_x = points[:,0].min()
        min_y = points[:,1].min()
        max_x = points[:,0].max()
        max_y = points[:,1].max()
        phy_width = (max_x - min_x)
        phy_height = (max_y - min_y)
        scale = min(self.x_lim[1] / (phy_width),self.y_lim[1] / (phy_height))

        vectors = []
        for line in lines:
            line = np.array(line)[:,[0,1]]
            line = (line - [min_x + phy_width/2,min_y + phy_height/2]) * scale / self.lightspotsize
            line = np.hstack((line, np.zeros((line.shape[0], 1), dtype=line.dtype)))
            vectors.append(line)
        
        element = Vectors(vectors,name='矢量')
        element.local.scale = self.lightspotsize
        element.local.z = target_height
        self.target_area.add(element)

    def count_elements(self):
        i = 0
        for obj in self.target_area.children:
            if Element not in obj.__class__.__mro__: continue
            obj : Label | Bitmap | Vectors
            if not obj.params['excutable']: continue
            i+=1
        return i

    def hide_all_elements(self):
        for obj in self.target_area.children:
            if Element not in obj.__class__.__mro__: continue
            obj : Label | Bitmap | Vectors
            obj.visible = False

    def show_all_elements(self):
        for obj in self.target_area.children:
            if Element not in obj.__class__.__mro__: continue
            obj : Label | Bitmap | Vectors
            obj.visible = True

    def export_svg(self):
        from io import BytesIO
        import cairo    
        svgs = []

        width = int((self.x_lim[1] - self.x_lim[0]) * 1000)
        height = int((self.y_lim[1] - self.y_lim[0]) * 1000)
        for obj in self.target_area.children:
            if Element not in obj.__class__.__mro__: continue
            obj : Label | Bitmap | Vectors
            if not obj.params['excutable']: continue

            svg = BytesIO()
            with cairo.SVGSurface(svg, width, height) as surface:
                cr = cairo.Context(surface)
                cr.set_line_width(self.lightspotsize)
                cr.translate(width / 2,height / 2)
                obj.draw_to_svg(cr)
        
            obj.params['pixelsize'] = 1 / (obj.local.scale_x / self.lightspotsize)
            svgs.append((svg,width,height,obj.params))
        return svgs
    
    def excute(self,gcode : str):
        def excute_next(lines : list[str]):
            while lines:
                line = lines.pop(0).strip()
                if not line or line.startswith(';'): 
                    continue

                # print(line)
                moveable = False
                x,y = self.focus.local.position[:2] * 1000
                power = self.power
                speed = self.speed
                command = line.split(' ')
                for param in command:
                    if param.startswith('G0'):
                        moveable = True
                        x = 0
                        y = 0
                        power = 0
                    elif param == 'G1': 
                        moveable = True
                    elif param.startswith('X'):
                        x = float(param[1:])
                        moveable = True
                    elif param.startswith('Y'):
                        y = float(param[1:])
                        moveable = True
                    elif param.startswith('F'):
                        self.speed = speed = float(param[1:])
                    elif param.startswith('S'):
                        self.power = power = float(param[1:])
                        self.laser.material.color = (1,0,0,power / 100)
                    elif param == 'M2':
                        self.laser.material.color = (1,0,0,0)
                        continue
                    elif param == 'M3':
                        self.laser.material.color = (1,0,0,power / 100)
                        continue
                    elif param == 'M5':
                        self.laser.material.color = (1,0,0,0)
                        continue
                    else:
                        pass


                if moveable: self.steps.append(lambda dt: self.move(x,y,speed,power,dt))
                break
            
            if lines: self.steps.append(lambda dt: excute_next(lines))
                
        excute_next(gcode.split('\n'))

    def move(self,x,y,speed,power,dt):
        def make_delta_move(x,y,power):
            def delta_move(dt):
                self.focus.local.x = x / 1000
                self.focus.local.y = y / 1000
                self.laser.material.color = (1,0,0,power / 100)
                self.laser.geometry.positions.data[1] = self.focus.local.position
                self.laser.geometry.positions.update_full()
            return delta_move

        start = self.focus.local.position[:2] * 1000
        end = np.array([x,y])
        dir = end - start
        S = np.linalg.norm(dir)

        if True and S > 0: 
            dir /= S
            v_max=speed; v0=0; v1=0; a=speed
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

            for i,ti in enumerate(t):
                if ti <= t1:
                    s = v0 * ti + 0.5 * a * ti**2
                elif ti <= t1 + t2:
                    s = s1 + v_max * (ti - t1)
                else:
                    delta_t = ti - (t1 + t2)
                    s = s1 + s2 + v_max * delta_t - 0.5 * a * delta_t**2

                xy = start + dir * s

                self.steps.insert(i,make_delta_move(xy[0],xy[1],power))
        else:
            self.steps.insert(0,make_delta_move(x,y,power))

    def is_connected(self): return True