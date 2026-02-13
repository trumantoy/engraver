import trimesh
import numpy as np
from PIL import Image
from scipy.spatial.transform import Rotation as R

def process_3d_model(model_path, output_depth_npy="mesh_depth.npy", output_gray_png="mesh_depth_gray.png",
                     image_size=(512, 512), camera_scale=2.0):
    """
    实现3D模型加载、正交投影、面片着色插值、深度值保存与灰度图生成
    :param model_path: 3D模型路径（.obj/.stl）
    :param output_depth_npy: 深度值保存的npy文件路径
    :param output_gray_png: 灰度图输出路径
    :param image_size: 输出图像尺寸 (宽, 高)
    :param camera_scale: 相机视野缩放系数，适配模型大小
    """
    # 步骤1：加载OBJ/STL 3D模型文件
    print(f"正在加载模型：{model_path}")
    mesh = trimesh.load(model_path)
    if not isinstance(mesh, trimesh.Trimesh):
        raise ValueError("加载的模型不是单个Trimesh对象，请确保输入文件是单个3D模型")
    print(f"模型加载成功：包含 {len(mesh.faces)} 个面片，{len(mesh.vertices)} 个顶点")

    # 步骤2：构建正交相机并执行模型投影
    # 2.1 模型中心化（便于投影对齐）
    mesh_centroid = mesh.centroid
    vertices_centered = mesh.vertices - mesh_centroid  # 顶点中心化，消除模型偏移

    # 2.2 定义正交相机参数（正交投影无透视变形，视线沿Z轴负方向）
    # 正交相机视野：左右/上下范围由模型尺寸和缩放系数决定
    model_extent = np.max(np.ptp(vertices_centered, axis=0))  # 模型在各轴上的最大跨度
    ortho_left = -model_extent * camera_scale / 2
    ortho_right = model_extent * camera_scale / 2
    ortho_bottom = -model_extent * camera_scale / 2
    ortho_top = model_extent * camera_scale / 2
    ortho_near = 0.1  # 近裁剪面
    ortho_far = model_extent * camera_scale  # 远裁剪面

    # 2.3 执行正交投影（将3D顶点投影到2D图像平面）
    # 正交投影矩阵（将3D顶点转换到[-1,1]标准化设备坐标）
    ortho_matrix = np.array([
        [2 / (ortho_right - ortho_left), 0, 0, -(ortho_right + ortho_left) / (ortho_right - ortho_left)],
        [0, 2 / (ortho_top - ortho_bottom), 0, -(ortho_top + ortho_bottom) / (ortho_top - ortho_bottom)],
        [0, 0, -2 / (ortho_far - ortho_near), -(ortho_far + ortho_near) / (ortho_far - ortho_near)],
        [0, 0, 0, 1]
    ])

    # 给顶点添加齐次坐标（N,3）->（N,4）
    vertices_homogeneous = np.hstack([vertices_centered, np.ones((len(vertices_centered), 1))])
    # 执行正交投影变换
    vertices_projected_hom = np.dot(ortho_matrix, vertices_homogeneous.T).T
    # 转换为2D图像坐标（标准化设备坐标->像素坐标）
    vertices_2d = np.zeros_like(vertices_projected_hom[:, :2])
    vertices_2d[:, 0] = (vertices_projected_hom[:, 0] + 1) * 0.5 * image_size[0]  # x轴映射到图像宽度
    vertices_2d[:, 1] = (1 - (vertices_projected_hom[:, 1] + 1) * 0.5) * image_size[1]  # y轴映射到图像高度（翻转y轴，符合图像坐标系）

    # 步骤3：对投影下面片进行着色插值（基于顶点深度的双线性/重心坐标插值）
    # 3.1 提取每个顶点的深度值（Z轴坐标，已通过正交投影归一化）
    vertex_depths = vertices_projected_hom[:, 2]  # 投影后的Z坐标即为深度值（越接近far，深度越大）
    # 3.2 初始化深度图像（存储每个像素的插值后深度）
    depth_image = np.zeros(image_size, dtype=np.float32)
    depth_mask = np.zeros(image_size, dtype=bool)  # 标记有效像素区域

    print("正在对面片进行深度插值计算...")
    for face_idx, face in enumerate(mesh.faces):
        # 提取当前面片的3个顶点及其2D坐标、深度值
        face_vertices_2d = vertices_2d[face]  # (3,2)
        face_depths = vertex_depths[face]  # (3,)

        # 计算面片包围盒（减少插值计算范围）
        x_min, x_max = int(np.floor(np.min(face_vertices_2d[:, 0]))), int(np.ceil(np.max(face_vertices_2d[:, 0])))
        y_min, y_max = int(np.floor(np.min(face_vertices_2d[:, 1]))), int(np.ceil(np.max(face_vertices_2d[:, 1])))
        # 裁剪包围盒到图像范围内
        x_min, x_max = max(0, x_min), min(image_size[0]-1, x_max)
        y_min, y_max = max(0, y_min), min(image_size[1]-1, y_max)

        if x_min >= x_max or y_min >= y_max:
            continue  # 跳过无效面片

        # 生成包围盒内的像素网格
        y_grid, x_grid = np.meshgrid(np.arange(y_min, y_max+1), np.arange(x_min, x_max+1), indexing='ij')
        pixels = np.hstack([x_grid.reshape(-1, 1), y_grid.reshape(-1, 1)])  # (N,2)

        # 重心坐标插值：判断像素是否在面片内，并计算插值深度
        for pixel in pixels:
            px, py = pixel
            # 计算重心坐标（基于三角形面片的面积比）
            v0 = face_vertices_2d[1] - face_vertices_2d[0]
            v1 = face_vertices_2d[2] - face_vertices_2d[0]
            v2 = np.array([px, py]) - face_vertices_2d[0]

            dot00 = np.dot(v0, v0)
            dot01 = np.dot(v0, v1)
            dot02 = np.dot(v0, v2)
            dot11 = np.dot(v1, v1)
            dot12 = np.dot(v1, v2)

            denom = dot00 * dot11 - dot01 * dot01
            if denom == 0:
                continue  # 退化三角形，跳过

            u = (dot11 * dot02 - dot01 * dot12) / denom
            v = (dot00 * dot12 - dot01 * dot02) / denom

            # 像素在三角形内的条件：u>=0, v>=0, u+v<=1
            if u >= 0 and v >= 0 and (u + v) <= 1:
                # 重心坐标插值计算深度值
                interpolated_depth = (1 - u - v) * face_depths[0] + u * face_depths[1] + v * face_depths[2]
                # 更新深度图像（保留最接近相机的深度值，即最小深度值）
                if not depth_mask[int(py), int(px)] or interpolated_depth < depth_image[int(py), int(px)]:
                    depth_image[int(py), int(px)] = interpolated_depth
                    depth_mask[int(py), int(px)] = True

    # 步骤4：保存每个面片/像素的深度值（两种格式：npy数组存储完整深度图像，面片深度汇总）
    # 4.1 保存完整深度图像数组（像素级深度）
    np.save(output_depth_npy, depth_image)
    # 4.2 保存面片级深度汇总（每个面片的平均深度）
    face_depths_avg = np.array([np.mean(vertex_depths[face]) for face in mesh.faces])
    np.save("mesh_face_avg_depth.npy", face_depths_avg)
    print(f"深度值已保存：\n  - 像素级深度：{output_depth_npy}\n  - 面片平均深度：mesh_face_avg_depth.npy")

    # 步骤5：将深度值转换并写入灰度图
    # 5.1 归一化深度值到[0, 255]灰度范围（仅处理有效像素区域）
    valid_depths = depth_image[depth_mask]
    if len(valid_depths) == 0:
        raise ValueError("未计算到有效深度值，模型可能超出相机视野，请调整camera_scale参数")
    
    depth_min, depth_max = np.min(valid_depths), np.max(valid_depths)
    # 归一化（避免除以零）
    normalized_depth = np.zeros_like(depth_image, dtype=np.uint8)
    normalized_depth[depth_mask] = ((depth_image[depth_mask] - depth_min) / (depth_max - depth_min + 1e-8) * 255).astype(np.uint8)
    # 反转灰度值（可选：使深度越大越亮，符合视觉习惯）
    normalized_depth[depth_mask] = 255 - normalized_depth[depth_mask]

    # 5.2 转换为PIL图像并保存
    gray_image = Image.fromarray(normalized_depth)
    gray_image.save(output_gray_png)
    print(f"灰度图已保存：{output_gray_png}")

    return depth_image, normalized_depth, gray_image

# 示例调用
if __name__ == "__main__":
    # 替换为你的OBJ/STL模型路径
    MODEL_PATH = "C:\\Users\\SLTru\\Desktop\\测试模型\\内雕\\金毛.OBJ"  # 支持 "your_model.stl"

    # 执行处理流程
    process_3d_model(
        model_path=MODEL_PATH,
        output_depth_npy="model_depth.npy",
        output_gray_png="model_depth_gray.png",
        image_size=(128, 128),
        camera_scale=2.0
    )