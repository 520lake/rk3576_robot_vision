#!/bin/bash
# 启动 RK3576 机器人视觉系统

echo "=========================================="
echo "RK3576 机器人视觉系统启动脚本"
echo "=========================================="

# 1. 清理之前的进程
echo "[1/3] 清理之前的进程..."
pkill -f "python3 app.py" 2>/dev/null
sleep 2

# 2. 释放摄像头
echo "[2/3] 释放摄像头设备..."
# 查找并释放占用摄像头的进程
fuser -k /dev/video33 2>/dev/null
fuser -k /dev/video0 2>/dev/null
sleep 1

# 3. 检查端口
echo "[3/3] 检查端口 8888..."
PORT_PID=$(lsof -t -i:8888 2>/dev/null)
if [ -n "$PORT_PID" ]; then
    echo "  释放端口 8888 (PID: $PORT_PID)"
    kill -9 $PORT_PID 2>/dev/null
    sleep 1
fi

echo ""
echo "=========================================="
echo "启动应用..."
echo "=========================================="
cd /home/myir/Desktop/rk3576_robot_vision
python3 app.py
