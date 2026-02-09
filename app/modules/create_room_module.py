# -*- coding: utf-8 -*-
import time
import os
import json
import re
import sys
import win32api
import win32con
import win32gui
import win32clipboard
from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtWidgets import QApplication

# 路径修复
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    from core import GameEngine, ConfigManager
    from logger import SimpleLogger
except ImportError:
    print("错误: 无法导入核心组件，请检查目录结构")
    sys.exit(1)

class CreateRoomModule(QThread):
    log_signal = pyqtSignal(int, str, str)
    room_ready = pyqtSignal(int, int, dict, str)
    all_ready = pyqtSignal()

    def __init__(self, hwnd_list: list, config_manager: ConfigManager, logger: SimpleLogger):
        super().__init__()
        self.hwnd_list = hwnd_list
        self.config = config_manager
        self.logger = logger
        self.engine = GameEngine(config_manager)
        self.running = False

    def run(self):
        self.running = True
        if not self.hwnd_list: return

        index, host_hwnd, account = self.hwnd_list[0]
        self.log_signal.emit(host_hwnd, "INFO", "房主窗口准备就绪...")
        self.engine.activate_window(host_hwnd)
        
        # 1. 执行创建序列
        create_seq = self.config.get_config("room_creation", [])
        for step in create_seq:
            if not self.running: break
            self.engine.activate_window(host_hwnd)
            self.log_signal.emit(host_hwnd, "INFO", f"执行步骤: {step.get('name')}")
            self.execute_step(host_hwnd, step)
            time.sleep(0.8)
            
        self.log_signal.emit(host_hwnd, "INFO", "确认指令已发送，等待进入房间...")
        time.sleep(2.0) 

        # 2. 提取房间号
        room_id = self.extract_room_id(host_hwnd)

        if room_id and room_id != "0":
            self.log_signal.emit(host_hwnd, "INFO", f"【成功】识别到房间号: {room_id}")
            self.save_session(room_id, host_hwnd)
            self.room_ready.emit(index, host_hwnd, account, room_id)
        else:
            self.log_signal.emit(host_hwnd, "ERROR", "【失败】未能识别房间号")

        self.all_ready.emit()

    def execute_step(self, hwnd, step):
        t = step.get("type")
        coord = step.get("coord", [0, 0])
        if t == "click":
            self.engine.click(hwnd, coord[0], coord[1])
        elif t == "input_text":
            text = self.config.get_config("room_password", "9527") if step.get("text_source") == "config_str" else step.get("text", "")
            self.engine.click(hwnd, coord[0], coord[1])
            time.sleep(0.5)
            self.engine.paste_text(hwnd, str(text))

    def extract_room_id(self, hwnd):
        seq = self.config.get_config("get_room_name_sequence", [])
        for i, s in enumerate(seq):
            if not self.running: break
            self.engine.activate_window(hwnd)
            coord = s.get("coord", [0, 0])
            if s.get("type") == "select_and_copy":
                self.engine.click(hwnd, coord[0], coord[1])
                time.sleep(0.8)
                self.send_ctrl_key(ord("A"))
                time.sleep(0.3)
                self.send_ctrl_key(ord("C"))
                time.sleep(1.0)
            else:
                self.engine.click(hwnd, coord[0], coord[1])
                time.sleep(1.0)
        
        try:
            win32clipboard.OpenClipboard()
            raw_text = win32clipboard.GetClipboardData(win32con.CF_UNICODETEXT)
            win32clipboard.CloseClipboard()
            res = re.findall(r"\d+", str(raw_text))
            return res[-1] if res else ""
        except: return ""

    def send_ctrl_key(self, char_code):
        win32api.keybd_event(win32con.VK_CONTROL, 0, 0, 0)
        win32api.keybd_event(char_code, 0, 0, 0)
        time.sleep(0.1)
        win32api.keybd_event(char_code, 0, win32con.KEYEVENTF_KEYUP, 0)
        win32api.keybd_event(win32con.VK_CONTROL, 0, win32con.KEYEVENTF_KEYUP, 0)

    def save_session(self, room_id, host_hwnd):
        session_data = {'room_id': str(room_id), 'host_hwnd': host_hwnd, 'timestamp': time.time()}
        session_path = self.config.get_path('room_session') 
        with open(session_path, 'w', encoding='utf-8') as f:
            json.dump(session_data, f, ensure_ascii=False, indent=4)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    cfg = ConfigManager()
    log = SimpleLogger()
    res_path = cfg.get_path('window_results')
    
    if not os.path.exists(res_path):
        print(f"ERR: 找不到文件 {res_path}")
        sys.exit(1)

    with open(res_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
        results = [(i['index'], i['hwnd'], {"user": i['username'], "pass": i['password']}) for i in data]

    worker = CreateRoomModule(results, cfg, log)
    worker.log_signal.connect(lambda h, l, m: print(f"[{l}] {m}"))
    worker.all_ready.connect(app.quit)
    worker.start()
    sys.exit(app.exec())
