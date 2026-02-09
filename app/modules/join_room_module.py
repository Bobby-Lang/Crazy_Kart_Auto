# -*- coding: utf-8 -*-
import time, os, json, win32con, sys
from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtWidgets import QApplication

# Ensure imports from package root
from app.core.game_engine import GameEngine
from app.core.config_manager import ConfigManager
from app.logger import SimpleLogger

class JoinRoomModule(QThread):
    log_signal = pyqtSignal(int, str, str)

    def __init__(self, hwnd_list, config_manager, logger):
        super().__init__()
        self.hwnd_list = hwnd_list
        self.config = config_manager
        self.engine = GameEngine(config_manager)
        self.logger = logger

    def run(self):
        session_path = self.config.get_path('room_session')
        if not os.path.exists(session_path):
            self.log_signal.emit(0, "ERROR", "未发现有效的房间Session")
            return

        with open(session_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            if time.time() - data.get('timestamp', 0) > 600:
                self.log_signal.emit(0, "ERROR", "房间Session已过期")
                return
            room_id = data.get('room_id')
            host_hwnd = data.get('host_hwnd')

        password = self.config.get_config('room_password', '9527')
        chat_coord = self.config.get_config('chat_input_coord', [300, 1060])
        join_cmd = f"##{room_id} {password}"

        for index, hwnd, account in self.hwnd_list:
            if hwnd == host_hwnd: continue 
            
            self.log_signal.emit(hwnd, "INFO", f"正在加入房间: {room_id}")
            self.engine.activate_window(hwnd)
            time.sleep(0.5)
            self.engine.click(hwnd, chat_coord[0], chat_coord[1])
            time.sleep(0.3)
            self.engine.type_text(hwnd, 0, 0, join_cmd)
            time.sleep(0.3)
            self.engine.key_press(hwnd, win32con.VK_RETURN)
            time.sleep(0.8)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    cfg = ConfigManager()
    log = SimpleLogger()
    res_path = cfg.get_path('window_results')
    
    if os.path.exists(res_path):
        with open(res_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            window_data = [(i['index'], i['hwnd'], {'user':i['username']}) for i in data]
            worker = JoinRoomModule(window_data, cfg, log)
            worker.start()
            worker.finished.connect(app.quit)
            sys.exit(app.exec())
    else:
        print("未找到窗口数据")
