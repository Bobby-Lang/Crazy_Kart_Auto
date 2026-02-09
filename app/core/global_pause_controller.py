# -*- coding: utf-8 -*-
"""
全局暂停控制器
负责控制全局暂停状态，处理异常情况
"""

import threading


class GlobalPauseController:
    """全局暂停控制器"""

    def __init__(self, logger):
        """
        初始化暂停控制器

        Args:
            logger: 日志记录器
        """
        self.is_paused = False
        self.is_running = True
        self.pause_reason = None
        self.exception_hwnds = []  # 异常窗口句柄列表
        self.logger = logger
        self.pause_lock = threading.Lock()

    def pause_for_exception(self, hwnd: int, exception_type: str):
        """
        因异常暂停全局

        Args:
            hwnd: 异常窗口句柄
            exception_type: 异常类型
        """
        with self.pause_lock:
            self.is_paused = True
            self.pause_reason = exception_type
            if hwnd not in self.exception_hwnds:
                self.exception_hwnds.append(hwnd)

        self.logger.log(0, "WARN", f"检测到异常: 窗口 {hwnd} ({exception_type})，全局暂停")

    def pause_manual(self):
        """手动暂停"""
        with self.pause_lock:
            self.is_paused = True
            self.pause_reason = "manual"

        self.logger.log(0, "INFO", "手动暂停运行")

    def resume_if_all_recovered(self) -> bool:
        """
        如果所有异常都恢复，则恢复全局

        Returns:
            是否恢复
        """
        with self.pause_lock:
            if len(self.exception_hwnds) == 0 and self.pause_reason != "manual":
                self.is_paused = False
                self.pause_reason = None
                self.logger.log(0, "INFO", "所有窗口恢复正常，继续运行")
                return True
        return False

    def resume_manual(self):
        """手动恢复"""
        with self.pause_lock:
            self.is_paused = False
            self.pause_reason = None

        self.logger.log(0, "INFO", "手动恢复运行")

    def is_all_windows_offline(self, total_windows: int) -> bool:
        """
        检查是否所有窗口都异常

        Args:
            total_windows: 总窗口数

        Returns:
            是否所有窗口都异常
        """
        with self.pause_lock:
            return len(self.exception_hwnds) >= total_windows

    def remove_exception(self, hwnd: int):
        """
        移除异常窗口

        Args:
            hwnd: 窗口句柄
        """
        with self.pause_lock:
            if hwnd in self.exception_hwnds:
                self.exception_hwnds.remove(hwnd)
                self.logger.log(0, "INFO", f"窗口 {hwnd} 异常已移除")

    def update_exception_hwnd(self, old_hwnd: int, new_hwnd: int):
        """
        更新异常窗口句柄（用于窗口重启后）

        Args:
            old_hwnd: 旧窗口句柄
            new_hwnd: 新窗口句柄
        """
        with self.pause_lock:
            if old_hwnd in self.exception_hwnds:
                self.exception_hwnds.remove(old_hwnd)
                self.exception_hwnds.append(new_hwnd)
                self.logger.log(0, "INFO", f"更新异常句柄: {old_hwnd} → {new_hwnd}")

    def get_status(self) -> dict:
        """
        获取当前状态

        Returns:
            状态字典
        """
        with self.pause_lock:
            return {
                'is_paused': self.is_paused,
                'is_running': self.is_running,
                'pause_reason': self.pause_reason,
                'exception_count': len(self.exception_hwnds),
                'exception_hwnds': self.exception_hwnds.copy()
            }

    def stop(self):
        """停止运行"""
        with self.pause_lock:
            self.is_running = False
            self.logger.log(0, "WARN", "全局停止信号已发出")
