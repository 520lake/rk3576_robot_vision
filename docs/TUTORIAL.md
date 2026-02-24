# RK3576 机器人视觉系统 - 完整实现教程

> **版本**: v1.0  
> **日期**: 2024-02-24  
> **作者**: AI Assistant  
> **硬件**: MYIR RK3576 开发板 + Arduino R4 Minima + 双舵机云台

---

## 目录

1. [项目概述](#一项目概述)
2. [系统架构](#二系统架构)
3. [硬件准备](#三硬件准备)
4. [环境搭建](#四环境搭建)
5. [一步一步实现](#五一步一步实现)
6. [代码详解](#六代码详解)
7. [常见问题解决](#七常见问题解决)
8. [进阶优化](#八进阶优化)

---

## 一、项目概述

### 1.1 功能特性

本项目是 `my_robot_vision` 的升级版，实现了完整的视觉伺服控制系统：

| 功能模块 | 说明 |
|---------|------|
| **视觉识别** | 基于 YOLOv5 RKNN 的实时目标检测，支持人脸、食物、学习用品、其他物品识别 |
| **运动控制** | Arduino 双舵机云台（X/Y 轴），实现人脸跟踪和物品响应动作 |
| **交互界面** | Flask Web 界面，实时视频流 + 控制面板 |
| **远程控制** | 支持 OpenClaw 集成，可通过手机/Discord 远程控制 |

### 1.2 升级对比

| 特性 | my_robot_vision (基础版) | rk3576_robot_vision (升级版) |
|------|------------------------|----------------------------|
| 检测模型 | YOLOv5 基础检测 | YOLOv5 + 类别映射（4大类） |
| 舵机控制 | 简单移动 | 动作序列 + 自动回正 |
| 跟踪策略 | 单一目标 | 人脸优先 + 物品响应 |
| Web界面 | 基础视频流 | 完整控制面板 + 状态显示 |
| 远程控制 | 无 | OpenClaw 集成 |

---

## 二、系统架构

### 2.1 硬件架构

```
┌─────────────────────────────────────────────────────────────┐
│                    RK3576 开发板                            │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │   NPU 单元   │  │   CPU 单元   │  │   摄像头     │      │
│  │  YOLO推理    │  │  Flask服务   │  │  视频采集    │      │
│  │  80类检测    │  │  Web界面     │  │  /dev/video0 │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
│           │                │                │              │
│           └────────────────┴────────────────┘              │
│                            │                               │
│                     ┌──────┴──────┐                        │
│                     │  串口通信   │  /dev/ttyACM0          │
│                     └──────┬──────┘  115200bps             │
└────────────────────────────┼───────────────────────────────┘
                             │
                    ┌────────┴────────┐
                    │  Arduino R4     │
                    │   Minima        │
                    │  ┌───────────┐  │
                    │  │ X轴舵机   │  │  水平: 65°-115° (中心90°)
                    │  │ (水平)    │  │  SG90/MG90S
                    │  └───────────┘  │
                    │  ┌───────────┐  │
                    │  │ Y轴舵机   │  │  垂直: 40°-90° (中心50°)
                    │  │ (垂直)    │  │  SG90/MG90S
                    │  └───────────┘  │
                    └─────────────────┘
```

### 2.2 软件架构

```
┌─────────────────────────────────────────────────────────────┐
│                    Flask Web 应用层                         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │ 视频流接口   │  │ 控制API接口  │  │ 状态API接口  │      │
│  │ /video_feed  │  │ /api/control │  │ /api/status  │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│                    核心控制逻辑层                           │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │  RobotSystem │  │ ObjectTracker│  │ ServoController      │
│  │   主控制器   │  │   目标跟踪   │  │   舵机控制   │      │
│  │  初始化管理  │  │  人脸优先    │  │  动作序列    │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│                    硬件抽象层                               │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │    Camera    │  │   YOLODet    │  │  ServoCtrl   │      │
│  │   摄像头     │  │  NPU检测器   │  │  串口通信    │      │
│  │  640x480     │  │  640x640     │  │  JSON协议    │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
└─────────────────────────────────────────────────────────────┘
```

---

## 三、硬件准备

### 3.1 硬件清单

| 序号 | 设备 | 型号/规格 | 数量 | 说明 |
|-----|------|----------|------|------|
| 1 | 开发板 | MYIR RK3576 | 1 | 主控板，带NPU |
| 2 | 摄像头 | USB摄像头 | 1 | 支持Linux，分辨率≥640x480 |
| 3 | Arduino | Arduino R4 Minima | 1 | 舵机控制 |
| 4 | 舵机 | SG90/MG90S | 2 | X轴(水平) + Y轴(垂直) |
| 5 | 云台支架 | 双轴云台 | 1 | 安装两个舵机 |
| 6 | 数据线 | USB Type-C | 2 | 供电+数据传输 |
| 7 | 杜邦线 | 公对母 | 若干 | 舵机信号线连接 |

### 3.2 硬件连接

#### 舵机接线图

```
Arduino R4 Minima
    ┌─────────┐
    │         │
    │    D9   │─────── X轴舵机信号线 (橙色/黄色)
    │    D10  │─────── Y轴舵机信号线 (橙色/黄色)
    │    5V   │─────── 舵机电源正极 (红色) ×2
    │    GND  │─────── 舵机电源负极 (棕色/黑色) ×2
    │         │
    └────┬────┘
         │
    USB Type-C
         │
    RK3576 USB口
```

#### 注意事项

1. **电源问题**: 如果两个舵机同时运动电流较大，建议外接5V电源
2. **信号线**: 确保舵机信号线连接到PWM引脚（D9, D10）
3. **地线共接**: Arduino和舵机电源必须共地

---

## 四、环境搭建

### 4.1 系统准备

#### 4.1.1 检查 NPU 驱动

```bash
# 检查 NPU 设备是否存在
ls /dev/dri/card1
ls /dev/rknpu

# 检查驱动是否加载
dmesg | grep -i rknpu

# 如果没有加载，手动加载
sudo modprobe rknpu
```

#### 4.1.2 检查摄像头

```bash
# 列出所有视频设备
v4l2-ctl --list-devices

# 测试摄像头
ls /dev/video*

# 检查权限
sudo chmod 666 /dev/video0
```

#### 4.1.3 检查 Arduino

```bash
# 连接 Arduino 后检查串口
ls /dev/ttyACM*

# 添加用户到 dialout 组（避免权限问题）
sudo usermod -a -G dialout $USER

# 重新登录或执行
newgrp dialout
```

### 4.2 安装依赖

```bash
# 创建虚拟环境（推荐）
cd /home/myir/Desktop/rk3576_robot_vision
python3 -m venv venv
source venv/bin/activate

# 安装 Python 依赖
pip install flask opencv-python numpy pyserial

# 安装 RKNN 工具包（根据 RK3576 SDK 版本）
pip install rknn-toolkit2
```

### 4.3 模型准备

```bash
# 模型目录
mkdir -p models

# 放置模型文件
# - yolov5s.rknn: YOLOv5 RKNN 模型
# - coco.names: COCO 类别名称文件

# 验证模型
ls -la models/
```

---

## 五、一步一步实现

### 步骤 1: 项目初始化

创建项目目录结构：

```bash
mkdir -p /home/myir/Desktop/rk3576_robot_vision
cd /home/myir/Desktop/rk3576_robot_vision

# 创建目录结构
mkdir -p core templates static/css static/js models docs

# 创建空文件
touch core/__init__.py
touch config.py app.py start_app.sh
```

### 步骤 2: 配置文件 (config.py)

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
全局配置文件
"""
import os

# 基础路径
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ==================== 模型配置 ====================
MODEL_PATH = os.path.join(BASE_DIR, "models", "yolov5s.rknn")

# ==================== 摄像头配置 ====================
CAMERA_CONFIG = {
    "width": 640,
    "height": 480,
    "fps": 30,
    "buffer_size": 1
}

# ==================== YOLO 检测配置 ====================
YOLO_CONFIG = {
    "input_size": (640, 640),
    "conf_threshold": 0.55,    # 置信度阈值
    "iou_threshold": 0.4,      # NMS IOU 阈值
    "min_box_size": 60,        # 最小框尺寸
    "classes_file": os.path.join(BASE_DIR, "models", "coco.names"),
}

# ==================== 类别映射配置 ====================
CATEGORY_MAPPING = {
    "face": ["person"],
    "food": ["banana", "apple", "orange", "broccoli", "carrot", 
             "pizza", "donut", "cake", "sandwich", "hot dog",
             "bottle", "wine glass", "cup", "fork", "knife", 
             "spoon", "bowl"],
    "learning": ["book", "laptop", "mouse", "remote", "keyboard",
                 "cell phone", "scissors", "backpack", "handbag",
                 "suitcase", "clock", "vase", "teddy bear", 
                 "umbrella", "tie"],
    "other": ["chair", "couch", "potted plant", "bed", "dining table", 
              "toilet", "tv", "microwave", "oven", "toaster", "sink",
              "refrigerator", "bicycle", "car", "motorcycle", "airplane", 
              "bus", "train", "truck", "boat"]
}

# ==================== 舵机配置 ====================
SERVO_CONFIG = {
    "port": "/dev/ttyACM0",
    "baudrate": 115200,
    "timeout": 2,
    
    # X轴（水平）配置
    "x_min": 65,
    "x_max": 115,
    "x_center": 90,
    
    # Y轴（垂直）配置
    "y_min": 40,
    "y_max": 90,
    "y_center": 50,
    
    # 跟踪参数
    "dead_zone": 40,
    "gain_x": 0.08,
    "gain_y": 0.10,
    "smooth_factor": 0.3,
    "move_delay": 3,
}

# ==================== 动作配置 ====================
ACTION_CONFIG = {
    "pause_duration": 3.0,
    
    # 点头动作序列
    "head_nod": [
        {"x": 0, "y": -15, "delay": 200},
        {"x": 0, "y": 15, "delay": 200},
        {"x": 0, "y": 0, "delay": 100}
    ],
    
    # 摇头动作序列
    "head_shake": [
        {"x": -15, "y": 0, "delay": 150},
        {"x": 15, "y": 0, "delay": 150},
        {"x": -15, "y": 0, "delay": 150},
        {"x": 0, "y": 0, "delay": 100}
    ],
    
    # 转圈动作序列
    "head_roll": [
        {"x": -15, "y": -15, "delay": 150},
        {"x": 15, "y": -15, "delay": 150},
        {"x": 15, "y": 15, "delay": 150},
        {"x": -15, "y": 15, "delay": 150},
        {"x": 0, "y": 0, "delay": 100}
    ]
}

# ==================== 日志配置 ====================
LOG_CONFIG = {
    "level": "INFO",
    "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
}
```

### 步骤 3: 摄像头模块 (core/camera.py)

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
摄像头管理模块
支持多摄像头自动检测和后台捕获
"""

import cv2
import threading
import time
import logging
from typing import Tuple, Optional

logger = logging.getLogger(__name__)

class Camera:
    """摄像头管理类"""
    
    def __init__(self, width: int = 640, height: int = 480, fps: int = 30):
        self.width = width
        self.height = height
        self.fps = fps
        self.cap: Optional[cv2.VideoCapture] = None
        self._frame = None
        self._lock = threading.Lock()
        self._running = False
        self._capture_thread: Optional[threading.Thread] = None
        
    def open(self, camera_id: int = 0) -> bool:
        """打开摄像头"""
        try:
            self.cap = cv2.VideoCapture(camera_id, cv2.CAP_V4L2)
            if not self.cap.isOpened():
                logger.error(f"无法打开摄像头 {camera_id}")
                return False
                
            # 设置分辨率
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
            self.cap.set(cv2.CAP_PROP_FPS, self.fps)
            
            # 读取一帧测试
            ret, frame = self.cap.read()
            if not ret:
                logger.error("无法读取摄像头帧")
                self.cap.release()
                return False
                
            logger.info(f"摄像头已打开: {self.width}x{self.height} @ {self.fps}fps")
            
            # 启动后台捕获线程
            self._running = True
            self._capture_thread = threading.Thread(target=self._capture_loop, daemon=True)
            self._capture_thread.start()
            
            return True
            
        except Exception as e:
            logger.error(f"打开摄像头失败: {e}")
            return False
    
    def _capture_loop(self):
        """后台捕获线程"""
        while self._running:
            if self.cap and self.cap.isOpened():
                ret, frame = self.cap.read()
                if ret and frame is not None:
                    # 水平翻转解决镜像问题
                    frame = cv2.flip(frame, 1)
                    with self._lock:
                        self._frame = frame
            time.sleep(0.001)
    
    def read(self) -> Tuple[bool, Optional]:
        """读取当前帧"""
        with self._lock:
            if self._frame is not None:
                return True, self._frame.copy()
            return False, None
    
    def is_opened(self) -> bool:
        """检查摄像头是否打开"""
        return self.cap is not None and self.cap.isOpened() and self._running
    
    def release(self):
        """释放摄像头"""
        self._running = False
        if self._capture_thread:
            self._capture_thread.join(timeout=1.0)
        if self.cap:
            self.cap.release()
            self.cap = None
        logger.info("摄像头已释放")
```

### 步骤 4: 舵机控制模块 (core/servo_controller.py)

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
舵机控制器 - Arduino 串口通信
支持 JSON 协议和动作序列
"""

import json
import serial
import time
import logging
import threading
from typing import Optional, List, Dict

logger = logging.getLogger(__name__)

class ServoController:
    """舵机控制器，通过串口与 Arduino 通信"""
    
    def __init__(self, port: str = "/dev/ttyACM0", baudrate: int = 115200, timeout: float = 2):
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.serial: Optional[serial.Serial] = None
        self.initialized = False
        self._lock = threading.Lock()
        
        # 当前角度位置
        self.current_x = 90
        self.current_y = 70
        
        # 角度限制
        self.x_min, self.x_max = 65, 115
        self.y_min, self.y_max = 20, 120
        self.x_center, self.y_center = 90, 70
        
        # 动作执行状态
        self.is_executing_action = False
        self.action_start_time = 0
        self.action_pause_duration = 3.0
        
    def connect(self) -> bool:
        """连接到 Arduino"""
        try:
            self.serial = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                timeout=self.timeout,
                write_timeout=1
            )
            time.sleep(2)  # 等待 Arduino 启动
            self.initialized = True
            logger.info(f"成功连接到 Arduino: {self.port}")
            
            # 初始化到中心位置
            self.center()
            return True
            
        except Exception as e:
            logger.error(f"连接 Arduino 失败: {e}")
            self.initialized = False
            return False
    
    def send_command(self, command_dict: Dict) -> bool:
        """发送 JSON 命令到 Arduino"""
        if not self.initialized or not self.serial:
            return False
            
        try:
            with self._lock:
                json_str = json.dumps(command_dict) + "\n"
                self.serial.write(json_str.encode('utf-8'))
                self.serial.flush()
                logger.debug(f"发送命令: {json_str.strip()}")
                return True
        except Exception as e:
            logger.error(f"发送命令失败: {e}")
            return False
    
    def head_move(self, offset_x: int, offset_y: int, delay_ms: int = 3) -> bool:
        """移动舵机头"""
        if not self.initialized:
            return False
            
        # 限制偏移范围
        offset_x = max(-25, min(25, offset_x))
        offset_y = max(-50, min(50, offset_y))
        
        # 计算目标角度
        target_x = self.x_center + offset_x
        target_y = self.y_center + offset_y
        
        # 限制角度范围
        target_x = max(self.x_min, min(self.x_max, target_x))
        target_y = max(self.y_min, min(self.y_max, target_y))
        
        # 发送命令
        command = {
            "factory": f"head_move {offset_x} {offset_y} {delay_ms}"
        }
        
        if self.send_command(command):
            self.current_x = target_x
            self.current_y = target_y
            return True
        return False
    
    def center(self) -> bool:
        """回到中心位置"""
        if not self.initialized:
            return False
            
        # 使用 head_move 方法回到中心（偏移量为0）
        if self.head_move(0, 0, 10):
            self.current_x = self.x_center
            self.current_y = self.y_center
            logger.info("舵机回到中心位置")
            return True
        return False
    
    def execute_action(self, action_name: str, action_config: Dict) -> bool:
        """执行动作序列"""
        logger.info(f"execute_action 被调用: {action_name}")
        
        if not self.initialized:
            logger.error("舵机未初始化")
            return False
            
        if self.is_executing_action:
            logger.warning("动作正在执行中")
            return False
            
        if action_name not in action_config:
            logger.warning(f"未知动作: {action_name}")
            return False
            
        action_sequence = action_config[action_name]
        
        def action_thread():
            try:
                self.is_executing_action = True
                self.action_start_time = time.time()
                
                logger.info(f"开始执行动作: {action_name}")
                
                for i, step in enumerate(action_sequence):
                    x = step.get("x", 0)
                    y = step.get("y", 0)
                    delay = step.get("delay", 100)
                    
                    logger.info(f"  步骤 {i+1}/{len(action_sequence)}: x={x}, y={y}")
                    self.head_move(x, y, 3)
                    time.sleep(delay / 1000.0)
                    
                logger.info(f"动作 {action_name} 执行完成，回到中心")
                self.center()
            except Exception as e:
                logger.error(f"动作执行异常: {e}")
            finally:
                self.is_executing_action = False
                logger.info("动作状态已重置")
        
        thread = threading.Thread(target=action_thread, daemon=True)
        thread.start()
        return True
    
    def is_action_running(self) -> bool:
        """检查是否正在执行动作"""
        if not self.is_executing_action:
            return False
            
        elapsed = time.time() - self.action_start_time
        if elapsed > self.action_pause_duration:
            self.is_executing_action = False
            return False
            
        return True
    
    def is_connected(self) -> bool:
        """检查是否已连接"""
        return self.initialized and self.serial is not None and self.serial.is_open
    
    def close(self):
        """关闭连接"""
        if self.serial:
            try:
                self.center()
                time.sleep(0.5)
                self.serial.close()
            except:
                pass
        self.initialized = False
        logger.info("舵机连接已关闭")
```

### 步骤 5: 目标跟踪模块 (core/tracker.py)

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
目标跟踪模块 - 人脸优先 + 物品识别控制舵机
"""

import time
import logging
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

class ObjectTracker:
    """目标跟踪器"""
    
    def __init__(self, servo_controller, action_config: Dict):
        self.servo = servo_controller
        self.action_config = action_config
        
        # 跟踪状态
        self.target_face: Optional[Dict] = None
        self.last_face_time = 0
        self.face_lost_threshold = 0.5
        
        # 平滑滤波
        self.smooth_x = 320
        self.smooth_y = 240
        self.alpha = 0.3
        
        # 死区
        self.dead_zone = 40
        
        # 增益
        self.gain_x = 0.08
        self.gain_y = 0.10
        
        # 物品检测冷却
        self.last_detected_category = None
        self.category_cooldown = 3.0
        self.last_category_time = 0
        
        # 统计
        self.frame_count = 0
        self.last_fps_time = time.time()
        self.fps = 0
        
    def update(self, detections: List[Dict], frame_shape: Tuple) -> Dict:
        """更新跟踪状态并控制舵机"""
        self.frame_count += 1
        current_time = time.time()
        
        # 计算 FPS
        if current_time - self.last_fps_time >= 1.0:
            self.fps = self.frame_count
            self.frame_count = 0
            self.last_fps_time = current_time
            
        status = {
            "mode": "idle",
            "target": None,
            "action": None,
            "fps": self.fps,
            "message": ""
        }
        
        # 检查是否正在执行动作
        if self.servo and self.servo.is_action_running():
            remaining = self.servo.get_pause_remaining()
            status["mode"] = "action_pause"
            status["message"] = f"Action running, {remaining:.1f}s remaining"
            return status
        
        # 分类检测
        faces = [d for d in detections if d.get("category") == "face"]
        foods = [d for d in detections if d.get("category") == "food"]
        learnings = [d for d in detections if d.get("category") == "learning"]
        others = [d for d in detections if d.get("category") == "other"]
        
        # 策略 1: 优先跟踪人脸
        if faces:
            self.target_face = self._select_best_face(faces)
            self.last_face_time = current_time
            
            if self.target_face:
                # 估算人脸框
                x1, y1, x2, y2 = self.target_face['bbox']
                face_height = int((y2 - y1) * 0.3)
                face_width = int((x2 - x1) * 0.5)
                face_center_y = y1 + int((y2 - y1) * 0.15)
                face_center_x = (x1 + x2) // 2
                
                face_x1 = face_center_x - face_width // 2
                face_y1 = face_center_y - face_height // 2
                face_x2 = face_center_x + face_width // 2
                face_y2 = face_center_y + face_height // 2
                
                self.target_face['face_bbox'] = (face_x1, face_y1, face_x2, face_y2)
                
                # 使用人体中心跟踪
                person_center_x = (x1 + x2) // 2
                person_center_y = (y1 + y2) // 2
                
                track_target = self.target_face.copy()
                track_target['center'] = (person_center_x, person_center_y)
                
                self.alpha = 0.4
                self._track_target(track_target, frame_shape)
                status["mode"] = "face_tracking"
                status["target"] = self.target_face
                status["message"] = f"Face: {self.target_face['confidence']:.2f}"
                return status
        
        # 检查人脸是否刚丢失
        elif current_time - self.last_face_time < self.face_lost_threshold:
            if self.target_face:
                status["mode"] = "face_lost"
                status["message"] = "Face lost, holding position"
                return status
        
        # 策略 2: 无人脸时识别物品
        if current_time - self.last_category_time > self.category_cooldown:
            action_executed = False
            
            if foods:
                best_food = max(foods, key=lambda x: x["confidence"])
                if self._execute_category_action("food", best_food):
                    status["mode"] = "food_detected"
                    status["target"] = best_food
                    status["action"] = "head_nod"
                    status["message"] = f"Food: {best_food['label']}"
                    action_executed = True
                    
            elif learnings:
                best_learning = max(learnings, key=lambda x: x["confidence"])
                if self._execute_category_action("learning", best_learning):
                    status["mode"] = "learning_detected"
                    status["target"] = best_learning
                    status["action"] = "head_shake"
                    status["message"] = f"Learning: {best_learning['label']}"
                    action_executed = True
                    
            elif others:
                best_other = max(others, key=lambda x: x["confidence"])
                if self._execute_category_action("other", best_other):
                    status["mode"] = "other_detected"
                    status["target"] = best_other
                    status["action"] = "head_roll"
                    status["message"] = f"Other: {best_other['label']}"
                    action_executed = True
                    
            if action_executed:
                return status
        
        status["mode"] = "idle"
        status["message"] = "Waiting for target..."
        return status
    
    def _select_best_face(self, faces: List[Dict]) -> Optional[Dict]:
        """选择最佳人脸"""
        if not faces:
            return None
        
        faces = sorted(faces, key=lambda x: x["confidence"], reverse=True)
        
        if faces[0]["confidence"] > 0.7:
            return faces[0]
        
        scored_faces = []
        for face in faces:
            x1, y1, x2, y2 = face["bbox"]
            area = (x2 - x1) * (y2 - y1)
            center_x = (x1 + x2) // 2
            center_y = (y1 + y2) // 2
            
            dist_to_center = ((center_x - 320) ** 2 + (center_y - 240) ** 2) ** 0.5
            max_dist = (320**2 + 240**2) ** 0.5
            center_score = 1 - (dist_to_center / max_dist)
            
            area_score = min(area / 100000, 1.0)
            score = face["confidence"] * 0.5 + center_score * 0.3 + area_score * 0.2
            
            scored_faces.append((score, face))
        
        scored_faces.sort(key=lambda x: x[0], reverse=True)
        return scored_faces[0][1]
    
    def _track_target(self, target: Dict, frame_shape: Tuple):
        """跟踪目标并控制舵机"""
        if not self.servo or not self.servo.initialized:
            return
            
        center_x, center_y = target["center"]
        confidence = target.get("confidence", 0.5)
        
        if confidence > 0.7:
            alpha = 0.6
        elif confidence > 0.5:
            alpha = 0.4
        else:
            alpha = 0.25
        
        self.smooth_x = alpha * center_x + (1 - alpha) * self.smooth_x
        self.smooth_y = alpha * center_y + (1 - alpha) * self.smooth_y
        
        frame_center_x = frame_shape[1] // 2
        frame_center_y = frame_shape[0] // 2
        
        offset_x = int(self.smooth_x - frame_center_x)
        offset_y = int(self.smooth_y - frame_center_y)
        
        dynamic_dead_zone = int(self.dead_zone * (1 - confidence * 0.5))
        if abs(offset_x) < dynamic_dead_zone:
            offset_x = 0
        if abs(offset_y) < dynamic_dead_zone:
            offset_y = 0
            
        angle_x = int(offset_x * self.gain_x)
        angle_y = int(offset_y * self.gain_y)
        
        angle_x = max(-25, min(25, angle_x))
        angle_y = max(-50, min(50, angle_y))
        
        self.servo.head_move(angle_x, angle_y)
    
    def _execute_category_action(self, category: str, detection: Dict) -> bool:
        """执行类别对应的动作"""
        if not self.servo or not self.servo.initialized:
            return False
            
        action_map = {
            "food": "head_nod",
            "learning": "head_shake",
            "other": "head_roll"
        }
        
        action_name = action_map.get(category)
        if not action_name:
            return False
            
        if self.servo.execute_action(action_name, self.action_config):
            self.last_category_time = time.time()
            self.last_detected_category = category
            logger.info(f"执行动作 {action_name} 响应类别 {category}")
            return True
            
        return False
    
    def reset(self):
        """重置跟踪状态"""
        self.target_face = None
        self.last_face_time = 0
        self.smooth_x = 320
        self.smooth_y = 240
        self.last_detected_category = None
        
        if self.servo and self.servo.initialized:
            self.servo.center()
```

### 步骤 6: NPU 检测器 (core/detector.py)

由于篇幅限制，检测器代码请参考项目中的 `core/detector.py` 文件。核心要点：

1. 使用 `rknnlite.api.RKNNLite` 加载模型
2. 预处理：resize → BGR2RGB → normalize → HWC2CHW
3. 后处理：YOLOv5 三分支输出解码 + NMS
4. 类别映射到 face/food/learning/other

### 步骤 7: 主应用 (app.py)

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RK3576 机器人视觉 - Flask Web 应用
人脸跟踪 + 物品识别控制舵机
"""

import cv2
import numpy as np
import logging
import threading
import time
import os
from flask import Flask, render_template, Response, jsonify

import config
from core.camera import Camera
from core.detector import YOLODetector
from core.detector_cpu import YOLODetectorCPU
from core.servo_controller import ServoController
from core.tracker import ObjectTracker

# 配置日志
logging.basicConfig(
    level=getattr(logging, config.LOG_CONFIG["level"]),
    format=config.LOG_CONFIG["format"]
)
logger = logging.getLogger(__name__)

# 创建 Flask 应用
app = Flask(__name__)

class RobotSystem:
    """机器人系统主类"""
    
    def __init__(self):
        self.camera: Camera = None
        self.detector = None
        self.servo: ServoController = None
        self.tracker: ObjectTracker = None
        self.is_running = False
        self.simulation_mode = False
        self.show_detection = True
        self.status = {"mode": "initializing", "message": "System starting..."}
        
    def initialize(self):
        """初始化系统"""
        logger.info("=" * 50)
        logger.info("RK3576 Robot Vision System Initializing")
        logger.info("=" * 50)
        
        # 1. 初始化摄像头
        logger.info("[1/4] Initializing camera...")
        self.camera = Camera(
            width=config.CAMERA_CONFIG["width"],
            height=config.CAMERA_CONFIG["height"],
            fps=config.CAMERA_CONFIG["fps"]
        )
        if not self.camera.open(0):
            logger.error("Failed to open camera")
            return False
        logger.info("✓ Camera initialized")
        
        # 2. 初始化检测器
        logger.info("[2/4] Initializing detector...")
        self.detector = YOLODetector(
            model_path=config.MODEL_PATH,
            input_size=config.YOLO_CONFIG["input_size"],
            conf_threshold=config.YOLO_CONFIG["conf_threshold"],
            iou_threshold=config.YOLO_CONFIG["iou_threshold"],
            min_box_size=config.YOLO_CONFIG.get("min_box_size", 50)
        )
        if not self.detector.initialize():
            logger.warning("NPU detector failed, trying CPU fallback...")
            self.detector = YOLODetectorCPU(
                model_path=config.MODEL_PATH,
                input_size=config.YOLO_CONFIG["input_size"],
                conf_threshold=config.YOLO_CONFIG["conf_threshold"],
                iou_threshold=config.YOLO_CONFIG["iou_threshold"],
                min_box_size=config.YOLO_CONFIG.get("min_box_size", 50)
            )
            if not self.detector.initialize():
                logger.error("Both NPU and CPU detectors failed")
                return False
            self.simulation_mode = True
        logger.info("✓ Detector initialized")
        
        # 3. 初始化舵机
        logger.info("[3/4] Initializing servo...")
        self.servo = ServoController(
            port=config.SERVO_CONFIG["port"],
            baudrate=config.SERVO_CONFIG["baudrate"],
            timeout=config.SERVO_CONFIG["timeout"]
        )
        if not self.servo.connect():
            logger.warning("Servo not connected, continuing without servo control")
        else:
            logger.info("✓ Servo initialized")
        
        # 4. 初始化跟踪器
        logger.info("[4/4] Initializing tracker...")
        self.tracker = ObjectTracker(
            servo_controller=self.servo,
            action_config=config.ACTION_CONFIG
        )
        logger.info("✓ Tracker initialized")
        
        self.is_running = True
        logger.info("=" * 50)
        logger.info("System initialization complete")
        logger.info("=" * 50)
        return True
    
    def generate_frames(self):
        """生成视频帧"""
        while self.is_running:
            try:
                ret, frame = self.camera.read()
                if not ret or frame is None:
                    time.sleep(0.01)
                    continue
                
                # 检测
                detections = self.detector.detect(frame)
                
                # 更新跟踪
                if self.tracker:
                    self.status = self.tracker.update(detections, frame.shape)
                
                # 绘制检测框
                if self.show_detection:
                    frame = self._draw_detections(frame, detections)
                
                # 绘制状态
                frame = self._draw_status(frame)
                
                # 编码
                ret, buffer = cv2.imencode('.jpg', frame)
                if not ret:
                    continue
                
                frame_bytes = buffer.tobytes()
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
                
            except Exception as e:
                logger.error(f"Frame generation error: {e}")
                time.sleep(0.01)
    
    def _draw_detections(self, frame, detections):
        """绘制检测结果"""
        colors = {
            "face": (0, 0, 255),
            "food": (0, 255, 0),
            "learning": (255, 0, 0),
            "other": (255, 255, 0),
        }
        
        # 只绘制最大目标
        if detections:
            largest = max(detections, key=lambda d: 
                         (d["bbox"][2] - d["bbox"][0]) * (d["bbox"][3] - d["bbox"][1]))
            
            x1, y1, x2, y2 = largest["bbox"]
            category = largest.get("category", "other")
            color = colors.get(category, (128, 128, 128))
            
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
            
            label = f"{largest['label']}: {largest['confidence']:.2f}"
            cv2.putText(frame, label, (x1, y1 - 10),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
        
        return frame
    
    def _draw_status(self, frame):
        """绘制状态信息"""
        mode = self.status.get("mode", "unknown")
        fps = self.status.get("fps", 0)
        message = self.status.get("message", "")
        
        cv2.putText(frame, f"Mode: {mode}", (10, 30),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        cv2.putText(frame, f"FPS: {fps}", (10, 60),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        cv2.putText(frame, message, (10, 90),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 2)
        
        return frame

# 全局系统实例
robot_system = RobotSystem()

@app.route('/')
def index():
    """主页"""
    return render_template('index.html')

@app.route('/video_feed')
def video_feed():
    """视频流"""
    return Response(robot_system.generate_frames(),
                   mimetype='multipart/x-mixed-replace; boundary=frame',
                   headers={
                       'Cache-Control': 'no-cache, no-store, must-revalidate',
                       'Pragma': 'no-cache',
                       'Expires': '0'
                   })

@app.route('/api/status')
def api_status():
    """获取系统状态"""
    status = robot_system.status.copy()
    status["camera_connected"] = robot_system.camera.is_opened() if robot_system.camera else False
    status["detector_initialized"] = robot_system.detector.initialized if robot_system.detector else False
    status["servo_connected"] = robot_system.servo.is_connected() if robot_system.servo else False
    status["simulation_mode"] = robot_system.simulation_mode
    status["system_running"] = robot_system.is_running
    return jsonify(status)

@app.route('/api/control/<action>', methods=['POST'])
def api_control(action):
    """控制接口"""
    logger.info(f"Control API called: {action}")
    
    if action == 'center':
        if robot_system.servo and robot_system.servo.initialized:
            result = robot_system.servo.center()
            return jsonify({"success": result, "message": "Centered" if result else "Failed"})
        return jsonify({"success": False, "message": "Servo not connected"})
    
    elif action == 'reset':
        if robot_system.tracker:
            robot_system.tracker.reset()
            return jsonify({"success": True, "message": "Tracker reset"})
        return jsonify({"success": False, "message": "Tracker not initialized"})
    
    elif action == 'toggle_detection':
        robot_system.show_detection = not robot_system.show_detection
        status = "showing" if robot_system.show_detection else "hidden"
        return jsonify({"success": True, "message": f"Detection {status}"})
    
    elif action == 'action_nod':
        if robot_system.servo and robot_system.servo.initialized:
            result = robot_system.servo.execute_action("head_nod", config.ACTION_CONFIG)
            return jsonify({"success": result, "message": "Nod action" if result else "Failed"})
        return jsonify({"success": False, "message": "Servo not connected"})
    
    elif action == 'action_shake':
        if robot_system.servo and robot_system.servo.initialized:
            result = robot_system.servo.execute_action("head_shake", config.ACTION_CONFIG)
            return jsonify({"success": result, "message": "Shake action" if result else "Failed"})
        return jsonify({"success": False, "message": "Servo not connected"})
    
    elif action == 'action_roll':
        if robot_system.servo and robot_system.servo.initialized:
            result = robot_system.servo.execute_action("head_roll", config.ACTION_CONFIG)
            return jsonify({"success": result, "message": "Roll action" if result else "Failed"})
        return jsonify({"success": False, "message": "Servo not connected"})
    
    return jsonify({"success": False, "message": "Unknown action"})

def main():
    """主函数"""
    if not robot_system.initialize():
        logger.error("System initialization failed")
        return
    
    try:
        app.run(host='0.0.0.0', port=8888, threaded=True)
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    finally:
        robot_system.is_running = False
        if robot_system.camera:
            robot_system.camera.release()
        if robot_system.servo:
            robot_system.servo.close()

if __name__ == '__main__':
    main()
```

### 步骤 8: Web 界面 (templates/index.html)

```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>RK3576 机器人视觉系统</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            min-height: 100vh;
            color: #fff;
        }
        .container { max-width: 1400px; margin: 0 auto; padding: 20px; }
        header {
            text-align: center;
            padding: 20px 0;
            border-bottom: 2px solid #0f3460;
            margin-bottom: 20px;
        }
        header h1 {
            font-size: 2.5em;
            background: linear-gradient(90deg, #e94560, #ff6b6b);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        .main-content {
            display: grid;
            grid-template-columns: 1fr 350px;
            gap: 20px;
        }
        @media (max-width: 1024px) {
            .main-content { grid-template-columns: 1fr; }
        }
        .video-section {
            background: #0f3460;
            border-radius: 15px;
            padding: 20px;
        }
        .video-container {
            position: relative;
            width: 100%;
            padding-bottom: 75%;
            background: #000;
            border-radius: 10px;
            overflow: hidden;
        }
        .video-container img {
            position: absolute;
            top: 0; left: 0;
            width: 100%; height: 100%;
            object-fit: contain;
        }
        .control-panel { display: flex; flex-direction: column; gap: 20px; }
        .panel-card {
            background: #0f3460;
            border-radius: 15px;
            padding: 20px;
        }
        .panel-card h3 {
            color: #e94560;
            margin-bottom: 15px;
            font-size: 1.2em;
        }
        .button-group {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 10px;
        }
        .btn {
            padding: 12px 20px;
            border: none;
            border-radius: 8px;
            cursor: pointer;
            font-size: 1em;
            transition: all 0.3s ease;
        }
        .btn-primary {
            background: linear-gradient(135deg, #e94560, #c73e54);
            color: #fff;
        }
        .btn-secondary {
            background: #1a1a2e;
            color: #fff;
        }
        .btn-action {
            background: linear-gradient(135deg, #3498db, #2980b9);
            color: #fff;
        }
        .btn:hover { transform: translateY(-2px); }
        .btn-full { grid-column: 1 / -1; }
        .status-item {
            display: flex;
            justify-content: space-between;
            padding: 10px 0;
            border-bottom: 1px solid #1a1a2e;
        }
        .status-label { color: #a0a0a0; }
        .status-value { color: #fff; font-weight: bold; }
        .status-value.online { color: #2ecc71; }
        .status-value.offline { color: #e74c3c; }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>RK3576 机器人视觉系统</h1>
            <p>人脸跟踪 + 物品识别 + 舵机控制</p>
        </header>
        
        <div class="main-content">
            <div class="video-section">
                <div class="video-container">
                    <img id="videoStream" src="/video_feed" alt="视频流">
                </div>
            </div>
            
            <div class="control-panel">
                <div class="panel-card">
                    <h3>📊 系统状态</h3>
                    <div class="status-item">
                        <span class="status-label">模式:</span>
                        <span class="status-value" id="mode">初始化中...</span>
                    </div>
                    <div class="status-item">
                        <span class="status-label">FPS:</span>
                        <span class="status-value" id="fps">0</span>
                    </div>
                    <div class="status-item">
                        <span class="status-label">摄像头:</span>
                        <span class="status-value" id="camera_status">检查中...</span>
                    </div>
                    <div class="status-item">
                        <span class="status-label">检测器:</span>
                        <span class="status-value" id="detector_status">检查中...</span>
                    </div>
                    <div class="status-item">
                        <span class="status-label">舵机:</span>
                        <span class="status-value" id="servo_status">检查中...</span>
                    </div>
                </div>
                
                <div class="panel-card">
                    <h3>🎮 控制面板</h3>
                    <div class="button-group">
                        <button class="btn btn-primary" onclick="sendCommand('center')">
                            🎯 回中心
                        </button>
                        <button class="btn btn-secondary" onclick="sendCommand('reset')">
                            🔄 重置跟踪
                        </button>
                        <button class="btn btn-secondary btn-full" onclick="sendCommand('toggle_detection')">
                            👁️ 显示/隐藏检测框
                        </button>
                    </div>
                </div>
                
                <div class="panel-card">
                    <h3>🎬 动作测试</h3>
                    <div class="button-group">
                        <button class="btn btn-action" onclick="sendCommand('action_nod')">
                            ↕️ 点头
                        </button>
                        <button class="btn btn-action" onclick="sendCommand('action_shake')">
                            ↔️ 摇头
                        </button>
                        <button class="btn btn-action btn-full" onclick="sendCommand('action_roll')">
                            🔄 转圈
                        </button>
                    </div>
                </div>
            </div>
        </div>
    </div>
    
    <script>
        async function sendCommand(action) {
            console.log(`Sending command: ${action}`);
            try {
                const response = await fetch(`/api/control/${action}`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' }
                });
                const data = await response.json();
                console.log('Response:', data);
                showMessage(data.message, !data.success);
            } catch (error) {
                console.error('Error:', error);
                showMessage('Network error: ' + error.message, true);
            }
        }
        
        function showMessage(message, isError = false) {
            const msgDiv = document.createElement('div');
            msgDiv.textContent = message;
            msgDiv.style.cssText = `
                position: fixed;
                top: 20px;
                right: 20px;
                padding: 15px 20px;
                border-radius: 8px;
                color: white;
                font-weight: bold;
                z-index: 10000;
                background: ${isError ? '#e74c3c' : '#27ae60'};
                box-shadow: 0 4px 12px rgba(0,0,0,0.3);
            `;
            document.body.appendChild(msgDiv);
            setTimeout(() => msgDiv.remove(), 3000);
        }
        
        async function updateStatus() {
            try {
                const response = await fetch('/api/status');
                const data = await response.json();
                
                document.getElementById('mode').textContent = data.mode || 'unknown';
                document.getElementById('fps').textContent = data.fps || 0;
                
                const camStatus = document.getElementById('camera_status');
                camStatus.textContent = data.camera_connected ? '在线' : '离线';
                camStatus.className = 'status-value ' + (data.camera_connected ? 'online' : 'offline');
                
                const detStatus = document.getElementById('detector_status');
                detStatus.textContent = data.detector_initialized ? '在线' : '离线';
                detStatus.className = 'status-value ' + (data.detector_initialized ? 'online' : 'offline');
                
                const servoStatus = document.getElementById('servo_status');
                servoStatus.textContent = data.servo_connected ? '在线' : '离线';
                servoStatus.className = 'status-value ' + (data.servo_connected ? 'online' : 'offline');
            } catch (error) {
                console.error('Status update failed:', error);
            }
        }
        
        setInterval(updateStatus, 1000);
        updateStatus();
    </script>
</body>
</html>
```

### 步骤 9: 启动脚本 (start_app.sh)

```bash
#!/bin/bash
# RK3576 机器人视觉系统启动脚本

echo "=========================================="
echo "RK3576 Robot Vision System"
echo "=========================================="

# 清理之前的进程
echo "[1/3] Cleaning up previous processes..."
pkill -f "python3 app.py" 2>/dev/null
sleep 2

# 释放摄像头
echo "[2/3] Releasing camera device..."
fuser -k /dev/video0 2>/dev/null
fuser -k /dev/video33 2>/dev/null
sleep 1

# 检查端口
echo "[3/3] Checking port 8888..."
PORT_PID=$(lsof -t -i:8888 2>/dev/null)
if [ -n "$PORT_PID" ]; then
    echo "  Releasing port 8888 (PID: $PORT_PID)"
    kill -9 $PORT_PID 2>/dev/null
    sleep 1
fi

echo ""
echo "=========================================="
echo "Starting application..."
echo "=========================================="
cd /home/myir/Desktop/rk3576_robot_vision
source venv/bin/activate 2>/dev/null || true
python3 app.py
```

---

## 六、代码详解

### 6.1 核心类关系图

```
RobotSystem (主控制器)
    ├── Camera (摄像头管理)
    │   └── 后台捕获线程
    ├── YOLODetector (NPU检测器)
    │   ├── preprocess (预处理)
    │   ├── inference (NPU推理)
    │   └── postprocess (后处理+NMS)
    ├── ServoController (舵机控制)
    │   ├── head_move (移动)
    │   ├── center (回中心)
    │   └── execute_action (动作序列)
    └── ObjectTracker (目标跟踪)
        ├── _select_best_face (选择人脸)
        ├── _track_target (跟踪控制)
        └── _execute_category_action (物品响应)
```

### 6.2 跟踪策略流程

```
开始
  │
  ▼
检测图像 ──► 分类检测结果
  │           ├── 人脸
  │           ├── 食物
  │           ├── 学习用品
  │           └── 其他
  │
  ▼
有人脸？ ──是──► 人脸跟踪模式
  │               ├── 估算人脸位置
  │               ├── 平滑滤波
  │               └── 控制舵机跟随
  │
  否
  ▼
动作执行中？ ──是──► 等待完成
  │
  否
  ▼
冷却时间到？ ──否──► 继续等待
  │
  是
  ▼
有食物？ ──是──► 执行点头动作
  │
  否
  ▼
有学习用品？ ──是──► 执行摇头动作
  │
  否
  ▼
有其他物品？ ──是──► 执行转圈动作
  │
  否
  ▼
待机模式
```

---

## 七、常见问题解决

### 7.1 摄像头问题

#### 问题：摄像头无法打开
```bash
# 检查设备
v4l2-ctl --list-devices

# 检查权限
ls -la /dev/video*
sudo chmod 666 /dev/video0

# 释放占用
fuser -k /dev/video0
```

#### 问题：画面镜像
已在 `camera.py` 中添加自动水平翻转：
```python
frame = cv2.flip(frame, 1)  # 水平翻转
```

### 7.2 NPU 检测问题

#### 问题：NPU 检测失败
```bash
# 检查驱动
dmesg | grep rknpu
sudo modprobe rknpu

# 使用 CPU 备用
# 程序会自动回退到 YOLODetectorCPU
```

#### 问题：检测框偏移
- 确保 `input_size` 与模型一致 (640x640)
- 检查后处理中的坐标缩放比例

### 7.3 舵机控制问题

#### 问题：舵机不响应
```bash
# 检查串口
ls -la /dev/ttyACM*

# 检查权限
sudo usermod -a -G dialout $USER

# 测试通信
python3 -c "from core.servo_controller import ServoController; s = ServoController(); print(s.connect())"
```

#### 问题：仰角太大
修改 `config.py`：
```python
"y_center": 50  # 从 70 逐步调小
```

#### 问题：动作后不回正
已在 `servo_controller.py` 的 `action_thread` 中添加：
```python
finally:
    self.center()  # 确保回中心
    self.is_executing_action = False
```

### 7.4 Web 界面问题

#### 问题：无法访问
```bash
# 检查防火墙
sudo ufw allow 8888

# 检查绑定地址
# 确保 app.run(host='0.0.0.0', ...)
```

#### 问题：按钮无响应
- 检查浏览器控制台日志
- 检查网络请求是否成功
- 查看后端日志输出

---

## 八、进阶优化

### 8.1 性能优化

1. **降低分辨率**：将摄像头分辨率从 640x480 降到 320x240
2. **跳过帧处理**：每 2-3 帧处理一次检测
3. **模型量化**：使用 INT8 量化模型

### 8.2 功能扩展

1. **添加语音控制**：集成 OpenClaw 语音指令
2. **添加手势识别**：使用 MediaPipe 检测手势
3. **添加记录功能**：保存检测历史到数据库

### 8.3 远程控制

集成 OpenClaw 实现远程控制：

```python
# 在 app.py 中添加
from openclaw import OpenClaw

claw = OpenClaw()

@claw.command()
def lookat(x: int, y: int):
    """看向指定坐标"""
    robot_system.servo.head_move(x, y)

@claw.command()
def center():
    """回到中心"""
    robot_system.servo.center()
```

---

## 附录

### A. 项目文件结构

```
rk3576_robot_vision/
├── app.py                      # Flask 主应用
├── config.py                   # 全局配置
├── start_app.sh               # 启动脚本
├── README.md                  # 项目说明
├── docs/
│   └── TUTORIAL.md           # 本教程
├── core/                      # 核心模块
│   ├── __init__.py
│   ├── camera.py             # 摄像头管理
│   ├── detector.py           # NPU 检测器
│   ├── detector_cpu.py       # CPU 备用检测器
│   ├── tracker.py            # 目标跟踪
│   └── servo_controller.py   # 舵机控制
├── templates/                 # Web 模板
│   └── index.html
├── static/                    # 静态资源
│   ├── css/
│   └── js/
└── models/                    # 模型文件
    ├── yolov5s.rknn
    └── coco.names
```

### B. 参考资料

- [RKNN Toolkit2 文档](https://github.com/rockchip-linux/rknn-toolkit2)
- [YOLOv5 官方文档](https://docs.ultralytics.com/)
- [Flask 文档](https://flask.palletsprojects.com/)
- [OpenClaw 文档](https://docs.openclaw.io/)

### C. 版本历史

| 版本 | 日期 | 说明 |
|-----|------|------|
| v0.1 | 2024-01 | my_robot_vision 基础版 |
| v1.0 | 2024-02 | rk3576_robot_vision 完整版 |

---

**文档结束**
