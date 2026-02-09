# -*- coding: utf-8 -*-
import os
import sys
import time
import json
import subprocess
import win32gui
import win32con
import win32api
from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtWidgets import QApplication

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.config_manager import ConfigManager

class LauncherModule(QThread):
    log_signal = pyqtSignal(int, str, str)
    all_ready = pyqtSignal()

    def __init__(self, box_path, game_path, accounts, config_manager, logger=None):
        super().__init__()
        self.box_path = box_path
        self.game_path = game_path
        self.accounts = accounts
        self.config_manager = config_manager
        self.logger = logger
        self.running = True
        self.target_window_title = config_manager.get_config('target_window_title', '疯狂赛车怀旧版')

    def log(self, level, msg):
        print(f"[{level}] {msg}")
        self.log_signal.emit(0, level, msg)

    def get_hwnds_by_title(self, title_part):
        res = []
        def cb(hwnd, _):
            if win32gui.IsWindowVisible(hwnd):
                title = win32gui.GetWindowText(hwnd)
                if title_part.lower() in title.lower():
                    res.append(hwnd)
        win32gui.EnumWindows(cb, None)
        return res

    def start_2box(self):
        hwnds = self.get_hwnds_by_title("2Box")
        if hwnds: return hwnds[0]
        self.log("INFO", f"检测到 2Box 未运行，尝试启动: {self.box_path}")
        subprocess.Popen(f'"{self.box_path}"', shell=True)
        for _ in range(15):
            time.sleep(1); hwnds = self.get_hwnds_by_title("2Box")
            if hwnds: return hwnds[0]
        return 0

    def open_game_in_2box(self, box_hwnd):
        try:
            win32gui.ShowWindow(box_hwnd, win32con.SW_RESTORE)
            win32gui.SetForegroundWindow(box_hwnd)
            time.sleep(0.5)
            # Alt+F -> O (2Box 打开快捷键)
            win32api.keybd_event(win32con.VK_MENU, 0, 0, 0)
            win32api.keybd_event(ord('F'), 0, 0, 0)
            win32api.keybd_event(ord('F'), 0, win32con.KEYEVENTF_KEYUP, 0)
            win32api.keybd_event(win32con.VK_MENU, 0, win32con.KEYEVENTF_KEYUP, 0)
            time.sleep(0.5)
            win32api.keybd_event(ord('O'), 0, 0, 0)
            win32api.keybd_event(ord('O'), 0, win32con.KEYEVENTF_KEYUP, 0)
            
            dlg_hwnd = 0
            for _ in range(20):
                time.sleep(0.3)
                hwnds = []
                win32gui.EnumWindows(lambda h, _: hwnds.append(h) if win32gui.GetClassName(h) == "#32770" else None, None)
                for h in hwnds:
                    if win32gui.IsWindowVisible(h):
                        t = win32gui.GetWindowText(h)
                        if "打开" in t or "Open" in t:
                            dlg_hwnd = h; break
                if dlg_hwnd: break

            if not dlg_hwnd: return False

            # 找到输入框并填入路径
            edit_hwnd = win32gui.FindWindowEx(dlg_hwnd, 0, "ComboBoxEx32", None)
            if edit_hwnd:
                edit_hwnd = win32gui.FindWindowEx(edit_hwnd, 0, "ComboBox", None)
                edit_hwnd = win32gui.FindWindowEx(edit_hwnd, 0, "Edit", None)
            else:
                edit_hwnd = win32gui.FindWindowEx(dlg_hwnd, 0, "Edit", None)

            win32gui.SendMessage(edit_hwnd, win32con.WM_SETTEXT, 0, self.game_path)
            time.sleep(0.5)
            win32api.PostMessage(edit_hwnd, win32con.WM_KEYDOWN, win32con.VK_RETURN, 0)
            return True
        except: return False

    def wait_for_new_window(self, pre_hwnds, timeout):
        start = time.time()
        while time.time() - start < timeout:
            current = self.get_hwnds_by_title(self.target_window_title)
            new = [h for h in current if h not in pre_hwnds]
            if new: return new[0]
            time.sleep(1)
        return 0

    def arrange_top_right(self, hwnds):
        """将窗口阶梯状排列在屏幕右上角"""
        if not hwnds: return
        
        # 从配置读取偏移
        cfg = self.config_manager.get_config("window_arrangement", {})
        offset_x = cfg.get("偏移设置", {}).get("offset_x", 80)
        offset_y = cfg.get("偏移设置", {}).get("offset_y", 40)
        
        # 获取显示器工作区尺寸（避开任务栏）
        monitor_info = win32api.GetMonitorInfo(win32api.MonitorFromPoint((0, 0)))
        work_area = monitor_info['Work'] # [left, top, right, bottom]
        screen_w = work_area[2]
        
        self.log("INFO", f"正在进行窗口右上角排列，偏移量: {offset_x}x{offset_y}")
        
        for i, hwnd in enumerate(hwnds):
            if not win32gui.IsWindow(hwnd): continue
            
            # 获取窗口物理尺寸
            rect = win32gui.GetWindowRect(hwnd)
            win_w = rect[2] - rect[0]
            win_h = rect[3] - rect[1]
            
            # 计算位置：最右边开始，向左下方阶梯偏移
            # X = 屏幕右边界 - 窗口宽 - (索引 * 水平偏移)
            x = screen_w - win_w - (i * offset_x)
            # Y = 屏幕顶边界 + (索引 * 垂直偏移)
            y = work_area[1] + (i * offset_y)
            
            # 执行移动，SWP_NOSIZE 保持原有大小
            win32gui.SetWindowPos(
                hwnd, win32con.HWND_TOP, 
                int(x), int(y), 0, 0, 
                win32con.SWP_NOSIZE | win32con.SWP_NOACTIVATE
            )

    def run(self):
        """主执行流程"""
        try:
            self.log("INFO", f"准备启动 {len(self.accounts)} 个账号窗口")
            box_hwnd = self.start_2box()
            if not box_hwnd:
                self.log("ERROR", "无法启动 2Box"); return

            final_results = []
            for i, acc in enumerate(self.accounts):
                if not self.running: break
                user, pwd = acc.get('username'), acc.get('password')
                if not user or not pwd:
                    user, pwd = acc.get('user'), acc.get('pass')
                self.log("INFO", f"--- 正在启动账号 ({i+1}/{len(self.accounts)}): {user} ---")

                pre_hwnds = self.get_hwnds_by_title(self.target_window_title)
                if self.open_game_in_2box(box_hwnd):
                    new_hwnd = self.wait_for_new_window(pre_hwnds, timeout=45)
                    if new_hwnd:
                        self.log("INFO", f"成功启动窗口: {new_hwnd}")
                        final_results.append({
                            "index": i, "hwnd": new_hwnd, "username": user, "password": pwd
                        })
                        time.sleep(2)
                    else:
                        self.log("WARN", f"账号 {user} 启动超时")
                else:
                    self.log("ERROR", f"账号 {user} 打开指令失败")

            # 所有窗口启动完毕后，执行右上角排列
            if final_results:
                hwnds = [item['hwnd'] for item in final_results]
                self.arrange_top_right(hwnds)

            # 保存结果
            json_path = self.config_manager.get_path('window_results')
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(final_results, f, ensure_ascii=False, indent=4)
            
            self.log("INFO", "所有任务启动完毕并已排列")
            self.all_ready.emit()
        except Exception as e:
            self.log("ERROR", f"执行异常: {e}")

# ... load_accounts 等剩余代码保持不变 ...
# ==========================================
# 外部调用接口
# ==========================================
def load_accounts(file_path):
    accounts = []
    if not os.path.exists(file_path):
        return accounts
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and ',' in line:
                    u, p = line.split(',', 1)
                    accounts.append({"user": u.strip(), "pass": p.strip()})
        print(f"[INFO] 成功从文件载入 {len(accounts)} 个账号")
    except Exception:
        pass
    return accounts

if __name__ == "__main__":
    app = QApplication(sys.argv)
    cfg = ConfigManager()
    
    # 彻底告别 D:\ 直接从配置读
    box_exe = cfg.get_user_config('paths.box_path')
    game_exe = cfg.get_user_config('paths.game_path')
    acc_file = cfg.get_path('accounts')
    account_list = load_accounts(acc_file)
    if account_list:
        launcher = LauncherModule(box_exe, game_exe, account_list, cfg)
        launcher.start()
        launcher.finished.connect(app.quit)
        sys.exit(app.exec())
