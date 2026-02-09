# -*- coding: utf-8 -*-
"""
简单日志记录器
用于替代print，支持带hwnd的日志输出
"""

import time
import os
import threading
import sys


class SimpleLogger:
    """简单日志记录器"""

    def __init__(self, log_callback=None):
        """
        初始化日志记录器

        Args:
            log_callback: 日志回调函数，参数为 (hwnd, level, message)
        """
        self.log_callback = log_callback
        self.lock = threading.Lock()

    def log(self, hwnd: int, level: str, message: str):
        """
        记录日志

        Args:
            hwnd: 窗口句柄（0表示系统级日志）
            level: 日志级别（INFO, WARN, ERROR）
            message: 日志消息
        """
        timestamp = time.strftime("%H:%M:%S")

        # 格式化消息
        if hwnd == 0:
            formatted_msg = f"[{timestamp}] [{level}] {message}"
        else:
            formatted_msg = f"[{timestamp}] [{hwnd}] [{level}] {message}"

        # 调用回调（如果有）
        if self.log_callback:
            try:
                self.log_callback(hwnd, level, message)
            except:
                pass

        # 控制台输出（处理中文编码）
        try:
            print(formatted_msg)
        except UnicodeEncodeError:
            # 如果编码失败，使用ASCII替代
            ascii_msg = formatted_msg.encode('ascii', 'replace').decode('ascii')
            print(ascii_msg)

    def info(self, hwnd: int, message: str):
        """记录INFO级别日志"""
        self.log(hwnd, "INFO", message)

    def warn(self, hwnd: int, message: str):
        """记录WARN级别日志"""
        self.log(hwnd, "WARN", message)

    def warning(self, hwnd: int, message: str):
        """记录WARNING级别日志（别名）"""
        self.log(hwnd, "WARN", message)

    def error(self, hwnd: int, message: str):
        """记录ERROR级别日志"""
        self.log(hwnd, "ERROR", message)

    def debug(self, hwnd: int, message: str):
        """记录DEBUG级别日志"""
        self.log(hwnd, "DEBUG", message)


# 全局日志实例
_global_logger = None


def set_global_logger(logger):
    """设置全局日志记录器"""
    global _global_logger
    _global_logger = logger


def get_logger() -> SimpleLogger:
    """获取全局日志记录器"""
    return _global_logger or SimpleLogger()


if __name__ == "__main__":
    # 测试日志
    logger = SimpleLogger()
    logger.info(0, "测试INFO日志")
    logger.warn(0, "测试WARN日志")
    logger.error(0, "测试ERROR日志")
    logger.info(0, "测试中文: 游戏自动化工具有效 ✓")
