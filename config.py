# -*- coding: utf-8 -*-
"""
RK3576 机器人视觉配置文件
人脸跟踪 + 物品识别控制舵机
"""

import os

# ==================== 路径配置 ====================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# 模型路径（使用相对路径，便于移植）
MODEL_PATH = os.path.join(BASE_DIR, "models", "yolov5s_rk3576.rknn")

# ==================== 摄像头配置 ====================
CAMERA_CONFIG = {
    "id": 33,  # 摄像头索引
    "width": 640,
    "height": 480,
    "fps": 30,
}

# ==================== YOLO 检测配置 ====================
YOLO_CONFIG = {
    "input_size": (640, 640),  # 模型输入尺寸 (根据模型要求)
    "conf_threshold": 0.55,    # 置信度阈值 (调整到 0.55 平衡准确度和召回率)
    "iou_threshold": 0.4,      # NMS IOU 阈值 (调整到 0.4)
    "min_box_size": 60,        # 最小框尺寸 (调整到 60)
    "classes_file": os.path.join(BASE_DIR, "models", "coco.names"),
}

# ==================== 类别映射配置 ====================
# COCO 类别映射到我们的功能类别
CATEGORY_MAPPING = {
    # 人脸 (使用 person 作为替代，或需要专门的人脸检测模型)
    "face": ["person"],  # 如果没有专门的人脸检测，用 person 代替
    
    # 食物类 -> 点头 (扩展更多食物相关物品)
    "food": ["banana", "apple", "orange", "broccoli", "carrot", 
             "pizza", "donut", "cake", "sandwich", "hot dog",
             "bottle", "wine glass", "cup", "fork", "knife", 
             "spoon", "bowl", "orange", "sandwich"],
    
    # 学习类 -> 摇头 (扩展学习用品和日常物品)
    "learning": ["book", "laptop", "mouse", "remote", "keyboard",
                 "cell phone", "scissors", "backpack", "handbag",
                 "suitcase", "clock", "vase", "teddy bear", 
                 "umbrella", "tie", "wallet", "watch", "glasses"],
    
    # 其他类 -> 转圈 (包含家具、交通工具等)
    "other": ["chair", "couch", "potted plant", "bed", "dining table", 
              "toilet", "tv", "microwave", "oven", "toaster", "sink",
              "refrigerator", "clock", "vase", "bicycle", "car", 
              "motorcycle", "airplane", "bus", "train", "truck", "boat"]
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
    
    # Y轴（垂直）配置 - 调整中心位置，减小初始仰角
    "y_min": 40,
    "y_max": 90,
    "y_center": 50,  # 进一步减小初始仰角
    
    # 跟踪参数
    "dead_zone": 40,        # 死区像素（防止抖动）
    "gain_x": 0.08,         # X轴增益 640px -> ±25°
    "gain_y": 0.10,         # Y轴增益 480px -> ±50°
    "smooth_factor": 0.3,   # 平滑系数
    "move_delay": 3,        # 移动延迟 ms
}

# ==================== 动作配置 ====================
ACTION_CONFIG = {
    "pause_duration": 3.0,  # 执行动作后暂停跟踪的时间（秒）
    
    # 点头动作序列 (Y轴上下移动)
    "head_nod": [
        {"x": 0, "y": -15, "delay": 200},   # 向上
        {"x": 0, "y": 15, "delay": 200},    # 向下
        {"x": 0, "y": 0, "delay": 100},     # 回到中心
    ],
    
    # 摇头动作序列 (X轴左右移动)
    "head_shake": [
        {"x": -20, "y": 0, "delay": 200},   # 向左
        {"x": 20, "y": 0, "delay": 200},    # 向右
        {"x": 0, "y": 0, "delay": 100},     # 回到中心
    ],
    
    # 转圈动作序列 (组合动作)
    "head_roll": [
        {"x": -15, "y": -15, "delay": 200}, # 左上
        {"x": 15, "y": -15, "delay": 200},  # 右上
        {"x": 15, "y": 15, "delay": 200},   # 右下
        {"x": -15, "y": 15, "delay": 200},  # 左下
        {"x": 0, "y": 0, "delay": 100},     # 回到中心
    ],
}

# ==================== Flask 配置 ====================
FLASK_CONFIG = {
    "host": "0.0.0.0",
    "port": 8888,  # 更改端口避免冲突
    "debug": False,
}

# ==================== 日志配置 ====================
LOG_CONFIG = {
    "level": "INFO",
    "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
}
