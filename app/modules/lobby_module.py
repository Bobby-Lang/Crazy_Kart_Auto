# -*- coding: utf-8 -*-
import time
import os
import json
import win32gui
import win32con
from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtWidgets import QApplication

import sys


from app.core.game_engine import GameEngine
from app.core.config_manager import ConfigManager
from app.logger import SimpleLogger

class LobbyModule(QThread):
    log_signal = pyqtSignal(int, str, str)
    progress_update = pyqtSignal(int, str)
    lobby_complete = pyqtSignal(int, int, dict, bool)

    def __init__(self, hwnd_list: list, config_manager: ConfigManager, logger: SimpleLogger):
        super().__init__()
        self.hwnd_list = hwnd_list
        self.config = config_manager
        self.logger = logger
        self.engine = GameEngine(config_manager)
        self.running = False
        self.lobby_results = {}

    def activate_window_force(self, hwnd):
        try:
            if win32gui.IsIconic(hwnd):
                win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
            win32gui.SetForegroundWindow(hwnd)
            time.sleep(0.2)
        except:
            pass

    def run(self):
        self.running = True
        self.arrange_windows()

        for index, hwnd, account in self.hwnd_list:
            if not self.running: break
            
            username = account.get('user', '')
            self.progress_update.emit(index, "正在处理")
            self.log_signal.emit(hwnd, "INFO", f"--- 窗口 [{username}] 流程开始 ---")

            self.activate_window_force(hwnd)

            # 1. 预检测是否已在大厅
            if self.is_already_in_lobby(hwnd):
                self.log_signal.emit(hwnd, "INFO", "检测到已在大厅，跳过点击序列")
                success = True
            else:
                # 2. 执行配置好的 login_sequence
                success = self.execute_window_flow(hwnd, index)

            self.lobby_results[hwnd] = success
            self.lobby_complete.emit(index, hwnd, account, success)
            
        self.log_signal.emit(0, "INFO", "所有流程处理完毕")

    def execute_window_flow(self, hwnd, index) -> bool:
        login_seq = self.config.get_config('login_sequence', [])
        
        for step in login_seq:
            if not self.running: return False
            
            # 执行每一个步骤的点击与循环验证
            ok = self.smart_step_with_retry(hwnd, step)
            if not ok:
                self.log_signal.emit(hwnd, "WARN", f"步骤 [{step.get('name')}] 验证图未出现，尝试继续下一步...")
            


        # 序列走完后，进入最终的大厅状态轮询 (Loading 阶段)
        return self.wait_for_lobby_loading(hwnd)

    def smart_step_with_retry(self, hwnd, step) -> bool:
        """核心：点击 -> 等待验证图 -> 不成功则重试点击"""
        name = step.get('name', '未知步')
        coords = step.get('coord', [0, 0])
        check_img = step.get('check_img', '')
        max_retries = step.get('max_retries', 2)
        
        for i in range(max_retries):
            self.log_signal.emit(hwnd, "INFO", f"发送点击: {name} (尝试 {i+1})")
            self.engine.click(hwnd, coords[0], coords[1])
            
            if not check_img:
                time.sleep(0.1)  # 没有验证图，简单等待
                return True
            
            # 等待验证图出现
            img_path = self.config.get_template_path(check_img)
            self.log_signal.emit(hwnd, "DEBUG", f"等待验证图: {check_img}...")
            
            # 给 3 秒时间让界面跳转，先立即检测，失败再等待
            for i in range(10): 
                if not self.running: return False
                if i > 0:  # 第一次立即检测，后续等待
                    time.sleep(0.05)
                found, score, _ = self.engine.match_template(hwnd, img_path, threshold=0.75)
                if found:
                    self.log_signal.emit(hwnd, "INFO", f"成功识别: {name} (匹配度:{score:.2f})")
                    return True
            
            self.log_signal.emit(hwnd, "WARN", f"未识别到验证图 {check_img}，准备重试点击...")
        
        return False

    def is_already_in_lobby(self, hwnd) -> bool:
        """检测是否已在大厅界面"""
        final_img = self.config.get_config('final_state', {}).get('img_name', '')
        if not final_img: return False
        
        path = self.config.get_template_path(final_img)
        found, _, _ = self.engine.match_template(hwnd, path, threshold=0.8)
        return found

    def wait_for_lobby_loading(self, hwnd) -> bool:
        """
        专门处理点击'进入游戏'后的 Loading 加载条阶段。
        这步需要较长的超时时间。
        """
        final_state = self.config.get_config('final_state', {})
        target_img = final_state.get('img_name', '')
        # 强制将超时提高，忽略配置中过短的 timeout_sec
        timeout = max(final_state.get('timeout_sec', 30), 25) 
        
        if not target_img: return True

        self.log_signal.emit(hwnd, "INFO", f"等待进入大厅中，最大等待 {timeout}s...")
        start_time = time.time()
        img_path = self.config.get_template_path(target_img)
        
        while time.time() - start_time < timeout:
            if not self.running: return False
            found, score, _ = self.engine.match_template(hwnd, img_path, threshold=0.8)
            if found:
                self.log_signal.emit(hwnd, "INFO", f"确认大厅状态成功! (匹配度:{score:.2f})")
                return True
            time.sleep(0.1)  # 每100ms检测一次
            
        self.log_signal.emit(hwnd, "ERROR", "等待大厅超时，界面未跳转或加载中卡死")
        return False

    def arrange_windows(self):
        cfg = self.config.get_config('window_arrangement', {})
        if cfg.get('enabled') and len(self.hwnd_list) > 1:
            hwnds = [h for _, h, _ in self.hwnd_list]
            self.engine.cascade_windows(hwnds, 80, 40)
            time.sleep(0.2)  # 等待窗口稳定

    def stop(self):
        self.running = False


if __name__ == "__main__":
    app = QApplication(sys.argv)
    cfg = ConfigManager()
    log = SimpleLogger()

    res_path = cfg.get_path('window_results')
    
    if os.path.exists(res_path):
        with open(res_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            # 确保这里解析出来的 hwnd 是正确的
            window_results = [(i['index'], i['hwnd'], {'user': i['username'], 'pass': i.get('password','')}) for i in data]
        
        worker = LobbyModule(window_results, cfg, log) 
        
        # --- 关键：将信号连接到标准输出，否则你看不见进度 ---
        worker.log_signal.connect(lambda h, l, m: print(f"[{l}] [窗口:{h}] {m}"))
        worker.progress_update.connect(lambda i, s: print(f"进度: {i} -> {s}"))
        worker.lobby_complete.connect(lambda i, h, a, s: print(f"窗口 {h} 完成结果: {s}"))
        
        print("开始 Lobby 模块测试...")
        worker.start()
        
        sys.exit(app.exec()) # 保持主进程不退出
    else:
        print(f"错误: 找不到结果文件 {res_path}")


