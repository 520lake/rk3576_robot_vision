#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
YOLO 目标检测器 - 使用正确的 YOLOv5 后处理
"""

import cv2
import numpy as np
import logging
from typing import List, Dict, Tuple
from pathlib import Path

logger = logging.getLogger(__name__)

# 尝试导入 RKNN
try:
    from rknnlite.api import RKNNLite
    HAS_RKNN = True
except ImportError:
    HAS_RKNN = False
    logger.warning("RKNNLite not available, will use CPU fallback")


class YOLODetector:
    """YOLO 检测器 - 支持 NPU 和 CPU"""
    
    # COCO 类别名称
    COCO_NAMES = [
        "person", "bicycle", "car", "motorcycle", "airplane", "bus", "train", "truck", "boat",
        "traffic light", "fire hydrant", "stop sign", "parking meter", "bench", "bird", "cat",
        "dog", "horse", "sheep", "cow", "elephant", "bear", "zebra", "giraffe", "backpack",
        "umbrella", "handbag", "tie", "suitcase", "frisbee", "skis", "snowboard", "sports ball",
        "kite", "baseball bat", "baseball glove", "skateboard", "surfboard", "tennis racket",
        "bottle", "wine glass", "cup", "fork", "knife", "spoon", "bowl", "banana", "apple",
        "sandwich", "orange", "broccoli", "carrot", "hot dog", "pizza", "donut", "cake",
        "chair", "couch", "potted plant", "bed", "dining table", "toilet", "tv", "laptop",
        "mouse", "remote", "keyboard", "cell phone", "microwave", "oven", "toaster", "sink",
        "refrigerator", "book", "clock", "vase", "scissors", "teddy bear", "hair drier", "toothbrush"
    ]
    
    # 功能类别映射 (与 config.py 保持一致)
    CATEGORY_MAP = {
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
    
    # YOLOv5 anchors
    ANCHORS = np.array([
        [10, 13, 16, 30, 33, 23],
        [30, 61, 62, 45, 59, 119],
        [116, 90, 156, 198, 373, 326]
    ], dtype=np.float32).reshape(3, 3, 2)
    
    def __init__(self, model_path: str, input_size: Tuple[int, int] = (640, 640),
                 conf_threshold: float = 0.5, iou_threshold: float = 0.3,
                 min_box_size: int = 50):
        self.model_path = model_path
        self.input_size = input_size
        self.conf_threshold = conf_threshold
        self.iou_threshold = iou_threshold
        self.min_box_size = min_box_size
        
        self.rknn = None
        self.initialized = False
        
        self._load_model()
    
    def _load_model(self):
        """加载模型"""
        if not HAS_RKNN:
            logger.error("RKNNLite not available")
            return
        
        if not Path(self.model_path).exists():
            logger.error(f"Model not found: {self.model_path}")
            return
        
        logger.info(f"Loading RKNN model: {self.model_path}")
        
        self.rknn = RKNNLite()
        
        ret = self.rknn.load_rknn(self.model_path)
        if ret != 0:
            logger.error(f"Failed to load model: {ret}")
            return
        
        ret = self.rknn.init_runtime()
        if ret != 0:
            logger.error(f"Failed to init runtime: {ret}")
            return
        
        self.initialized = True
        logger.info("✓ RKNN model loaded successfully")
    
    def preprocess(self, frame: np.ndarray) -> np.ndarray:
        """预处理图像"""
        # Resize
        img = cv2.resize(frame, self.input_size)
        
        # BGR -> RGB
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        
        # Normalize to [0, 1]
        img = img.astype(np.float32) / 255.0
        
        # HWC -> CHW
        img = np.transpose(img, (2, 0, 1))
        
        # Add batch dimension
        img = np.expand_dims(img, axis=0)
        
        return img
    
    def detect(self, frame: np.ndarray) -> List[Dict]:
        """检测图像"""
        if not self.initialized or self.rknn is None:
            logger.warning("Detector not initialized")
            return []
        
        orig_h, orig_w = frame.shape[:2]
        
        # Preprocess
        input_data = self.preprocess(frame)
        
        # Inference
        outputs = self.rknn.inference(inputs=[input_data])
        
        # Postprocess
        detections = self.postprocess(outputs, (orig_w, orig_h))
        
        return detections
    
    def postprocess(self, outputs: List[np.ndarray], img_size: Tuple[int, int]) -> List[Dict]:
        """
        YOLOv5 后处理 - 使用正确的 anchor 解码
        """
        num_classes = 80
        prop_box_size = 5 + num_classes  # 85
        img_w, img_h = img_size
        model_w, model_h = 640.0, 640.0
        
        all_boxes = []
        all_scores = []
        all_cls = []
        
        for branch_idx, out in enumerate(outputs):
            if not isinstance(out, np.ndarray):
                out = np.array(out)
            
            out = np.squeeze(out)
            
            if out.ndim == 4:
                out = out[0]
            
            if out.ndim != 3:
                logger.warning(f"Unexpected output shape: {out.shape}")
                continue
            
            c, gh, gw = out.shape
            
            if c != prop_box_size * 3:  # 255 = 3 * 85
                logger.warning(f"Unexpected channels: {c}, expected {prop_box_size * 3}")
                continue
            
            stride = model_h / float(gh)
            branch_anchors = self.ANCHORS[branch_idx]
            
            for a in range(3):
                base_c = prop_box_size * a
                for iy in range(gh):
                    for ix in range(gw):
                        # 读取 box confidence
                        box_conf = float(out[base_c + 4, iy, ix])
                        
                        if box_conf < self.conf_threshold:
                            continue
                        
                        # 读取类别分数
                        cls_scores = out[base_c + 5 : base_c + 5 + num_classes, iy, ix]
                        cls_id = int(np.argmax(cls_scores))
                        cls_score = float(cls_scores[cls_id])
                        
                        # 最终置信度 = box_conf * cls_score
                        score = box_conf * cls_score
                        
                        if score < self.conf_threshold:
                            continue
                        
                        # 解码 bbox (YOLOv5 使用 sigmoid + anchor)
                        bx = float(out[base_c + 0, iy, ix])
                        by = float(out[base_c + 1, iy, ix])
                        bw = float(out[base_c + 2, iy, ix])
                        bh = float(out[base_c + 3, iy, ix])
                        
                        # Sigmoid activation
                        bx = 1.0 / (1.0 + np.exp(-bx))
                        by = 1.0 / (1.0 + np.exp(-by))
                        bw = 1.0 / (1.0 + np.exp(-bw))
                        bh = 1.0 / (1.0 + np.exp(-bh))
                        
                        # Decode
                        bx = (bx * 2.0 - 0.5 + float(ix)) * stride
                        by = (by * 2.0 - 0.5 + float(iy)) * stride
                        bw = (bw * 2.0) ** 2 * float(branch_anchors[a, 0])
                        bh = (bh * 2.0) ** 2 * float(branch_anchors[a, 1])
                        
                        # Convert to xyxy
                        x1 = bx - bw / 2.0
                        y1 = by - bh / 2.0
                        x2 = bx + bw / 2.0
                        y2 = by + bh / 2.0
                        
                        # Scale to original image
                        scale_x = img_w / model_w
                        scale_y = img_h / model_h
                        x1 *= scale_x
                        x2 *= scale_x
                        y1 *= scale_y
                        y2 *= scale_y
                        
                        all_boxes.append([x1, y1, x2, y2])
                        all_scores.append(score)
                        all_cls.append(cls_id)
        
        if not all_boxes:
            return []
        
        # NMS
        boxes_xyxy = np.array(all_boxes, dtype=np.float32)
        scores = np.array(all_scores, dtype=np.float32)
        cls_ids = np.array(all_cls, dtype=np.int32)
        
        keep = self._nms(boxes_xyxy, scores, self.iou_threshold)
        
        # Build results
        results = []
        for idx in keep:
            x1, y1, x2, y2 = boxes_xyxy[idx]
            score = scores[idx]
            cls_id = int(cls_ids[idx])
            
            # Filter small boxes
            w = x2 - x1
            h = y2 - y1
            if w < self.min_box_size or h < self.min_box_size:
                continue
            
            # Clamp to image bounds
            x1 = max(0, min(int(x1), img_w))
            y1 = max(0, min(int(y1), img_h))
            x2 = max(0, min(int(x2), img_w))
            y2 = max(0, min(int(y2), img_h))
            
            if x2 <= x1 or y2 <= y1:
                continue
            
            label = self.COCO_NAMES[cls_id] if cls_id < len(self.COCO_NAMES) else f"class_{cls_id}"
            category = self._get_category(label)
            
            results.append({
                "class": cls_id,
                "label": label,
                "category": category,
                "confidence": float(score),
                "bbox": (x1, y1, x2, y2),
                "center": ((x1 + x2) // 2, (y1 + y2) // 2)
            })
        
        return results
    
    def detect_face_only(self, frame: np.ndarray) -> List[Dict]:
        """
        只检测人脸（person类别），返回最置信的一个
        用于人脸跟踪模式
        """
        detections = self.detect(frame)
        
        # 只保留人脸（person类别）
        faces = [d for d in detections if d['label'] == 'person']
        
        if not faces:
            return []
        
        # 按置信度排序，返回最置信的一个
        faces = sorted(faces, key=lambda x: x['confidence'], reverse=True)
        return [faces[0]]  # 只返回一个最置信的人脸
    
    def _nms(self, boxes: np.ndarray, scores: np.ndarray, iou_thresh: float) -> List[int]:
        """非极大值抑制"""
        x1 = boxes[:, 0]
        y1 = boxes[:, 1]
        x2 = boxes[:, 2]
        y2 = boxes[:, 3]
        areas = (x2 - x1) * (y2 - y1)
        
        order = scores.argsort()[::-1]
        keep = []
        
        while order.size > 0:
            i = int(order[0])
            keep.append(i)
            
            if order.size == 1:
                break
            
            xx1 = np.maximum(x1[i], x1[order[1:]])
            yy1 = np.maximum(y1[i], y1[order[1:]])
            xx2 = np.minimum(x2[i], x2[order[1:]])
            yy2 = np.minimum(y2[i], y2[order[1:]])
            
            w = np.maximum(0.0, xx2 - xx1)
            h = np.maximum(0.0, yy2 - yy1)
            inter = w * h
            
            iou = inter / (areas[i] + areas[order[1:]] - inter + 1e-6)
            inds = np.where(iou <= iou_thresh)[0]
            order = order[inds + 1]
        
        return keep
    
    def _get_category(self, label: str) -> str:
        """获取功能类别"""
        for category, items in self.CATEGORY_MAP.items():
            if label in items:
                return category
        return "other"
    
    def release(self):
        """释放资源"""
        if self.rknn is not None:
            self.rknn.release()
            logger.info("RKNN model released")


if __name__ == "__main__":
    # Test
    import os
    logging.basicConfig(level=logging.INFO)
    
    # 获取项目根目录
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    model_path = os.path.join(base_dir, "models", "yolov5s_rk3576.rknn")
    
    detector = YOLODetector(
        model_path=model_path,
        conf_threshold=0.5,
        iou_threshold=0.3
    )
    
    if detector.initialized:
        print("✓ Detector initialized")
    else:
        print("✗ Failed to initialize detector")
