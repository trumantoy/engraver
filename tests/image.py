import cairo
import numpy as np

def draw_gray_with_a8(output_png: str):
    width, height = 200, 200
    # 1. 生成灰度数据（模拟激光标刻的灰度图）
    gray_data = np.linspace(255, 255, width*height, dtype=np.uint8).reshape(height, width)
    
    # 2. 创建A8 Surface（直接用灰度数据当Alpha值）
    surface = cairo.ImageSurface.create_for_data(
        gray_data.data,
        cairo.FORMAT_A8,
        width,
        height,
        width * 1
    )
    
    # 3. 渲染A8 Surface到ARGB32 Surface（方便保存为PNG）
    output_surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, width, height)
    ctx = cairo.Context(output_surface)
    # 将A8的Alpha值映射为灰度（R=G=B=Alpha/255）
    ctx.set_source_surface(surface, 0, 0)
    ctx.paint()
    
    # 4. 保存为PNG（灰度图）
    output_surface.write_to_png(output_png)
    surface.finish()
    output_surface.finish()
    print(f"A8格式灰度图已保存：{output_png}")

if __name__ == "__main__":
    draw_gray_with_a8("a8_gray_output.png")