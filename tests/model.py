import trimesh
import numpy as np
import math as m

def model2depth(model_path:str, image_size:tuple=(512,512)):
    # 载入stl文件
    mesh = trimesh.load(model_path)

    # 求出mesh的包围盒
    bounds = mesh.bounds
    x_min, y_min, z_min = bounds[0]
    x_max, y_max, z_max = bounds[1]

    # 第三步：计算包围盒中心（核心！替代centroid）
    aabb_center = np.array([
        (x_min + x_max) / 2,  # X轴中心
        (y_min + y_max) / 2,  # Y轴中心（解决之前不准确的问题）
        (z_min + z_max) / 2   # Z轴中心
    ])

    # 打印mesh信息
    mesh = mesh.apply_translation(-aabb_center)

    # 计算模型在各轴上的最大跨度
    model_extent = np.max(np.ptp(mesh.vertices, axis=0))  # 模型在各轴上的最大跨度

    ortho_left = -model_extent / 2
    ortho_right = model_extent / 2
    ortho_bottom = -model_extent / 2
    ortho_top = model_extent / 2 
    ortho_near = mesh.bounds[1][2]  # 近裁剪面
    ortho_far = mesh.bounds[0][2]  # 远裁剪面

    # 图像尺寸（像素）
    width, height = image_size

    # 创建像素网格
    x_pixel = np.linspace(0, width-1, width)
    y_pixel = np.linspace(0, height-1, height)
    px, py = np.meshgrid(x_pixel, y_pixel)

    # 像素坐标转换为标准化设备坐标 (NDC: [-1,1])
    ndc_x = (px / (width-1)) * 2 - 1
    ndc_y = -((py / (height-1)) * 2 - 1)  # 翻转y轴，匹配图像坐标系

    # 正交投影逆变换：将NDC坐标转换回世界坐标

    world_x = ndc_x * (ortho_right - ortho_left) / 2 + (ortho_right + ortho_left) / 2
    world_y = ndc_y * (ortho_top - ortho_bottom) / 2 + (ortho_top + ortho_bottom) / 2

    # 3. 定义射线起点和方向（正交相机，所有射线平行于Z轴）
    # 射线起点（近裁剪面）
    ray_origins = np.column_stack([
        world_x.ravel(), 
        world_y.ravel(), 
        np.full(width*height, ortho_near)  # 近裁剪面位置（Z轴负方向）
    ])

    # 射线方向（正交投影，所有射线沿Z轴正方向）
    ray_directions = np.tile([0, 0, -1], (width*height, 1))

    locations, index_ray, index_tri = mesh.ray.intersects_location(
        ray_origins=ray_origins,
        ray_directions=ray_directions,
        multiple_hits=False  # 只取第一个交点（最近的）
    )

    # 5. 计算深度值并填充深度图像
    depth_image = np.full(image_size, 0, dtype=np.float32)  # 初始化为无穷远
    depth_mask = np.zeros(image_size, dtype=bool)

    # 遍历所有交点
    for i, loc in enumerate(locations):
        # 获取对应的射线索引
        ray_idx = index_ray[i]
        
        # 将射线索引转换为像素坐标
        pixel_y = ray_idx // width
        pixel_x = ray_idx % width
        
        # 计算深度（Z轴坐标的绝对值，或到近裁剪面的距离）
        depth = (loc[2] - ortho_far) / (ortho_near - ortho_far)
        depth_image[pixel_y, pixel_x] = depth
        depth_mask[pixel_y, pixel_x] = True

    # 归一化深度图像到[0,255]范围
    depth_image = (depth_image * 255).astype(np.uint8)
    return depth_image

#保存位png，用PIL
from PIL import Image

# 显示深度图像
Image.fromarray(model2depth("C:/Users/SLTru/Desktop/测试模型/内雕/龙凤仿古古典圆形浮雕.STL")).save('res/x.png')

def model2path(model_path:str):
    # 载入stl文件
    mesh = trimesh.load(model_path)

    # 求出mesh的包围盒
    bounds = mesh.bounds
    x_min, y_min, z_min = bounds[0]
    x_max, y_max, z_max = bounds[1]

    # 第三步：计算包围盒中心
    aabb_center = np.array([
        (x_min + x_max) / 2,  # X轴中心
        (y_min + y_max) / 2,  # Y轴中心（解决之前不准确的问题）
        (z_min + z_max) / 2   # Z轴中心
    ])

    # 打印mesh信息
    mesh = mesh.apply_translation(-aabb_center)

    # 计算模型在各轴上的最大跨度
    model_extent = np.max(np.ptp(mesh.vertices, axis=0))  # 模型在各轴上的最大跨度

    ortho_left = -model_extent / 2
    ortho_right = model_extent / 2
    ortho_bottom = -model_extent / 2
    ortho_top = model_extent / 2 
    ortho_near = mesh.bounds[1][2]  # 近裁剪面
    ortho_far = mesh.bounds[0][2]  # 远裁剪面

    plane_origin = [0, 0, 0]          # 平面上的任意一点（如Z=5的原点）
    plane_normal = [0, 0, 1]          # 平面法向量（[0,0,1]表示垂直Z轴的水平面）

    # 生成一个svg字符串，svg标签，内部包含path标签
    svg_str = """<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100" viewBox="{} {} {} {}">""".format(ortho_left, ortho_bottom, ortho_right-ortho_left, ortho_top-ortho_bottom)

    # 从mesh z轴最低向z轴最高的地方，进行z轴方向的切片
    pass_depth = 0.1
    for z in np.linspace(ortho_far, ortho_near, int((ortho_near-ortho_far)/pass_depth)):
        plane_origin[2] = z

        # 用一个平面 与 mesh 的所有三角面 求交线
        # trimesh求交核心函数：mesh.section()
        # 返回值：(交线轮廓列表, 相交三角面列表)
        from trimesh.path import Path3D
        sections : Path3D = mesh.section(
            plane_origin=plane_origin,    # 平面上的点
            plane_normal=plane_normal,    # 平面法向量
        )

        if not sections: continue
        
        # 将所有的线绘制成svg
        line = sections.to_dict()
        vertices = line['vertices']
            
        # 遍历所有的线，将其转换为svg的path标签
        for entity in line['entities']:
            if entity['type'] != 'Line': continue
            closed = entity['closed']
            indexes = entity['points']

            # 从indexes中，取出对应的vertices
            path_str = "M {} {}".format(*vertices[indexes[0]])
            for i in indexes[1:]:
                path_str += " L {} {}".format(*vertices[i])
            if closed:
                path_str += " Z"
            
            svg_str += """<path pass_depth="{}" stroke="red" stroke-width="0.01" fill="none" d="{}" />
            """.format(pass_depth, path_str)
    svg_str += """</svg>"""

    # 保存svg文件
    with open(f"test.svg", "w") as f:
        f.write(svg_str)


# model2path("C:/Users/SLTru/Desktop/测试模型/内雕/a.STL")