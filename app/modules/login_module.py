# -*- coding: utf-8 -*-
import time
import os
import json
import sys
import win32con
import win32gui
from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtWidgets import QApplication

# 确保能找到 core 和 logger
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import GameEngine, ConfigManager
from logger import SimpleLogger

class LoginModule(QThread):
    log_signal = pyqtSignal(int, str, str)
    progress_update = pyqtSignal(int, str)
    login_complete = pyqtSignal(int, int, dict, bool)

    def __init__(self, hwnd_list: list, config_manager: ConfigManager, logger: SimpleLogger):
        super().__init__()
        self.hwnd_list = hwnd_list
        self.config_manager = config_manager
        self.logger = logger
        self.engine = GameEngine(config_manager)
        self.running = False
        self.target_title = config_manager.get_config('target_window_title', '疯狂赛车')

    def force_activate(self, hwnd):
        """强力激活窗口，确保窗口在最前且可用"""
        try:
            if not win32gui.IsWindow(hwnd):
                return False
            # 先显示并恢复窗口
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
            time.sleep(0.2)
            win32gui.SetForegroundWindow(hwnd)
            return True
        except Exception:
            return False

    def run(self):
        self.running = True
        # 从配置中读取坐标，默认值与你之前的一致
        coords = self.config_manager.get_config('input_coords', {
            'acc_input': [520, 300],
            'pwd_input': [520, 350]
        })

        for index, hwnd, account in self.hwnd_list:
            if not self.running: break

            # 再次验证句柄是否有效
            if not win32gui.IsWindow(hwnd):
                self.log_signal.emit(0, "ERROR", f"窗口句柄 {hwnd} 已失效，跳过账号 {account['user']}")
                continue

            username = account.get('user', '')
            password = account.get('pass', '')

            self.log_signal.emit(hwnd, "INFO", f"正在登录账号: {username}")
            success = self.login_single_window(hwnd, username, password, coords)
            
            self.login_complete.emit(index, hwnd, account, success)
            # 处理完一个窗口，稍微休息一下
            time.sleep(1.5)

        self.log_signal.emit(0, "INFO", "所有账号登录指令发送完毕")

    def login_single_window(self, hwnd, username, password, coords):
        try:
            # 步骤1: 强力激活
            self.force_activate(hwnd)
            time.sleep(0.2)

            # 步骤2: 跳过开场动画 (空格)
            self.engine.key_press(hwnd, win32con.VK_SPACE)
            time.sleep(0.2)

            # 步骤3: 输入账号
            acc_pos = coords.get('acc_input', [520, 300])
            self.log_signal.emit(hwnd, "DEBUG", f"输入账号到: {acc_pos}")
            # 使用已有的 type_text 方法
            self.engine.type_text(hwnd, acc_pos[0], acc_pos[1], username)
            time.sleep(0.5)

            # 步骤4: 输入密码
            pwd_pos = coords.get('pwd_input', [520, 350])
            self.log_signal.emit(hwnd, "DEBUG", f"输入密码到: {pwd_pos}")
            self.engine.type_text(hwnd, pwd_pos[0], pwd_pos[1], password)
            time.sleep(0.5)

            # 步骤5: 按回车登录
            self.engine.key_press(hwnd, win32con.VK_RETURN)
            self.log_signal.emit(hwnd, "INFO", "登录指令已发送")
            
            return True
        except Exception as e:
            self.log_signal.emit(hwnd, "ERROR", f"执行登录操作失败: {e}")
            return False

if __name__ == "__main__":
    # 创建 QCoreApplication 防止 thread 需要事件循环
    from PyQt6.QtCore import QCoreApplication
    app = QCoreApplication(sys.argv)
    
    cfg = ConfigManager()
    log = SimpleLogger()

    # 1. 检查路径
    res_path = cfg.get_path('window_results')
    print(f"尝试读取路径: {res_path}") # 调试信息
    
    if os.path.exists(res_path):
        try:
            with open(res_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                # 转换格式以匹配 LoginModule 的输入
                window_results = [(i['index'], i['hwnd'], {'user': i['username'], 'pass': i.get('password','')}) for i in data]
            
            if not window_results:
                print("错误: json 文件内没有数据。")
                sys.exit()

            # 2. 实例化
            worker = LoginModule(window_results, cfg, log)

            # 3. 【核心】连接信号，否则你看不到报错和日志
            worker.log_signal.connect(lambda hwnd, level, msg: print(f"[{level}] [窗口:{hwnd}] {msg}"))
            worker.progress_update.connect(lambda idx, msg: print(f"[进度] {msg}"))
            
            # 4. 线程结束时退出程序
            worker.finished.connect(app.quit)

            # 5. 启动
            print("--- 开始执行登录模块 ---")
            worker.start()

            # 6. 进入事件循环，等待线程执行完毕
            sys.exit(app.exec())

        except Exception as e:
            print(f"启动失败: {e}")
    else:
        print(f"错误: 找不到窗口数据文件 {res_path}，请先运行 launcher_module.py")
