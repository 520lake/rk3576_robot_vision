#!/bin/bash
# RK3576 机器人视觉系统启动脚本
# 作者: SU_LAKE
# 日期: 2026/02/24

set -e  # 遇到错误立即退出

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 项目路径
PROJECT_DIR="/home/myir/Desktop/rk3576_robot_vision"
APP_NAME="RK3576 机器人视觉系统"
PORT=8888

# 打印带颜色的信息
print_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[OK]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 显示启动画面
show_banner() {
    echo ""
    echo "=========================================="
    echo "     🤖 RK3576 机器人视觉系统"
    echo "     人脸跟踪 + 物品识别 + 舵机控制"
    echo "=========================================="
    echo ""
}

# 检查是否在项目目录
check_project_dir() {
    if [ ! -d "$PROJECT_DIR" ]; then
        print_error "项目目录不存在: $PROJECT_DIR"
        exit 1
    fi
    cd "$PROJECT_DIR"
    print_success "进入项目目录: $PROJECT_DIR"
}

# 清理之前的进程
cleanup_processes() {
    print_info "清理之前的进程..."
    
    # 清理 Python 进程
    pkill -f "python3 app.py" 2>/dev/null || true
    sleep 1
    
    # 清理摄像头占用
    local video_devices=("/dev/video0" "/dev/video33" "/dev/video1")
    for device in "${video_devices[@]}"; do
        if [ -e "$device" ]; then
            fuser -k "$device" 2>/dev/null || true
        fi
    done
    sleep 1
    
    print_success "进程清理完成"
}

# 释放端口
release_port() {
    print_info "检查端口 $PORT..."
    local port_pid=$(lsof -t -i:$PORT 2>/dev/null || true)
    if [ -n "$port_pid" ]; then
        print_warning "端口 $PORT 被占用 (PID: $port_pid)，正在释放..."
        kill -9 $port_pid 2>/dev/null || true
        sleep 1
    fi
    print_success "端口 $PORT 可用"
}

# 检查 Python 环境
check_python_env() {
    print_info "检查 Python 环境..."
    
    if ! command -v python3 &> /dev/null; then
        print_error "Python3 未安装"
        exit 1
    fi
    
    local python_version=$(python3 --version 2>&1 | cut -d' ' -f2)
    print_success "Python 版本: $python_version"
    
    # 检查关键依赖
    local required_packages=("flask" "cv2" "numpy")
    for pkg in "${required_packages[@]}"; do
        if python3 -c "import $pkg" 2>/dev/null; then
            print_success "依赖包已安装: $pkg"
        else
            print_warning "依赖包未安装: $pkg"
        fi
    done
}

# 检查硬件设备
check_hardware() {
    print_info "检查硬件设备..."
    
    # 检查摄像头
    if [ -e "/dev/video0" ] || [ -e "/dev/video33" ]; then
        print_success "摄像头设备已连接"
    else
        print_warning "摄像头设备未检测到"
    fi
    
    # 检查 Arduino
    if [ -e "/dev/ttyACM0" ] || [ -e "/dev/ttyUSB0" ]; then
        print_success "Arduino 设备已连接"
    else
        print_warning "Arduino 设备未检测到"
    fi
    
    # 检查 NPU
    if lsmod | grep -q rknpu; then
        print_success "NPU 驱动已加载"
    else
        print_warning "NPU 驱动未加载 (将使用 CPU 模式)"
    fi
}

# 显示使用说明
show_usage() {
    echo ""
    echo "=========================================="
    echo "📖 使用说明"
    echo "=========================================="
    echo ""
    echo "1. 访问 Web 界面:"
    echo "   浏览器打开: http://$(hostname -I | awk '{print $1}'):$PORT"
    echo ""
    echo "2. 功能说明:"
    echo "   • 人脸跟踪: 自动识别人脸并控制舵机跟随"
    echo "   • 物品识别: 识别食物/学习用品/其他物品并执行动作"
    echo "   • 手动控制: 点击控制面板按钮控制舵机"
    echo ""
    echo "3. 停止系统:"
    echo "   按 Ctrl+C 停止"
    echo ""
    echo "=========================================="
    echo ""
}

# 主函数
main() {
    show_banner
    
    # 检查项目目录
    check_project_dir
    
    # 清理环境
    cleanup_processes
    release_port
    
    # 检查环境
    check_python_env
    check_hardware
    
    # 显示使用说明
    show_usage
    
    # 启动应用
    print_info "正在启动 $APP_NAME..."
    echo ""
    
    # 使用 exec 替换当前进程，确保信号能正确传递给 Python
    exec python3 app.py
}

# 处理中断信号
trap 'print_error "收到中断信号，正在退出..."; exit 0' INT TERM

# 运行主函数
main "$@"
