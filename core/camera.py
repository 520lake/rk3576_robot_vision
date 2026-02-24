# -*- coding: utf-8 -*-
"""
摄像头模块 - 支持多索引尝试和 MJPEG 格式
"""

import cv2
import logging
import threading
import time
from typing import Optional, Tuple
import numpy as np

logger = logging.getLogger(__name__)


class Camera:
    """摄像头类，支持多索引尝试"""
    
    def __init__(self, camera_id: int = 0, width: int = 640, height: int = 480, fps: int = 30):
        self.camera_id = camera_id
        self.width = width
        self.height = height
        self.fps = fps
        self.cap: Optional[cv2.VideoCapture] = None
        self._lock = threading.Lock()
        self._running = False
        self._frame = None
        self._thread: Optional[threading.Thread] = None
        
    def open(self) -> bool:
        """打开摄像头，尝试多个索引"""
        if self.cap and self.cap.isOpened():
            return True

        # 尝试多个摄像头索引
        camera_ids = [self.camera_id, 33, 0, 1, 2, 34, 35, 36, 37]

        for cam_id in camera_ids:
            try:
                logger.info(f"尝试打开摄像头 {cam_id}...")
                
                # 尝试不同的后端
                for backend in [cv2.CAP_V4L2, cv2.CAP_ANY]:
                    try:
                        self.cap = cv2.VideoCapture(cam_id, backend)
                        
                        if self.cap.isOpened():
                            # 等待摄像头初始化
                            time.sleep(0.5)
                            
                            # 先清除缓冲区
                            for _ in range(5):
                                self.cap.read()
                            
                            # 设置分辨率
                            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
                            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
                            self.cap.set(cv2.CAP_PROP_FPS, self.fps)
                            
                            # 读取一帧测试
                            ret, frame = self.cap.read()
                            if ret and frame is not None and frame.size > 0:
                                actual_width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                                actual_height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                                logger.info(f"摄像头 {cam_id} 打开成功，分辨率: {actual_width}x{actual_height}")
                                self.camera_id = cam_id
                                self._running = True
                                self._thread = threading.Thread(target=self._capture_loop, daemon=True)
                                self._thread.start()
                                return True
                            else:
                                self.cap.release()
                                time.sleep(0.1)
                    except Exception as e:
                        logger.debug(f"摄像头 {cam_id} 使用后端 {backend} 失败: {e}")
                        if self.cap:
                            self.cap.release()

            except Exception as e:
                logger.warning(f"摄像头 {cam_id} 打开失败: {e}")
                if self.cap:
                    self.cap.release()

        logger.error("无法打开任何摄像头")
        return False
        
    def _capture_loop(self):
        """后台捕获线程"""
        consecutive_errors = 0
        max_errors = 10

        while self._running:
            if self.cap and self.cap.isOpened():
                try:
                    ret, frame = self.cap.read()
                    if ret and frame is not None:
                        # 水平翻转图像（解决镜像问题）
                        frame = cv2.flip(frame, 1)
                        with self._lock:
                            self._frame = frame
                        consecutive_errors = 0
                    else:
                        consecutive_errors += 1
                        if consecutive_errors >= max_errors:
                            logger.error("摄像头读取连续失败，停止捕获")
                            break
                except Exception as e:
                    logger.error(f"摄像头读取异常: {e}")
                    consecutive_errors += 1
                    if consecutive_errors >= max_errors:
                        break
            time.sleep(0.001)
            
    def read(self) -> Tuple[bool, Optional[np.ndarray]]:
        """读取当前帧"""
        with self._lock:
            if self._frame is not None:
                return True, self._frame.copy()
            return False, None
            
    def is_opened(self) -> bool:
        """检查摄像头是否打开"""
        return self.cap is not None and self.cap.isOpened() and self._running
        
    def release(self):
        """释放摄像头资源"""
        self._running = False
        if self._thread:
            self._thread.join(timeout=1.0)
        if self.cap:
            self.cap.release()
            self.cap = None
        logger.info("摄像头已释放")
        
    def __enter__(self):
        self.open()
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()
