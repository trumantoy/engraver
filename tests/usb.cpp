#include <boost/asio.hpp>
#include <string>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <thread>
#include <mutex>
#include <condition_variable>
#include <chrono>
#include <vector>
#include <algorithm>

// 纯C接口声明
#ifdef __cplusplus
extern "C" {
#endif

typedef void* USBControllerHandle;

USBControllerHandle usb_controller_create();
int usb_controller_connect(USBControllerHandle handle, const char* port);
void usb_controller_disconnect(USBControllerHandle handle);
int usb_controller_is_connected(USBControllerHandle handle);
void usb_controller_get_name(USBControllerHandle handle, char* buf, size_t buf_len);
void usb_controller_set_pulse(USBControllerHandle handle);
void usb_controller_set_axes_invert(USBControllerHandle handle);
void usb_controller_set_process_params(USBControllerHandle handle);
void usb_controller_execute(USBControllerHandle handle, const char* gcode);
void usb_controller_destroy(USBControllerHandle handle);

#ifdef __cplusplus
}
#endif

// 内部状态结构体
struct ControllerCtx {
    boost::asio::io_context io_ctx;
    boost::asio::serial_port serial{io_ctx};
    std::string name;
    bool connected = false;
    std::vector<std::string> steps;
    std::mutex mutex,mutex_steps;
    std::condition_variable event;
    std::thread worker_thread;
    bool running = true;
};

// 后台工作线程（完全对齐Python原逻辑）
static void worker_func(ControllerCtx* ctx) {
    while (true) {
        std::unique_lock<std::mutex> lock_steps(ctx->mutex_steps);
        size_t count = ctx->steps.size();
        lock_steps.unlock();

        size_t sent = 0;
        size_t received = 0;
        const size_t limit = 800;

        std::unique_lock<std::mutex> lock(ctx->mutex);
        
        while (count > 0 || received < sent) {
            std::vector<std::string> req;
            std::stringstream ss;

            size_t take = std::min(received + limit - sent, count);
            if (take > 0) {
                lock_steps.lock();
                req.assign(ctx->steps.begin(), ctx->steps.begin() + take);
                ctx->steps.erase(ctx->steps.begin(), ctx->steps.begin() + take);
                lock_steps.unlock();
                for (const auto& cmd : req) ss << cmd;
                std::string s = ss.str();
                ctx->serial.write_some(boost::asio::buffer(s.c_str(), s.size()));
                sent += take;
                count -= take;
            }
            
            if (ctx->serial.is_open()) {
                char res_buf[1024 * 1024] = {0};
                size_t len = ctx->serial.read_some(boost::asio::buffer(res_buf, sizeof(res_buf)));
                std::string res(res_buf, len);
                received += std::count(res.begin(), res.end(), '\n');
            }

            printf("已发送：%zu, 已接收：%zu diff:%zu\n", sent, received, sent-received);
        }

        if (!ctx->running) break;
    }
}

// 内部辅助：发送单条指令
static void send_single_cmd(ControllerCtx* ctx, const char* cmd) {
    if (!ctx || !ctx->connected || !ctx->serial.is_open()) return;
    std::unique_lock<std::mutex> lock(ctx->mutex);
    try {
        ctx->serial.write_some(boost::asio::buffer(cmd, strlen(cmd)));
        char res[256] = {0};
        ctx->serial.read_some(boost::asio::buffer(res, sizeof(res)));
        printf("参数指令响应：%s\n", res); // 测试用：打印参数指令响应
    } catch (...) {
        printf("参数指令发送失败\n");
    }
}

// -------------------------- C接口实现 --------------------------
USBControllerHandle usb_controller_create() {
    try {
        ControllerCtx* ctx = new ControllerCtx();
        ctx->worker_thread = std::thread(worker_func, ctx);
        return (USBControllerHandle)ctx;
    } catch (...) {
        return NULL;
    }
}

int usb_controller_connect(USBControllerHandle handle, const char* port) {
    if (!handle || !port) return 0;
    ControllerCtx* ctx = (ControllerCtx*)handle;

    try {
        if (ctx->serial.is_open()) ctx->serial.close();
        ctx->serial.open(port);
        ctx->serial.set_option(boost::asio::serial_port::baud_rate(9600));
        ctx->serial.set_option(boost::asio::serial_port::character_size(8));
        ctx->serial.set_option(boost::asio::serial_port::parity(boost::asio::serial_port::parity::none));
        ctx->serial.set_option(boost::asio::serial_port::stop_bits(boost::asio::serial_port::stop_bits::one));
        ctx->serial.set_option(boost::asio::serial_port::flow_control(boost::asio::serial_port::flow_control::none));
        
        ctx->connected = usb_controller_is_connected(handle);
        if (ctx->connected) {
            printf("串口 %s 连接成功！\n", port);
        } else {
            printf("串口 %s 连接失败（设备验证失败）\n", port);
        }
        return ctx->connected ? 1 : 0;
    } catch (...) {
        ctx->serial.close();
        ctx->connected = false;
        printf("串口 %s 连接失败（打开失败）\n", port);
        return 0;
    }
}

void usb_controller_disconnect(USBControllerHandle handle) {
    if (!handle) return;
    ControllerCtx* ctx = (ControllerCtx*)handle;
    ctx->connected = false;
    if (ctx->serial.is_open()) {
        ctx->serial.close();
        printf("串口已断开连接\n");
    }
}

int usb_controller_is_connected(USBControllerHandle handle) {
    if (!handle) return 0;
    ControllerCtx* ctx = (ControllerCtx*)handle;

    if (!ctx->serial.is_open()) return 0;
    std::unique_lock<std::mutex> lock(ctx->mutex);

    try {
        const char* verify_cmd = "$I\n";
        ctx->serial.write_some(boost::asio::buffer(verify_cmd, strlen(verify_cmd)));
        std::this_thread::sleep_for(std::chrono::milliseconds(0));
        
        char buf[1024] = {0};
        size_t len = ctx->serial.read_some(boost::asio::buffer(buf, sizeof(buf)));
        std::string res(buf, len);

        if (res.find("[MODEL:") == std::string::npos) return 0;
        
        size_t model_start = res.find("[MODEL:") + strlen("[MODEL:");
        size_t model_end = res.find("]", model_start);
        if (model_start > 0 && model_end > model_start) {
            ctx->name = res.substr(model_start, model_end - model_start);
            printf("设备型号：%s\n", ctx->name.c_str());
        }
        return 1;
    } catch (...) {
        // 部分串口设备无MODEL响应，仍视为连接成功
        return 1;
    }
}

void usb_controller_get_name(USBControllerHandle handle, char* buf, size_t buf_len) {
    if (!handle || !buf || buf_len == 0) return;
    ControllerCtx* ctx = (ControllerCtx*)handle;
    strncpy(buf, ctx->name.c_str(), buf_len - 1);
    buf[buf_len - 1] = '\0';
}

void usb_controller_set_pulse(USBControllerHandle handle) {
    if (!handle) return;
    printf("发送脉冲参数指令：$222P1P400\n");
    send_single_cmd((ControllerCtx*)handle, "$222P1P400\n");
}

void usb_controller_set_axes_invert(USBControllerHandle handle) {
    if (!handle) return;
    printf("发送轴反转参数指令：$240P3P6P5P1\n");
    send_single_cmd((ControllerCtx*)handle, "$240P3P6P5P1\n");
}

void usb_controller_set_process_params(USBControllerHandle handle) {
    if (!handle) return;
    printf("发送加工参数指令：T0 C25\n");
    send_single_cmd((ControllerCtx*)handle, "T0 C25\n");
}

void usb_controller_execute(USBControllerHandle handle, const char* gcode) {
    if (!handle || !gcode) return;
    ControllerCtx* ctx = (ControllerCtx*)handle;
    if (!ctx->connected) {
        printf("串口未连接，无法发送G代码\n");
        return;
    }

    std::unique_lock<std::mutex> lock(ctx->mutex_steps);
    std::string gcode_str(gcode);
    size_t pos = 0;
    while (pos < gcode_str.size()) {
        size_t end = gcode_str.find('\n', pos);
        if (end == std::string::npos) end = gcode_str.size();
        std::string line = gcode_str.substr(pos, end - pos);
        pos = end + 1;
        
        if (!line.empty() && (line[0] == ' ' || line[0] == '\t')) {
            line = line.substr(line.find_first_not_of(" \t"));
        }
        if (!line.empty() && (line.back() == ' ' || line.back() == '\t')) {
            line = line.substr(0, line.find_last_not_of(" \t") + 1);
        }
        
        if (line.empty() || (line.size() > 0 && line[0] == ';')) continue;

        ctx->steps.push_back(line + "\n");
    }

    ctx->event.notify_one();
    printf("已添加 %zu 条G代码到发送队列\n", ctx->steps.size());
}

void usb_controller_destroy(USBControllerHandle handle) {
    if (!handle) return;
    ControllerCtx* ctx = (ControllerCtx*)handle;
    ctx->running = false;
    ctx->event.notify_one();
    if (ctx->worker_thread.joinable()) {
        ctx->worker_thread.join();
        printf("工作线程已退出\n");
    }
    if (ctx->serial.is_open()) ctx->serial.close();
    delete ctx;
    printf("控制器资源已释放\n");
}

#include <windows.h>
#include <fstream>
#include <sstream>

// -------------------------- 测试用main函数 --------------------------
int main(int argc, char* argv[]) {
    // 1. 检查参数（需传入串口名，如 COM3 或 /dev/ttyUSB0）
    if (argc < 2) {
        printf("使用方法：%s <串口名>\n", argv[0]);
        printf("示例：%s COM3\n", argv[0]);
        printf("示例：%s /dev/ttyUSB0\n", argv[0]);
        return -1;
    }
    const char* port = argv[1];

    // 2. 创建控制器实例
    USBControllerHandle handle = usb_controller_create();
    if (!handle) {
        printf("创建控制器失败\n");
        return -1;
    }

    // 3. 连接串口
    if (!usb_controller_connect(handle, port)) {
        usb_controller_destroy(handle);
        return -1;
    }

    // 4. 配置参数（可选）
    usb_controller_set_pulse(handle);
    std::this_thread::sleep_for(std::chrono::milliseconds(500)); // 等待指令执行
    usb_controller_set_axes_invert(handle);
    std::this_thread::sleep_for(std::chrono::milliseconds(500));
    usb_controller_set_process_params(handle);
    std::this_thread::sleep_for(std::chrono::milliseconds(500));

    std::string content = "G0 X20 Y20\nG0 X-20 Y-20\nG0 X0 Y0\n";
    // 新增：安全读取GCode文件内容
    std::ifstream file("b.gc", std::ios::in);
    if (file.is_open()) {
        std::stringstream ss;
        ss << file.rdbuf();  // 读取整个文件内容
        file.close();

        content = ss.str();
        printf("成功读取GCode文件 b.gc，文件大小：%zu 字节\n", content.size());
    } 

    printf("\n开始发送测试G代码：\n");
    usb_controller_execute(handle, content.c_str());

    getchar();

    // 7. 断开串口并释放资源
    usb_controller_disconnect(handle);
    usb_controller_destroy(handle);

    printf("\n测试完成！\n");
    return 0;
}