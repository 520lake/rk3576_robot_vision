# -*- coding: utf-8 -*-
"""
目标跟踪模块 - 人脸优先 + 物品识别控制舵机
"""

import time
import logging
from typing import Dict, List, Optional, Tuple
from collections import deque

logger = logging.getLogger(__name__)


class ObjectTracker:
    """
    目标跟踪器
    策略：
    1. 优先跟踪人脸
    2. 无人脸时识别物品并执行动作
    3. 动作执行期间暂停跟踪
    """
    
    def __init__(self, servo_controller, action_config: Dict):
        self.servo = servo_controller
        self.action_config = action_config
        
        # 跟踪状态
        self.target_face: Optional[Dict] = None
        self.last_face_time = 0
        self.face_lost_threshold = 0.5  # 人脸丢失阈值（秒）
        
        # 平滑滤波
        self.smooth_x = 320  # 画面中心
        self.smooth_y = 240
        self.alpha = 0.3  # 平滑系数
        
        # 死区
        self.dead_zone = 40
        
        # 增益
        self.gain_x = 0.08
        self.gain_y = 0.10
        
        # 最近检测到的物品类别
        self.last_detected_category = None
        self.category_cooldown = 3.0  # 物品检测冷却时间（减少到3秒）
        self.last_category_time = 0
        self.action_pause_duration = action_config.get("pause_duration", 3.0)
        
        # 统计信息
        self.frame_count = 0
        self.last_fps_time = time.time()
        self.fps = 0
        
    def update(self, detections: List[Dict], frame_shape: Tuple) -> Dict:
        """
        更新跟踪状态并控制舵机
        返回状态信息字典
        """
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
            
        # 分离人脸和其他物品
        faces = [d for d in detections if d.get("category") == "face"]
        foods = [d for d in detections if d.get("category") == "food"]
        learnings = [d for d in detections if d.get("category") == "learning"]
        others = [d for d in detections if d.get("category") == "other"]
        
        # 调试：打印检测统计
        if faces or foods or learnings or others:
            logger.info(f"Detection stats - faces:{len(faces)} foods:{len(foods)} learnings:{len(learnings)} others:{len(others)}")
            for f in faces[:2]:
                logger.info(f"  Face: {f['label']} conf={f['confidence']:.2f}")
            for item in (foods + learnings + others)[:2]:
                logger.info(f"  Item: {item['label']}({item['category']}) conf={item['confidence']:.2f}")
        
        # 策略 1: 优先跟踪人脸
        if faces:
            # 选择最佳人脸
            self.target_face = self._select_best_face(faces)
            self.last_face_time = current_time
            
            # 跟踪人脸
            if self.target_face:
                # 使用原始 person 框的中心进行跟踪（更稳定）
                # 但计算一个缩小的人脸区域用于显示
                x1, y1, x2, y2 = self.target_face['bbox']
                
                # 估算人脸位置（用于显示）
                face_height = int((y2 - y1) * 0.3)  # 人脸占人体高度的30%
                face_width = int((x2 - x1) * 0.5)   # 人脸占人体宽度的50%
                face_center_y = y1 + int((y2 - y1) * 0.15)  # 人脸中心在人体顶部15%处
                face_center_x = (x1 + x2) // 2
                
                face_x1 = face_center_x - face_width // 2
                face_y1 = face_center_y - face_height // 2
                face_x2 = face_center_x + face_width // 2
                face_y2 = face_center_y + face_height // 2
                
                # 保存估算的人脸框用于显示
                self.target_face['face_bbox'] = (face_x1, face_y1, face_x2, face_y2)
                
                # 使用人体框中心进行跟踪（更稳定）
                person_center_x = (x1 + x2) // 2
                person_center_y = (y1 + y2) // 2
                
                # 创建跟踪用的目标（使用人体中心）
                track_target = self.target_face.copy()
                track_target['center'] = (person_center_x, person_center_y)
                
                # 跟踪人脸
                self.alpha = 0.4  # 平滑系数
                self._track_target(track_target, frame_shape)
                status["mode"] = "face_tracking"
                status["target"] = self.target_face
                status["message"] = f"Face: {self.target_face['confidence']:.2f}"
                logger.info(f"Tracking face: person_center=({person_center_x},{person_center_y}), face_bbox=({face_x1},{face_y1},{face_x2},{face_y2})")
                return status
                
        # 检查人脸是否刚丢失
        elif current_time - self.last_face_time < self.face_lost_threshold:
            # 继续跟踪最后的位置
            if self.target_face:
                status["mode"] = "face_lost"
                status["message"] = "Face lost, holding position"
                return status
                
        # 策略 2: 无人脸时识别物品并执行动作
        cooldown_remaining = self.category_cooldown - (current_time - self.last_category_time)
        logger.info(f"物品检测检查: foods={len(foods)}, learnings={len(learnings)}, others={len(others)}, cooldown={cooldown_remaining:.1f}s")
        
        if current_time - self.last_category_time > self.category_cooldown:
            action_executed = False
            
            # 优先级: food > learning > other
            if foods:
                best_food = max(foods, key=lambda x: x["confidence"])
                logger.info(f"尝试执行食物动作: {best_food['label']} conf={best_food['confidence']:.2f}")
                if self._execute_category_action("food", best_food):
                    status["mode"] = "food_detected"
                    status["target"] = best_food
                    status["action"] = "head_nod"
                    status["message"] = f"检测到食物: {best_food['label']}，执行点头"
                    action_executed = True
                else:
                    logger.warning("食物动作执行失败")
                    
            elif learnings:
                best_learning = max(learnings, key=lambda x: x["confidence"])
                logger.info(f"尝试执行学习用品动作: {best_learning['label']} conf={best_learning['confidence']:.2f}")
                if self._execute_category_action("learning", best_learning):
                    status["mode"] = "learning_detected"
                    status["target"] = best_learning
                    status["action"] = "head_shake"
                    status["message"] = f"检测到学习用品: {best_learning['label']}，执行摇头"
                    action_executed = True
                else:
                    logger.warning("学习用品动作执行失败")
                    
            elif others:
                best_other = max(others, key=lambda x: x["confidence"])
                logger.info(f"尝试执行其他物品动作: {best_other['label']} conf={best_other['confidence']:.2f}")
                if self._execute_category_action("other", best_other):
                    status["mode"] = "other_detected"
                    status["target"] = best_other
                    status["action"] = "head_roll"
                    status["message"] = f"检测到其他物品: {best_other['label']}，执行转圈"
                    action_executed = True
                else:
                    logger.warning("其他物品动作执行失败")
                    
            if action_executed:
                return status
        else:
            logger.info(f"物品检测冷却中，还需等待 {cooldown_remaining:.1f} 秒")
                
        # 没有检测到任何目标
        status["mode"] = "idle"
        status["message"] = "等待目标..."
        return status
        
    def _select_best_face(self, faces: List[Dict]) -> Optional[Dict]:
        """选择最佳人脸（最大、最居中、置信度最高）"""
        if not faces:
            return None
        
        # 首先选择置信度最高的人脸
        faces = sorted(faces, key=lambda x: x["confidence"], reverse=True)
        
        # 如果最高置信度的人脸置信度 > 0.7，直接选择
        if faces[0]["confidence"] > 0.7:
            return faces[0]
        
        # 否则综合考虑面积和位置
        scored_faces = []
        for face in faces:
            x1, y1, x2, y2 = face["bbox"]
            area = (x2 - x1) * (y2 - y1)
            center_x = (x1 + x2) // 2
            center_y = (y1 + y2) // 2
            
            # 距离画面中心的距离（归一化）
            dist_to_center = ((center_x - 320) ** 2 + (center_y - 240) ** 2) ** 0.5
            max_dist = (320**2 + 240**2) ** 0.5
            center_score = 1 - (dist_to_center / max_dist)
            
            # 综合得分：置信度 * 0.5 + 居中程度 * 0.3 + 面积 * 0.2
            area_score = min(area / 100000, 1.0)  # 归一化面积
            score = face["confidence"] * 0.5 + center_score * 0.3 + area_score * 0.2
            
            scored_faces.append((score, face))
        
        # 返回得分最高的
        scored_faces.sort(key=lambda x: x[0], reverse=True)
        return scored_faces[0][1]
        
    def _track_target(self, target: Dict, frame_shape: Tuple):
        """跟踪目标并控制舵机 - 优化稳定性"""
        if not self.servo or not self.servo.initialized:
            return
            
        center_x, center_y = target["center"]
        
        # 自适应平滑系数：人脸置信度高时用高响应，低时用高平滑
        confidence = target.get("confidence", 0.5)
        if confidence > 0.7:
            alpha = 0.6  # 高置信度，快速响应
        elif confidence > 0.5:
            alpha = 0.4  # 中等置信度
        else:
            alpha = 0.25  # 低置信度，高平滑
        
        # 平滑滤波
        self.smooth_x = alpha * center_x + (1 - alpha) * self.smooth_x
        self.smooth_y = alpha * center_y + (1 - alpha) * self.smooth_y
        
        # 计算偏移
        frame_center_x = frame_shape[1] // 2
        frame_center_y = frame_shape[0] // 2
        
        offset_x = int(self.smooth_x - frame_center_x)
        offset_y = int(self.smooth_y - frame_center_y)
        
        # 死区过滤（动态死区）
        dynamic_dead_zone = int(self.dead_zone * (1 - confidence * 0.5))  # 置信度高时死区小
        if abs(offset_x) < dynamic_dead_zone:
            offset_x = 0
        if abs(offset_y) < dynamic_dead_zone:
            offset_y = 0
            
        # 转换为角度
        angle_x = int(offset_x * self.gain_x)
        angle_y = int(offset_y * self.gain_y)
        
        # 限制角度范围
        angle_x = max(-25, min(25, angle_x))
        angle_y = max(-50, min(50, angle_y))
        
        # 发送舵机命令
        self.servo.head_move(angle_x, angle_y)
        
    def _execute_category_action(self, category: str, detection: Dict) -> bool:
        """执行类别对应的动作"""
        if not self.servo or not self.servo.initialized:
            return False
            
        # 映射类别到动作
        action_map = {
            "food": "head_nod",
            "learning": "head_shake",
            "other": "head_roll"
        }
        
        action_name = action_map.get(category)
        if not action_name:
            return False
            
        # 执行动作
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
