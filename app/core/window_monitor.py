# -*- coding: utf-8 -*-
"""
窗口状态监控器
每10秒检测一次窗口状态，识别异常窗口
"""

import time
import os
import win32gui
import cv2
from PyQt6.QtCore import QThread, pyqtSignal

# 获取脚本目录
SCRIPT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class WindowMonitor(QThread):
    """窗口状态监控器（10秒检测）"""

    # 信号
    status_update = pyqtSignal(list)  # 状态列表更新
    window_exception = pyqtSignal(int, str)  # 窗口异常 (hwnd, exception_type)
    all_windows_offline = pyqtSignal()  # 所有窗口异常

    def __init__(self, hwnds: list, engine, config_manager, logger):
        """
        初始化窗口监控器

        Args:
            hwnds: 窗口句柄列表
            engine: 游戏引擎
            config_manager: 配置管理器
            logger: 日志记录器
        """
        super().__init__()
        self.all_hwnds = hwnds.copy()
        self.active_hwnds = hwnds.copy()  # 活跃窗口
        self.engine = engine
        self.config_manager = config_manager
        self.logger = logger

        # 获取监控配置
        monitor_config = config_manager.get_user_config('window_monitor', {})
        self.check_interval = monitor_config.get('check_interval', 10)  # 检测间隔（秒）
        self.auto_recovery = monitor_config.get('auto_recovery', True)

        self.running = True
        self.paused = False

        # 窗口状态
        self.window_states = {}
        for hwnd in hwnds:
            self.window_states[hwnd] = {
                'hwnd': hwnd,
                'status': 'online',
                'last_check': time.time(),
                'exception_count': 0
            }

        # 异常类型定义
        self.exception_types = {
            'offline': '网络掉线',
            'crashed': '窗口崩溃',
            'not_responding': '窗口无响应'
        }

    def run(self):
        """监控循环"""
        self.logger.log(0, "INFO", f"窗口监控启动，检测间隔: {self.check_interval}秒")

        while self.running:
            try:
                if not self.paused:
                    self.check_all_windows()

                # 发送状态更新
                self.status_update.emit(list(self.window_states.values()))

                # 等待下一次检测
                time.sleep(self.check_interval)
            except Exception as e:
                self.logger.log(0, "ERROR", f"监控循环异常: {e}")
                time.sleep(1)

    def check_all_windows(self):
        """检查所有窗口"""
        offline_count = 0

        for hwnd in self.all_hwnds:
            state = self.window_states.get(hwnd, {})
            exception_type = None

            # 1. 检查窗口是否崩溃
            if not win32gui.IsWindow(hwnd):
                exception_type = 'crashed'
            elif self.check_window_offline(hwnd):
                exception_type = 'offline'

            # 2. 处理异常
            if exception_type:
                if state.get('status') != exception_type:
                    # 新检测到的异常
                    self.logger.log(0, "WARN", f"窗口 {hwnd} 异常: {self.exception_types[exception_type]}")
                    if self.auto_recovery:
                        self.window_exception.emit(hwnd, exception_type)
                    else:
                        self.logger.log(0, "INFO", "自动恢复已禁用，跳过恢复")

                state['status'] = exception_type
                state['exception_count'] += 1
                state['last_check'] = time.time()
                offline_count += 1

                # 从活跃窗口中移除
                if hwnd in self.active_hwnds:
                    self.active_hwnds.remove(hwnd)
            else:
                # 窗口正常
                if state.get('status') != 'online':
                    self.logger.log(0, "INFO", f"窗口 {hwnd} 已恢复")
                    state['status'] = 'online'
                    state['exception_count'] = 0

                    # 重新加入活跃窗口
                    if hwnd not in self.active_hwnds:
                        self.active_hwnds.append(hwnd)

        # 3. 检查是否全部异常
        if offline_count == len(self.all_hwnds):
            self.logger.log(0, "ERROR", "所有窗口都异常！")
            self.all_windows_offline.emit()

    def check_window_offline(self, hwnd: int) -> bool:
        """
        检测窗口是否掉线

        Args:
            hwnd: 窗口句柄

        Returns:
            是否掉线
        """
        # 检查掉线特征图
        offline_images = [
            'reconnect_btn.png',
            'back_to_lobby.png',
            'offline_msg.png'
        ]

        for img_name in offline_images:
            img_path = self.config_manager.get_template_path(img_name)
            if img_path:
                found, _, _ = self.engine.match_template(hwnd, img_path, threshold=0.8)
                if found:
                    return True
        return False

    def mark_recovered(self, hwnd: int):
        """
        标记窗口已恢复

        Args:
            hwnd: 窗口句柄
        """
        if hwnd in self.window_states:
            self.window_states[hwnd]['status'] = 'online'
            self.window_states[hwnd]['exception_count'] = 0

    def update_hwnds(self, hwnds: list):
        """
        更新窗口列表（用于窗口重启后）

        Args:
            hwnds: 新的窗口句柄列表
        """
        self.all_hwnds = hwnds.copy()
        self.active_hwnds = hwnds.copy()

        # 重新初始化状态
        self.window_states = {}
        for hwnd in hwnds:
            self.window_states[hwnd] = {
                'hwnd': hwnd,
                'status': 'online',
                'last_check': time.time(),
                'exception_count': 0
            }

        self.logger.log(0, "INFO", f"窗口列表已更新，共 {len(hwnds)} 个窗口")

    def pause(self):
        """暂停监控"""
        self.paused = True
        self.logger.log(0, "INFO", "窗口监控已暂停")

    def resume(self):
        """恢复监控"""
        self.paused = False
        self.logger.log(0, "INFO", "窗口监控已恢复")

    def stop(self):
        """停止监控"""
        self.running = False
        self.logger.log(0, "INFO", "窗口监控已停止")

    def get_online_hwnds(self) -> list:
        """获取在线窗口列表"""
        return [hwnd for hwnd in self.all_hwnds
                if self.window_states.get(hwnd, {}).get('status') == 'online']

    def get_offline_hwnds(self) -> list:
        """获取离线窗口列表"""
        return [hwnd for hwnd in self.all_hwnds
                if self.window_states.get(hwnd, {}).get('status') != 'online']
