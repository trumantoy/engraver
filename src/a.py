import numpy as np
import matplotlib.pyplot as plt

# ========== 解决中文乱码核心配置 ==========
plt.rcParams['font.sans-serif'] = ['SimHei']  # 显示中文（Windows系统优先用这个）
# Mac系统替换为：['PingFang SC']；Linux系统替换为：['WenQuanYi Micro Hei']
plt.rcParams['axes.unicode_minus'] = False  # 解决负号显示为方块的问题

def trapezoidal_profile(S, v_max, v0=0, v1=0, a=2):
    """
    计算梯形加速曲线并绘图
    :param S: 总距离 (m)
    :param v_max: 目标匀速速度 (m/s)
    :param v0: 初速度 (m/s)，默认0
    :param v1: 末速度 (m/s)，默认0
    :param a: 加速度/减速度大小 (m/s²)，默认2（可根据需求调整）
    :return: 各阶段时间、距离等参数
    """
    # ========== 1. 计算各阶段核心参数 ==========
    # 加速阶段：从v0到v_max
    t1 = (v_max - v0) / a  # 加速时间
    s1 = v0 * t1 + 0.5 * a * t1**2  # 加速距离
    
    # 减速阶段：从v_max到v1
    t3 = (v_max - v1) / a  # 减速时间
    s3 = v_max * t3 - 0.5 * a * t3**2  # 减速距离
    
    # 匀速阶段：总距离 - 加速距离 - 减速距离
    s2 = S - s1 - s3
    if s2 < 0:
        # 若匀速距离为负，自动切换为三角加速（无匀速阶段）
        print(f"提示：加速度{a}过大，无法达到{v_max}m/s，自动切换为三角加速（无匀速阶段）")
        total_v_sq = 2 * a * S
        v_peak = np.sqrt(total_v_sq)  # 三角加速的速度峰值
        t1 = v_peak / a  # 加速时间 = 减速时间
        t3 = t1
        s1 = 0.5 * a * t1**2
        s3 = s1
        s2 = 0  # 无匀速阶段
        v_max = v_peak  # 更新实际峰值速度
    
    t2 = s2 / v_max if v_max != 0 else 0  # 匀速时间
    total_time = t1 + t2 + t3  # 总运动时间
    
    # ========== 2. 生成时间序列，计算各时刻的速度、加速度、位移 ==========
    t = np.linspace(0, total_time, 500)
    v = np.zeros_like(t)
    a_t = np.zeros_like(t)
    s = np.zeros_like(t)
    
    for i, ti in enumerate(t):
        if ti <= t1:
            # 加速阶段
            v[i] = v0 + a * ti
            a_t[i] = a
            s[i] = v0 * ti + 0.5 * a * ti**2
        elif ti <= t1 + t2:
            # 匀速阶段
            v[i] = v_max
            a_t[i] = 0
            s[i] = s1 + v_max * (ti - t1)
        else:
            # 减速阶段
            delta_t = ti - (t1 + t2)
            v[i] = v_max - a * delta_t
            a_t[i] = -a
            s[i] = s1 + s2 + v_max * delta_t - 0.5 * a * delta_t**2
    
    # ========== 3. 绘图 ==========
    fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(10, 8), sharex=True)
    
    # 子图1：速度-时间曲线（核心）
    ax1.plot(t, v, 'b-', linewidth=2, label=f'目标速度={v_max:.1f}m/s')
    ax1.axhline(y=v_max, color='r', linestyle='--', alpha=0.5, label='匀速段速度')
    ax1.fill_between(t, 0, v, alpha=0.2, color='blue')
    ax1.set_ylabel('速度 (m/s)', fontsize=12)
    ax1.set_title('梯形加速 - 速度-时间曲线', fontsize=14)
    ax1.grid(True, alpha=0.3)
    ax1.legend()
    
    # 子图2：加速度-时间曲线
    ax2.plot(t, a_t, 'g-', linewidth=2)
    ax2.axhline(y=a, color='orange', linestyle='--', alpha=0.5, label='加速段加速度')
    ax2.axhline(y=-a, color='purple', linestyle='--', alpha=0.5, label='减速段加速度')
    ax2.set_ylabel('加速度 (m/s²)', fontsize=12)
    ax2.set_title('加速度-时间曲线', fontsize=14)
    ax2.grid(True, alpha=0.3)
    ax2.legend()
    
    # 子图3：位移-时间曲线
    ax3.plot(t, s, 'orange', linewidth=2, label=f'总距离={S:.1f}m')
    ax3.axhline(y=S, color='green', linestyle='--', alpha=0.5, label='目标总距离')
    ax3.set_xlabel('时间 (s)', fontsize=12)
    ax3.set_ylabel('位移 (m)', fontsize=12)
    ax3.set_title('位移-时间曲线', fontsize=14)
    ax3.grid(True, alpha=0.3)
    ax3.legend()
    
    plt.tight_layout()
    plt.show()
    
    # ========== 4. 输出关键参数 ==========
    print("="*50)
    print("梯形加速运动参数汇总：")
    print(f"总距离：{S:.2f} m")
    print(f"目标匀速速度：{v_max:.2f} m/s")
    print(f"加速度：{a:.2f} m/s²")
    print(f"加速时间：{t1:.2f} s，加速距离：{s1:.2f} m")
    print(f"匀速时间：{t2:.2f} s，匀速距离：{s2:.2f} m")
    print(f"减速时间：{t3:.2f} s，减速距离：{s3:.2f} m")
    print(f"总运动时间：{total_time:.2f} s")
    print("="*50)
    
    return {
        't1': t1, 't2': t2, 't3': t3, 'total_time': total_time,
        's1': s1, 's2': s2, 's3': s3, 'v_max': v_max
    }

# ========== 示例调用 ==========
if __name__ == "__main__":
    total_distance = 10  # 总距离（m）
    target_velocity = 1  # 目标匀速速度（m/s）
    trapezoidal_profile(S=total_distance, v_max=target_velocity,a=1)