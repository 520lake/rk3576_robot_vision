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
        self.current_x = 90  # 中心位置
        self.current_y = 70  # 中心位置
        
        # 角度限制
        self.x_min, self.x_max = 65, 115
        self.y_min, self.y_max = 20, 120
        self.x_center, self.y_center = 90, 70
        
        # 动作执行状态
        self.is_executing_action = False
        self.action_start_time = 0
        self.action_pause_duration = 3.0  # 动作后暂停时间
        
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
        """
        移动舵机头
        offset_x: X轴偏移 (-25 to 25)
        offset_y: Y轴偏移 (-50 to 50)
        delay_ms: 移动延迟
        """
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
        """
        执行动作序列
        action_name: 动作名称 (head_nod, head_shake, head_roll)
        action_config: 动作配置字典
        """
        logger.info(f"execute_action 被调用: {action_name}, initialized={self.initialized}, is_executing={self.is_executing_action}")
        
        if not self.initialized:
            logger.error("舵机未初始化，无法执行动作")
            return False
            
        if self.is_executing_action:
            logger.warning(f"动作正在执行中，忽略新动作: {action_name}")
            return False
            
        if action_name not in action_config:
            logger.warning(f"未知动作: {action_name}, 可用动作: {list(action_config.keys())}")
            return False
            
        action_sequence = action_config[action_name]
        logger.info(f"动作序列: {action_sequence}")
        
        def action_thread():
            try:
                self.is_executing_action = True
                self.action_start_time = time.time()
                
                logger.info(f"开始执行动作: {action_name}")
                
                for i, step in enumerate(action_sequence):
                    x = step.get("x", 0)
                    y = step.get("y", 0)
                    delay = step.get("delay", 100)
                    
                    logger.info(f"  动作步骤 {i+1}/{len(action_sequence)}: x={x}, y={y}, delay={delay}ms")
                    self.head_move(x, y, 3)
                    time.sleep(delay / 1000.0)  # 转换为秒
                    
                logger.info(f"动作 {action_name} 执行完成，回到中心位置")
                # 动作完成后回到中心位置
                self.center()
            except Exception as e:
                logger.error(f"动作执行异常: {e}")
            finally:
                # 确保状态被重置
                self.is_executing_action = False
                logger.info(f"动作状态已重置")
            
        # 启动动作线程
        thread = threading.Thread(target=action_thread, daemon=True)
        thread.start()
        logger.info(f"动作线程已启动: {action_name}")
        return True
        
    def is_action_running(self) -> bool:
        """检查是否正在执行动作"""
        if not self.is_executing_action:
            return False
            
        # 检查动作是否超时
        elapsed = time.time() - self.action_start_time
        if elapsed > self.action_pause_duration:
            self.is_executing_action = False
            return False
            
        return True
        
    def get_pause_remaining(self) -> float:
        """获取动作暂停剩余时间"""
        if not self.is_executing_action:
            return 0.0
        elapsed = time.time() - self.action_start_time
        return max(0, self.action_pause_duration - elapsed)
        
    def look_at(self, screen_x: int, screen_y: int, screen_width: int = 640, screen_height: int = 480,
                dead_zone: int = 40, gain_x: float = 0.08, gain_y: float = 0.10) -> bool:
        """
        看向屏幕上的某个位置
        screen_x, screen_y: 目标位置（像素坐标）
        screen_width, screen_height: 屏幕尺寸
        dead_zone: 死区（像素）
        gain_x, gain_y: 增益系数
        """
        if not self.initialized:
            return False
            
        # 计算相对于中心的偏移
        center_x = screen_width // 2
        center_y = screen_height // 2
        
        offset_x = screen_x - center_x
        offset_y = screen_y - center_y
        
        # 死区过滤
        if abs(offset_x) < dead_zone:
            offset_x = 0
        if abs(offset_y) < dead_zone:
            offset_y = 0
            
        # 转换为角度
        angle_x = int(offset_x * gain_x)
        angle_y = int(offset_y * gain_y)
        
        return self.head_move(angle_x, angle_y)
        
    def is_connected(self) -> bool:
        """检查是否已连接"""
        return self.initialized and self.serial is not None and self.serial.is_open

    def close(self):
        """关闭连接"""
        if self.serial:
            try:
                self.center()  # 回到中心位置
                time.sleep(0.5)
                self.serial.close()
            except:
                pass
            self.serial = None
            self.initialized = False
            logger.info("舵机控制器已关闭")
