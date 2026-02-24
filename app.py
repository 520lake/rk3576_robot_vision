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
from flask import Flask, render_template, Response, jsonify, request

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
app.config['SECRET_KEY'] = 'rk3576-robot-vision'

# 全局组件
class RobotVisionSystem:
    def __init__(self):
        self.camera: Camera = None
        self.detector: YOLODetector = None
        self.servo: ServoController = None
        self.tracker: ObjectTracker = None
        
        self.is_running = False
        self.frame = None
        self.status = {"mode": "stopped", "message": "系统未启动"}
        self.lock = threading.Lock()
        
        # 显示设置
        self.show_detection = True
        self.show_fps = True
        
        # 模拟模式
        self.simulation_mode = False
        self.sim_frame_count = 0
        
    def initialize(self) -> bool:
        """初始化所有组件"""
        try:
            logger.info("=" * 50)
            logger.info("RK3576 机器人视觉系统初始化")
            logger.info("=" * 50)
            
            # 1. 初始化摄像头
            logger.info("[1/4] 初始化摄像头...")
            self.camera = Camera(
                camera_id=config.CAMERA_CONFIG["id"],
                width=config.CAMERA_CONFIG["width"],
                height=config.CAMERA_CONFIG["height"],
                fps=config.CAMERA_CONFIG["fps"]
            )
            if not self.camera.open():
                logger.warning("⚠ 摄像头初始化失败，使用模拟模式")
                self.simulation_mode = True
            else:
                self.simulation_mode = False
                logger.info("✓ 摄像头初始化成功")
            
            # 2. 初始化检测器 (NPU 优先，失败则使用 CPU)
            logger.info("[2/4] 初始化 YOLO 检测器...")
            self.detector = YOLODetector(
                model_path=config.MODEL_PATH,
                input_size=config.YOLO_CONFIG["input_size"],
                conf_threshold=config.YOLO_CONFIG["conf_threshold"],
                iou_threshold=config.YOLO_CONFIG["iou_threshold"],
                min_box_size=config.YOLO_CONFIG.get("min_box_size", 50)
            )
            if self.detector.initialized:
                logger.info("✓ YOLO NPU 检测器初始化成功")
            else:
                logger.warning("⚠ NPU 检测器初始化失败，尝试使用 CPU 检测器...")
                self.detector = YOLODetectorCPU(
                    model_path=config.MODEL_PATH,
                    input_size=config.YOLO_CONFIG["input_size"],
                    conf_threshold=config.YOLO_CONFIG["conf_threshold"],
                    iou_threshold=config.YOLO_CONFIG["iou_threshold"],
                    min_box_size=config.YOLO_CONFIG.get("min_box_size", 50)
                )
                if self.detector.initialized:
                    # 检查是否是模拟模式
                    if hasattr(self.detector, 'simulation_mode') and self.detector.simulation_mode:
                        logger.info("✓ YOLO CPU 检测器初始化成功 (模拟模式 - 将生成随机检测框)")
                        # 如果摄像头也失败了，使用完全模拟模式
                        if not self.camera.is_opened():
                            self.simulation_mode = True
                    else:
                        logger.info("✓ YOLO CPU 检测器初始化成功 (真实推理)")
                else:
                    logger.warning("⚠ CPU 检测器也未初始化")
                
            # 3. 初始化舵机控制器
            logger.info("[3/4] 初始化舵机控制器...")
            self.servo = ServoController(
                port=config.SERVO_CONFIG["port"],
                baudrate=config.SERVO_CONFIG["baudrate"],
                timeout=config.SERVO_CONFIG["timeout"]
            )
            if not self.servo.connect():
                logger.warning("⚠ 舵机控制器连接失败")
            else:
                logger.info("✓ 舵机控制器连接成功")
                
            # 4. 初始化跟踪器
            logger.info("[4/4] 初始化跟踪器...")
            self.tracker = ObjectTracker(
                servo_controller=self.servo,
                action_config=config.ACTION_CONFIG
            )
            logger.info("✓ 跟踪器初始化成功")
            
            self.is_running = True
            logger.info("=" * 50)
            logger.info("系统初始化完成！")
            logger.info("=" * 50)
            return True
            
        except Exception as e:
            logger.error(f"初始化失败: {e}")
            return False
            
    def process_frame(self):
        """处理视频帧的主循环 - 优化帧率"""
        frame_count = 0
        error_count = 0
        max_errors = 5
        
        # 跳帧参数：每 N 帧检测一次
        detect_interval = 3  # 每3帧检测一次，提高帧率
        last_detections = []
        last_detect_time = 0

        while self.is_running:
            try:
                if self.simulation_mode:
                    # 模拟模式：生成测试画面
                    frame = self._generate_simulation_frame()
                    self.status = {"mode": "simulation", "message": "Simulation Mode - Run on host for real camera", "fps": 30}
                else:
                    # 正常模式：读取摄像头帧
                    ret, frame = self.camera.read()
                    if not ret or frame is None:
                        time.sleep(0.001)  # 减少等待时间
                        continue

                    # 验证帧数据
                    if not isinstance(frame, np.ndarray) or frame.size == 0:
                        logger.warning("无效的帧数据")
                        time.sleep(0.001)
                        continue

                    # 目标检测 - 跳帧优化
                    detections = last_detections  # 默认使用上次的检测结果
                    current_time = time.time()
                    
                    if self.detector and self.detector.initialized:
                        # 每隔 detect_interval 帧或超过 100ms 没有检测时才检测
                        if frame_count % detect_interval == 0 or (current_time - last_detect_time) > 0.1:
                            try:
                                detections = self.detector.detect(frame)
                                last_detections = detections
                                last_detect_time = current_time
                                if frame_count % 90 == 0:  # 每90帧记录一次 (考虑跳帧)
                                    logger.info(f"Detection result: {len(detections)} objects")
                            except Exception as det_e:
                                logger.error(f"检测过程出错: {det_e}")
                                detections = last_detections  # 出错时使用上次结果
                    else:
                        if frame_count % 30 == 0:
                            logger.warning(f"Detector not ready: detector={self.detector}, initialized={self.detector.initialized if self.detector else False}")

                    # 更新跟踪器
                    target_to_draw = None
                    if self.tracker:
                        try:
                            self.status = self.tracker.update(detections, frame.shape)
                            # 获取当前跟踪的目标
                            if self.status.get("target"):
                                target_to_draw = self.status["target"]
                        except Exception as track_e:
                            logger.error(f"跟踪过程出错: {track_e}")

                    # 绘制检测结果 - 只绘制占画面比例最大的目标
                    if self.show_detection:
                        try:
                            best_target = None
                            
                            if detections:
                                # 计算每个检测框的面积（占画面比例）
                                frame_area = frame.shape[0] * frame.shape[1]
                                
                                def get_box_area(det):
                                    x1, y1, x2, y2 = det['bbox']
                                    return (x2 - x1) * (y2 - y1)
                                
                                # 按面积排序，选择最大的
                                best_target = max(detections, key=get_box_area)
                                
                            elif target_to_draw:
                                best_target = target_to_draw
                            
                            # 只绘制一个目标
                            if best_target:
                                frame = self._draw_single_detection(frame, best_target, True)
                                
                        except Exception as draw_e:
                            logger.error(f"绘制检测结果出错: {draw_e}")

                # 绘制状态信息
                if self.show_fps:
                    try:
                        frame = self._draw_status(frame)
                    except Exception as status_e:
                        logger.error(f"绘制状态信息出错: {status_e}")

                with self.lock:
                    self.frame = frame.copy() if isinstance(frame, np.ndarray) else frame

                frame_count += 1
                error_count = 0  # 重置错误计数

            except Exception as e:
                error_count += 1
                logger.error(f"处理帧出错 ({error_count}/{max_errors}): {e}")
                import traceback
                logger.error(traceback.format_exc())

                if error_count >= max_errors:
                    logger.error("连续错误次数过多，停止处理")
                    break

                time.sleep(0.01)
    
    def _generate_simulation_frame(self) -> np.ndarray:
        """生成模拟测试画面"""
        self.sim_frame_count += 1
        
        # 创建渐变背景
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        
        # 添加动态效果
        t = self.sim_frame_count % 100
        color_val = int(128 + 127 * np.sin(t * 0.1))
        
        # 绘制背景
        frame[:, :] = [color_val // 4, color_val // 3, color_val // 2]
        
        # 绘制网格
        for i in range(0, 640, 40):
            cv2.line(frame, (i, 0), (i, 480), (50, 50, 50), 1)
        for i in range(0, 480, 40):
            cv2.line(frame, (0, i), (640, i), (50, 50, 50), 1)
        
        # 绘制中心十字
        cx, cy = 320, 240
        cv2.line(frame, (cx - 30, cy), (cx + 30, cy), (0, 255, 0), 2)
        cv2.line(frame, (cx, cy - 30), (cx, cy + 30), (0, 255, 0), 2)
        
        # 绘制模拟人脸框（移动）
        offset_x = int(100 * np.sin(t * 0.05))
        offset_y = int(50 * np.cos(t * 0.03))
        face_x, face_y = cx + offset_x - 50, cy + offset_y - 50
        cv2.rectangle(frame, (face_x, face_y), (face_x + 100, face_y + 100), (255, 0, 0), 2)
        cv2.putText(frame, "person: 0.85", (face_x, face_y - 10), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 2)
        
        # 绘制文字
        cv2.putText(frame, "SIMULATION MODE", (180, 50), 
                   cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 255), 2)
        cv2.putText(frame, "Run on host for real camera", (150, 450), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (200, 200, 200), 1)
        
        return frame
                
    def _draw_single_detection(self, frame: np.ndarray, det: dict, is_target: bool = False) -> np.ndarray:
        """在帧上绘制单个检测结果 - 人脸使用精确框"""
        # 类别颜色映射 (BGR格式)
        colors = {
            "face": (0, 0, 255),      # 红色 - 人脸
            "food": (0, 255, 0),      # 绿色 - 食物
            "learning": (255, 0, 0),  # 蓝色 - 学习用品
            "other": (255, 255, 0),   # 青色 - 其他
        }
        
        x1, y1, x2, y2 = det["bbox"]
        label = det["label"]
        category = det.get("category", "other")
        conf = det["confidence"]
        
        color = colors.get(category, (128, 128, 128))
        
        # 如果是人脸，使用 tracker 估算的人脸框（更稳定）
        if category == "face" and label == "person":
            # 优先使用 tracker 保存的 face_bbox
            if "face_bbox" in det:
                x1, y1, x2, y2 = det["face_bbox"]
            else:
                # 如果没有，估算人脸位置
                face_height = int((y2 - y1) * 0.3)
                face_width = int((x2 - x1) * 0.5)
                face_center_y = y1 + int((y2 - y1) * 0.15)
                face_center_x = (x1 + x2) // 2
                x1 = face_center_x - face_width // 2
                y1 = face_center_y - face_height // 2
                x2 = face_center_x + face_width // 2
                y2 = face_center_y + face_height // 2
            # 更新 det 的 center 为人脸中心
            det["center"] = ((x1 + x2) // 2, (y1 + y2) // 2)
        
        # 使用细框（线条更细）
        thickness = 2 if is_target else 1
        
        # 绘制框
        cv2.rectangle(frame, (x1, y1), (x2, y2), color, thickness)
        
        # 如果是目标，绘制细的外发光效果
        if is_target:
            cv2.rectangle(frame, (x1-1, y1-1), (x2+1, y2+1), (255, 255, 255), 1)
        
        # 绘制标签背景
        text = f"{label}: {conf:.2f}"
        (text_w, text_h), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 2)
        cv2.rectangle(frame, (x1, y1 - text_h - 8), (x1 + text_w + 8, y1), color, -1)
        cv2.putText(frame, text, (x1 + 4, y1 - 4), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2)
        
        # 绘制中心点（只有目标才绘制）
        if is_target:
            cx, cy = det["center"]
            cv2.circle(frame, (cx, cy), 4, (0, 255, 255), -1)  # 小一点的中心点
            cv2.circle(frame, (cx, cy), 4, (0, 0, 0), 1)
        
        return frame
        
    def _draw_detections(self, frame: np.ndarray, detections: list) -> np.ndarray:
        """在帧上绘制所有检测结果（调试用）"""
        # 类别颜色映射 (BGR格式)
        colors = {
            "face": (0, 0, 255),      # 红色 - 人脸
            "food": (0, 255, 0),      # 绿色 - 食物
            "learning": (255, 0, 0),  # 蓝色 - 学习用品
            "other": (255, 255, 0),   # 青色 - 其他
        }
        
        for det in detections:
            x1, y1, x2, y2 = det["bbox"]
            label = det["label"]
            category = det.get("category", "other")
            conf = det["confidence"]
            
            color = colors.get(category, (128, 128, 128))
            
            # 绘制框
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
            
            # 绘制标签
            text = f"{label}: {conf:.2f}"
            (text_w, text_h), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 2)
            cv2.rectangle(frame, (x1, y1 - text_h - 10), (x1 + text_w, y1), color, -1)
            cv2.putText(frame, text, (x1, y1 - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2)
            
            # 绘制中心点
            cx, cy = det["center"]
            cv2.circle(frame, (cx, cy), 5, (0, 255, 255), -1)
            
        return frame
        
    def _draw_status(self, frame: np.ndarray) -> np.ndarray:
        """在帧上绘制状态信息 - 小字体透明背景"""
        # 状态信息
        mode = self.status.get("mode", "unknown")
        message = self.status.get("message", "")
        fps = self.status.get("fps", 0)
        
        # 模式英文映射 (OpenCV不支持中文)
        mode_names = {
            "idle": "IDLE",
            "face_tracking": "FACE",
            "face_lost": "LOST",
            "food_detected": "FOOD",
            "learning_detected": "LEARN",
            "other_detected": "OTHER",
            "action_pause": "PAUSE",
            "stopped": "STOP",
            "simulation": "SIM"
        }
        
        # 简化的状态文本
        status_text = f"{mode_names.get(mode, mode)} | {fps}FPS"
        
        # 小字体设置
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 0.4
        thickness = 1
        
        # 获取文本大小
        (text_w, text_h), _ = cv2.getTextSize(status_text, font, font_scale, thickness)
        
        # 位置：左上角，留小边距
        x, y = 10, 20
        padding = 4
        
        # 绘制半透明背景（使用叠加）
        overlay = frame.copy()
        bg_color = (0, 0, 0)
        alpha = 0.3  # 透明度
        
        cv2.rectangle(overlay, 
                     (x - padding, y - text_h - padding), 
                     (x + text_w + padding, y + padding), 
                     bg_color, -1)
        
        # 应用透明度
        cv2.addWeighted(overlay, alpha, frame, 1 - alpha, 0, frame)
        
        # 绘制文字（带阴影提高可读性）
        # 阴影
        cv2.putText(frame, status_text, (x+1, y+1), font, font_scale, (0, 0, 0), thickness)
        # 主文字
        cv2.putText(frame, status_text, (x, y), font, font_scale, (0, 255, 0), thickness)
        
        # 绘制中心十字线
        h, w = frame.shape[:2]
        cx, cy = w // 2, h // 2
        cv2.line(frame, (cx - 20, cy), (cx + 20, cy), (0, 255, 0), 1)
        cv2.line(frame, (cx, cy - 20), (cx, cy + 20), (0, 255, 0), 1)
        
        return frame
        
    def get_frame_bytes(self) -> bytes:
        """获取当前帧的 JPEG 字节"""
        with self.lock:
            if self.frame is None:
                # 创建空白帧
                blank = np.zeros((480, 640, 3), dtype=np.uint8)
                # 添加状态信息
                cv2.putText(blank, "NO CAMERA FEED", (120, 200),
                           cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
                cv2.putText(blank, f"Mode: {self.status.get('mode', 'unknown')}", (120, 250),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
                cv2.putText(blank, "Check camera connection", (120, 300),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 200), 1)
                ret, buffer = cv2.imencode('.jpg', blank)
                return buffer.tobytes() if ret else b""

            ret, buffer = cv2.imencode('.jpg', self.frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
            if not ret:
                logger.warning("JPEG encoding failed")
                return b""
            return buffer.tobytes()
            
    def shutdown(self):
        """关闭系统"""
        self.is_running = False
        
        if self.camera:
            self.camera.release()
        if self.detector:
            self.detector.release()
        if self.servo:
            self.servo.close()
            
        logger.info("系统已关闭")

# 创建全局系统实例
robot_system = RobotVisionSystem()

# ==================== Flask 路由 ====================

@app.route('/')
def index():
    """主页"""
    return render_template('index.html')

@app.route('/video_feed')
def video_feed():
    """视频流"""
    logger.info("Video feed requested")

    def generate():
        frame_count = 0
        last_log_time = time.time()

        while True:
            try:
                frame_bytes = robot_system.get_frame_bytes()
                if frame_bytes:
                    yield (b'--frame\r\n'
                           b'Content-Type: image/jpeg\r\n'
                           b'Cache-Control: no-cache\r\n'
                           b'\r\n' + frame_bytes + b'\r\n')
                    frame_count += 1

                    # 每5秒记录一次日志
                    current_time = time.time()
                    if current_time - last_log_time >= 5:
                        fps = frame_count / (current_time - last_log_time)
                        logger.info(f"Video stream: {fps:.1f} FPS, mode: {robot_system.status.get('mode', 'unknown')}")
                        frame_count = 0
                        last_log_time = current_time
                else:
                    logger.warning("No frame bytes available")

                time.sleep(0.033)  # ~30 FPS

            except Exception as e:
                logger.error(f"Video stream error: {e}")
                break

    return Response(generate(),
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
    logger.info(f"控制接口被调用: action={action}")
    
    if action == 'center':
        logger.info(f"回中心命令: servo={robot_system.servo}, initialized={robot_system.servo.initialized if robot_system.servo else False}")
        if robot_system.servo and robot_system.servo.initialized:
            result = robot_system.servo.center()
            logger.info(f"回中心结果: {result}")
            return jsonify({"success": result, "message": "舵机回到中心" if result else "舵机回中心失败"})
        else:
            logger.warning("舵机未初始化，无法回中心")
            return jsonify({"success": False, "message": "舵机未连接"})
        
    elif action == 'reset':
        if robot_system.tracker:
            robot_system.tracker.reset()
            return jsonify({"success": True, "message": "跟踪器已重置"})
        return jsonify({"success": False, "message": "跟踪器未初始化"})
        
    elif action == 'toggle_detection':
        robot_system.show_detection = not robot_system.show_detection
        status = "显示" if robot_system.show_detection else "隐藏"
        return jsonify({"success": True, "message": f"检测框已{status}"})
        
    elif action == 'action_nod':
        logger.info(f"点头动作: servo={robot_system.servo}, initialized={robot_system.servo.initialized if robot_system.servo else False}")
        if robot_system.servo and robot_system.servo.initialized:
            result = robot_system.servo.execute_action("head_nod", config.ACTION_CONFIG)
            return jsonify({"success": result, "message": "执行点头动作" if result else "动作执行失败"})
        return jsonify({"success": False, "message": "舵机未连接"})
        
    elif action == 'action_shake':
        logger.info(f"摇头动作: servo={robot_system.servo}, initialized={robot_system.servo.initialized if robot_system.servo else False}")
        if robot_system.servo and robot_system.servo.initialized:
            result = robot_system.servo.execute_action("head_shake", config.ACTION_CONFIG)
            return jsonify({"success": result, "message": "执行摇头动作" if result else "动作执行失败"})
        return jsonify({"success": False, "message": "舵机未连接"})
        
    elif action == 'action_roll':
        logger.info(f"转圈动作: servo={robot_system.servo}, initialized={robot_system.servo.initialized if robot_system.servo else False}")
        if robot_system.servo and robot_system.servo.initialized:
            result = robot_system.servo.execute_action("head_roll", config.ACTION_CONFIG)
            return jsonify({"success": result, "message": "执行转圈动作" if result else "动作执行失败"})
        return jsonify({"success": False, "message": "舵机未连接"})
        
    return jsonify({"success": False, "message": "未知动作"})

# ==================== 主程序 ====================

def main():
    """主函数"""
    # 初始化系统
    if not robot_system.initialize():
        logger.error("系统初始化失败，退出")
        return
        
    # 启动处理线程
    process_thread = threading.Thread(target=robot_system.process_frame, daemon=True)
    process_thread.start()
    
    try:
        # 启动 Flask 服务
        logger.info(f"启动 Web 服务: http://0.0.0.0:{config.FLASK_CONFIG['port']}")
        app.run(
            host=config.FLASK_CONFIG["host"],
            port=config.FLASK_CONFIG["port"],
            debug=config.FLASK_CONFIG["debug"],
            threaded=True,
            use_reloader=False
        )
    except KeyboardInterrupt:
        logger.info("收到退出信号")
    finally:
        robot_system.shutdown()

if __name__ == '__main__':
    main()
