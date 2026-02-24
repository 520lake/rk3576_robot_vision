# -*- coding: utf-8 -*-
"""
YOLO 检测模块 - CPU 版本 (备用)
当 NPU 不可用时使用 OpenCV DNN 进行 CPU 推理
"""

import cv2
import numpy as np
import logging
import os
from typing import List, Tuple, Dict, Optional

logger = logging.getLogger(__name__)


class YOLODetectorCPU:
    """YOLO 目标检测器 - CPU 模式"""

    # COCO 80 类名称
    COCO_NAMES = [
        'person', 'bicycle', 'car', 'motorcycle', 'airplane', 'bus', 'train', 'truck', 'boat', 'traffic light',
        'fire hydrant', 'stop sign', 'parking meter', 'bench', 'bird', 'cat', 'dog', 'horse', 'sheep', 'cow',
        'elephant', 'bear', 'zebra', 'giraffe', 'backpack', 'umbrella', 'handbag', 'tie', 'suitcase', 'frisbee',
        'skis', 'snowboard', 'sports ball', 'kite', 'baseball bat', 'baseball glove', 'skateboard', 'surfboard',
        'tennis racket', 'bottle', 'wine glass', 'cup', 'fork', 'knife', 'spoon', 'bowl', 'banana', 'apple',
        'sandwich', 'orange', 'broccoli', 'carrot', 'hot dog', 'pizza', 'donut', 'cake', 'chair', 'couch',
        'potted plant', 'bed', 'dining table', 'toilet', 'tv', 'laptop', 'mouse', 'remote', 'keyboard',
        'cell phone', 'microwave', 'oven', 'toaster', 'sink', 'refrigerator', 'book', 'clock', 'vase',
        'scissors', 'teddy bear', 'hair drier', 'toothbrush'
    ]

    def __init__(self, model_path: str, input_size: Tuple[int, int] = (640, 640),
                 conf_threshold: float = 0.5, iou_threshold: float = 0.3,
                 min_box_size: int = 50):
        self.model_path = model_path
        self.input_size = input_size
        self.conf_threshold = conf_threshold
        self.iou_threshold = iou_threshold
        self.min_box_size = min_box_size
        self.net = None
        self.initialized = False

        # 类别映射
        self.category_map = {
            "food": ["banana", "apple", "orange", "broccoli", "carrot",
                     "pizza", "donut", "cake", "sandwich", "hot dog"],
            "learning": ["book", "laptop", "mouse", "remote", "keyboard",
                         "cell phone", "scissors", "backpack"],
            "face": ["person"],
            "other": []
        }

        self._init_model()

    def _init_model(self):
        """初始化 OpenCV DNN 模型"""
        # 尝试找到 ONNX 模型
        onnx_path = self.model_path.replace('.rknn', '.onnx')

        # 如果没有 ONNX，尝试下载或创建简单的检测器
        if not os.path.exists(onnx_path):
            logger.warning(f"ONNX 模型不存在: {onnx_path}")
            logger.warning("将使用模拟模式 - 随机生成检测结果用于测试")
            self.initialized = True  # 标记为初始化，但实际使用模拟
            self.simulation_mode = True
            return

        try:
            self.net = cv2.dnn.readNetFromONNX(onnx_path)
            self.net.setPreferableBackend(cv2.dnn.DNN_BACKEND_OPENCV)
            self.net.setPreferableTarget(cv2.dnn.DNN_TARGET_CPU)
            self.initialized = True
            self.simulation_mode = False
            logger.info(f"OpenCV DNN 模型加载成功: {onnx_path}")
        except Exception as e:
            logger.error(f"加载 ONNX 模型失败: {e}")
            self.simulation_mode = True
            self.initialized = True

    def preprocess(self, frame: np.ndarray) -> np.ndarray:
        """预处理图像"""
        img = cv2.resize(frame, self.input_size)
        blob = cv2.dnn.blobFromImage(img, 1/255.0, self.input_size, swapRB=True, crop=False)
        return blob

    def detect(self, frame: np.ndarray) -> List[Dict]:
        """检测目标"""
        if not self.initialized:
            return []

        # 模拟模式：随机生成检测结果用于测试
        if hasattr(self, 'simulation_mode') and self.simulation_mode:
            return self._simulate_detection(frame)

        try:
            blob = self.preprocess(frame)
            self.net.setInput(blob)
            outputs = self.net.forward()

            detections = self._parse_outputs(outputs, frame.shape)
            return detections

        except Exception as e:
            logger.error(f"CPU 检测失败: {e}")
            return []

    def _simulate_detection(self, frame: np.ndarray) -> List[Dict]:
        """模拟检测 - 用于测试"""
        import random
        import time
        random.seed(int(time.time() * 100) % 1000)

        detections = []
        h, w = frame.shape[:2]

        # 80% 概率检测到 person (提高概率以便测试)
        if random.random() < 0.8:
            # 随机位置
            cx = int(w * (0.3 + random.random() * 0.4))
            cy = int(h * (0.3 + random.random() * 0.4))
            bw = int(w * 0.2)
            bh = int(h * 0.3)
            x1 = max(0, cx - bw // 2)
            y1 = max(0, cy - bh // 2)
            x2 = min(w, cx + bw // 2)
            y2 = min(h, cy + bh // 2)
            detections.append({
                "class": 0,
                "label": "person",
                "category": "face",
                "confidence": 0.7 + random.random() * 0.25,
                "bbox": (x1, y1, x2, y2),
                "center": (cx, cy)
            })

        # 50% 概率检测到食物
        if random.random() < 0.5:
            foods = ["banana", "apple", "pizza", "cake"]
            food = random.choice(foods)
            cx = int(w * 0.2)
            cy = int(h * 0.7)
            x1 = max(0, cx - 50)
            y1 = max(0, cy - 50)
            x2 = min(w, cx + 50)
            y2 = min(h, cy + 50)
            detections.append({
                "class": self.COCO_NAMES.index(food) if food in self.COCO_NAMES else 46,
                "label": food,
                "category": "food",
                "confidence": 0.6 + random.random() * 0.3,
                "bbox": (x1, y1, x2, y2),
                "center": (cx, cy)
            })

        # 50% 概率检测到学习用品
        if random.random() < 0.5:
            learnings = ["book", "laptop", "cell phone"]
            item = random.choice(learnings)
            cx = int(w * 0.8)
            cy = int(h * 0.6)
            x1 = max(0, cx - 60)
            y1 = max(0, cy - 40)
            x2 = min(w, cx + 60)
            y2 = min(h, cy + 40)
            detections.append({
                "class": self.COCO_NAMES.index(item) if item in self.COCO_NAMES else 73,
                "label": item,
                "category": "learning",
                "confidence": 0.6 + random.random() * 0.3,
                "bbox": (x1, y1, x2, y2),
                "center": (cx, cy)
            })

        logger.info(f"[模拟模式] 生成 {len(detections)} 个模拟检测框: {[d['label'] for d in detections]}")

        return detections

    def _parse_outputs(self, outputs, orig_shape) -> List[Dict]:
        """解析模型输出"""
        detections = []
        h, w = orig_shape[:2]

        # 这里需要根据实际的 ONNX 模型输出格式调整
        # 简化版本：假设输出格式与 YOLOv5 类似
        for detection in outputs:
            scores = detection[5:]
            class_id = np.argmax(scores)
            confidence = scores[class_id]

            if confidence > self.conf_threshold:
                center_x = int(detection[0] * w)
                center_y = int(detection[1] * h)
                width = int(detection[2] * w)
                height = int(detection[3] * h)

                x1 = max(0, center_x - width // 2)
                y1 = max(0, center_y - height // 2)
                x2 = min(w, center_x + width // 2)
                y2 = min(h, center_y + height // 2)

                label = self.COCO_NAMES[class_id] if class_id < len(self.COCO_NAMES) else f"class_{class_id}"
                func_category = self._get_function_category(label)

                detections.append({
                    "class": class_id,
                    "label": label,
                    "category": func_category,
                    "confidence": float(confidence),
                    "bbox": (x1, y1, x2, y2),
                    "center": ((x1 + x2) // 2, (y1 + y2) // 2)
                })

        return self._nms(detections)

    def _get_function_category(self, label: str) -> str:
        """获取功能类别"""
        for category, items in self.category_map.items():
            if label in items:
                return category
        return "other"

    def _nms(self, detections: List[Dict]) -> List[Dict]:
        """非极大值抑制"""
        if len(detections) <= 1:
            return detections

        detections = sorted(detections, key=lambda x: x["confidence"], reverse=True)
        keep = []

        while len(detections) > 0:
            keep.append(detections[0])
            if len(detections) == 1:
                break

            current = detections[0]
            rest = detections[1:]
            detections = []

            for det in rest:
                iou = self._calculate_iou(current["bbox"], det["bbox"])
                if iou < self.iou_threshold:
                    detections.append(det)

        return keep

    def _calculate_iou(self, box1, box2):
        """计算 IOU"""
        x1_1, y1_1, x2_1, y2_1 = box1
        x1_2, y1_2, x2_2, y2_2 = box2

        xi1 = max(x1_1, x1_2)
        yi1 = max(y1_1, y1_2)
        xi2 = min(x2_1, x2_2)
        yi2 = min(y2_1, y2_2)

        inter_area = max(0, xi2 - xi1) * max(0, yi2 - yi1)
        box1_area = (x2_1 - x1_1) * (y2_1 - y1_1)
        box2_area = (x2_2 - x1_2) * (y2_2 - y1_2)
        union_area = box1_area + box2_area - inter_area

        return inter_area / union_area if union_area > 0 else 0

    def release(self):
        """释放资源"""
        self.net = None
        self.initialized = False
        logger.info("CPU 检测器已释放")
