# -*- coding: utf-8 -*-
import time, os, json, re, sys, win32api, win32con, win32gui, win32clipboard
from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtWidgets import QApplication

# Ensure package imports
from app.core.game_engine import GameEngine
from app.core.config_manager import ConfigManager
from app.logger import SimpleLogger

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
        if not self.hwnd_list:
            self.log_signal.emit(0, "ERROR", "未提供窗口列表，无法创建房间")
            return
        # 取第一个窗口为房主，确保列表非空
        index, host_hwnd, account = self.hwnd_list[0]
        self.log_signal.emit(host_hwnd, "INFO", "房主窗口准备就绪...")
        self.engine.activate_window(host_hwnd)
        
        # 1. 执行创建序列
        # 确保获取到的创建序列为列表
        create_seq = self.config.get_config("room_creation", []) or []
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
        seq = self.config.get_config("get_room_name_sequence", []) or []
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
        # Ensure room_session path exists before saving
        session_path = self.config.get_path('room_session')
        if not session_path:
            self.log_signal.emit(host_hwnd, "ERROR", "room_session 配置缺失，无法保存会话")
            return
        with open(session_path, 'w', encoding='utf-8') as f:
            json.dump(session_data, f, ensure_ascii=False, indent=4)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    cfg = ConfigManager()
    log = SimpleLogger()
    res_path = cfg.get_path('window_results')
    
    if not res_path or not os.path.exists(res_path):
        print(f"ERR: 找不到文件 {res_path}")
        sys.exit(1)
    
    # 读取窗口结果文件并构建列表
    with open(res_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    results = [(i['index'], i['hwnd'], {"user": i['username'], "pass": i['password']}) for i in data]
    
    worker = CreateRoomModule(results, cfg, log)
    worker.log_signal.connect(lambda h, l, m: print(f"[{l}] {m}"))
    worker.all_ready.connect(app.quit)
    worker.start()
    sys.exit(app.exec())
