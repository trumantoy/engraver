import trimesh
import numpy as np
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
from sklearn.cluster import KMeans
from skimage import color  # 内置RGB转Lab函数

def barycentric_by_distance(A, B, C, P):
    """
    纯距离法求重心权重
    A,B,C,P 都是 np.array([x,y,z])
    返回 (wA, wB, wC)，和为1
    """
    # 计算距离
    dA = np.linalg.norm(P - A)
    dB = np.linalg.norm(P - B)
    dC = np.linalg.norm(P - C)
    
    # 倒数距离（避免除以0）
    eps = 1e-9
    invA = 1.0 / (dA + eps)
    invB = 1.0 / (dB + eps)
    invC = 1.0 / (dC + eps)
    
    # 归一化得到权重
    total = invA + invB + invC
    wA = invA / total
    wB = invB / total
    wC = invC / total
    
    return wA, wB, wC

def interpolate_color(A, B, C, colorA, colorB, colorC, P):
    wA, wB, wC = barycentric_by_distance(A, B, C, P)

    color = wA * colorA + wB * colorB + wC * colorC
    return np.clip(color / 255, 0, 1)

def rgb_to_hsv_single(rgb):
    """
    将单个 RGB 颜色转换为 HSV 颜色空间
    :param rgb: 输入 RGB 颜色，列表/元组形式，值范围 [0, 255] 或 [0, 1]
    :return: HSV 颜色，元组形式，H ∈ [0, 360), S/V ∈ [0, 1]
    """
    r,g,b = rgb
    # 2. 计算最大值、最小值和差值
    max_rgb = max(r, g, b)
    min_rgb = min(r, g, b)
    delta = max_rgb - min_rgb

    # 3. 计算 V (明度)
    v = max_rgb

    # 4. 计算 S (饱和度)
    s = 0.0 if max_rgb == 0 else delta / max_rgb

    # 5. 计算 H (色相)    h = 0.0  # 灰度情况默认 H=0
    if delta > 0:
        if max_rgb == r:
            h = 60 * ((g - b) / delta)
        elif max_rgb == g:
            h = 60 * ((b - r) / delta) + 120
        elif max_rgb == b:
            h = 60 * ((r - g) / delta) + 240
        # 处理 H 为负数的情况，映射到 [0, 360)
        h = h % 360

    return (h / 360, s, v)

def get_voxel_color_from_texture(mesh : trimesh.Trimesh, voxel_points):
    # 1. 找到体素点最近的三角面（索引、重心坐标）
    _,_,face_idx  = mesh.nearest.on_surface(voxel_points)

    # 2. 该面的三个顶点 UV
    face = mesh.faces[face_idx]
    vertices = mesh.vertices[face]
    vertex_colors = mesh.visual.to_color().vertex_colors[face]

    points = []
    for i in range(len(voxel_points)):
        p = np.array(voxel_points[i])
        v = vertices[i]
        c = vertex_colors[i]
        rgba = np.array(interpolate_color(v[0], v[1], v[2], c[0], c[1], c[2], p))
        p = np.concatenate((p, rgba[:3]))
        points.append(p)
    
    points = np.stack(points, axis=0)
    return points

# 高斯函数：sigma 越小 → 峰值越窄越尖
def gaussian(x, mu=0, sigma=0.15):  # 这里改小 sigma！
    return np.exp(-((x - mu) ** 2) / (2 * sigma ** 2))

# 2. 降采样函数：越亮越密，越暗越疏
def downsample(points, percent=0.5):
    n_total = len(points)
    n_keep = int(n_total * percent)  # 要保留的数量
    # 随机选择 n_keep 个索引（不重复）
    keep_indices = np.random.choice(n_total, size=n_keep, replace=False)
    
    # 返回保留的点
    return points[keep_indices]

# ===================== 1. 加载3D模型 =====================
# 支持格式：STL / OBJ / GLB / PLY / 3DS 等
mesh : trimesh.Trimesh = trimesh.load('C:/Users/SLTru/Desktop/测试模型/内雕/企鹅2.obj')  # 替换成你的模型路径
bounds0 = np.array(mesh.bounds[0])
mesh = mesh.apply_translation(-bounds0)
ux,uy,uz = np.ptp(mesh.vertices, axis=0)
mesh : trimesh.Trimesh = mesh.apply_scale([50 / ux,50 / uy,80 / uz])
# ===================== 2. 体素化（核心代码） =====================
# pitch：每个体素的大小（单位和模型一致），数值越小精度越高
pitch = 0.5  # 体素分辨率，根据模型大小调整
# 体素化：返回 VoxelGrid 对象
voxel_grid = mesh.voxelized(pitch=pitch)
# ===================== 3. 获取体素数据 =====================
# 1. 获取所有体素的 3D 坐标 (N, 3)
voxel_points = voxel_grid.points

# 剔除背部的点
voxel_points = get_voxel_color_from_texture(mesh, voxel_points)

xyz = voxel_points[:, :3]
xyz_min = xyz.min(axis=0)
xyz_max = xyz.max(axis=0)
xyz = (xyz - xyz_min) / (xyz_max - xyz_min)

# 得到背部的点
back_mask = xyz[:,1] > 0.5
front_mask = xyz[:,1] <= 0.5

# 得到背部的点距离0的距离
back_distances = xyz[back_mask][:,1]

# 根据距离得到灰度
back_grays = np.clip((back_distances - 0.5) * 2, 0, 1)

# 渐变函数
back_grays = gaussian(back_grays,0.15)

# 给背部的点添加黑色
back_points = voxel_points[back_mask]
back_points[:,3:] = back_points[:,3:] * np.repeat(back_grays, 3).reshape(-1,3)
voxel_points[back_mask] = back_points

front_points = voxel_points
pixels = front_points[:, 3:]

features = np.hstack([pixels])

# K-Means
optimal_layer_count = 5
db = KMeans(n_clusters=optimal_layer_count, random_state=42)
labels = db.fit_predict(features)
cluster_centers = db.cluster_centers_
grays = color.rgb2gray(cluster_centers)
grays = np.round(grays / np.max(grays), 1)
grays[grays < 0.25] = 0.1

clustered_points = {}  # 存放每个类别的点

for label in set(labels):
    mask = (labels == label)
    points = voxel_points[mask]
    gray = grays[label]
    clustered_points[gray] = points

fig = plt.figure(figsize=(10,8))
ax = fig.add_subplot(111, projection='3d')

for gray, points in clustered_points.items():
    points = downsample(points, gray)
    print(gray)
    ax.scatter(points[:,0], points[:,1], points[:,2], s=1, c=[0,0,0] * points[:,3:])

ax.set_aspect('equal')
plt.show()
