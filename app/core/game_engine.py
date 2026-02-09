# -*- coding: utf-8 -*-
import os
import time
import cv2
import numpy as np
import win32gui
import win32ui
import win32con
import win32api
import win32clipboard
import ctypes


class GameEngine:
    _template_cache = {}
    _cfg_mgr = None
    _base_width = 1920.0
    _base_height = 1080.0

    def __init__(self, cfg_mgr=None):
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except:
            ctypes.windll.user32.SetProcessDPIAware()

        if cfg_mgr is not None:
            GameEngine._cfg_mgr = cfg_mgr
            GameEngine._update_resolution()

    @classmethod
    def _update_resolution(cls):
        """更新基准分辨率配置"""
        if cls._cfg_mgr:
            cls._base_width, cls._base_height = cls._cfg_mgr.get_resolution()

    @classmethod
    def set_resolution(cls, width, height):
        """手动设置分辨率（用于UI配置）"""
        cls._base_width = float(width)
        cls._base_height = float(height)

    @classmethod
    def get_base_width(cls):
        return cls._base_width

    @classmethod
    def get_base_height(cls):
        return cls._base_height

    @staticmethod
    def get_real_client_size(hwnd):
        """获取游戏画面的真实物理尺寸"""
        try:
            left, top, right, bot = win32gui.GetClientRect(hwnd)
            return right - left, bot - top
        except:
            return 0, 0

    @staticmethod
    def activate_window(hwnd):
        """增强版窗口激活"""
        try:
            if win32gui.GetForegroundWindow() == hwnd:
                return
            if win32gui.IsIconic(hwnd):
                win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)

            win32api.keybd_event(win32con.VK_MENU, 0, 0, 0)
            win32gui.SetForegroundWindow(hwnd)
            win32api.keybd_event(win32con.VK_MENU, 0, win32con.KEYEVENTF_KEYUP, 0)
            time.sleep(0.3)
        except:
            pass

    @staticmethod
    def cascade_windows(hwnds, offset_x=60, offset_y=40):
        """
        阶梯排列：从屏幕右侧开始向左下阶梯排列
        对应 lobby_module.py 中的 self.engine.cascade_windows 调用
        """
        if not hwnds:
            return

        # 获取工作区尺寸（扣除任务栏）
        monitor_info = win32api.GetMonitorInfo(win32api.MonitorFromPoint((0, 0)))
        work_area = monitor_info["Work"]
        scr_w = work_area[2] - work_area[0]
        scr_h = work_area[3] - work_area[1]

        for i, hwnd in enumerate(hwnds):
            if not win32gui.IsWindow(hwnd):
                continue

            # 获取窗口当前的真实尺寸（不改变它）
            rect = win32gui.GetWindowRect(hwnd)
            curr_w = rect[2] - rect[0]
            curr_h = rect[3] - rect[1]

            # 计算坐标：靠右侧开始排
            base_x = scr_w - curr_w - 5
            x = base_x - (i * offset_x)
            y = 5 + (i * offset_y)

            # 防出界修正
            if x < 0:
                x = 0
            if y + curr_h > scr_h:
                y = scr_h - curr_h

            try:
                win32gui.SetWindowPos(
                    hwnd,
                    win32con.HWND_NOTOPMOST,
                    int(x),
                    int(y),
                    0,
                    0,
                    win32con.SWP_NOSIZE
                    | win32con.SWP_NOACTIVATE
                    | win32con.SWP_NOZORDER,
                )
            except Exception as e:
                print(f"移动窗口失败: {e}")

    @staticmethod
    def clear_input(hwnd, x, y):
        """清空方案：双击 -> Ctrl+A -> Backspace"""
        try:
            curr_w, curr_h = GameEngine.get_real_client_size(hwnd)
            if curr_w == 0 or curr_h == 0:
                return
            base_w = GameEngine.get_base_width()
            base_h = GameEngine.get_base_height()
            real_x = int(round(x * (curr_w / base_w)))
            real_y = int(round(y * (curr_h / base_h)))

            GameEngine.activate_window(hwnd)
            point = win32gui.ClientToScreen(hwnd, (real_x, real_y))
            win32api.SetCursorPos(point)

            # 物理双击
            for _ in range(2):
                win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
                win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
                time.sleep(0.05)

            time.sleep(0.4)

            # Ctrl + A
            win32api.keybd_event(win32con.VK_CONTROL, 0, 0, 0)
            time.sleep(0.1)
            win32api.keybd_event(ord("A"), 0, 0, 0)
            time.sleep(0.1)
            win32api.keybd_event(ord("A"), 0, win32con.KEYEVENTF_KEYUP, 0)
            win32api.keybd_event(win32con.VK_CONTROL, 0, win32con.KEYEVENTF_KEYUP, 0)
            time.sleep(0.2)

            # Backspace
            win32api.keybd_event(win32con.VK_DELETE, 0, 0, 0)
            time.sleep(0.1)
            win32api.keybd_event(win32con.VK_DELETE, 0, win32con.KEYEVENTF_KEYUP, 0)
            time.sleep(0.2)
        except Exception as e:
            print(f"Clear Error: {e}")

    @staticmethod
    def type_text(hwnd, x, y, text):
        """输入流程"""
        GameEngine.clear_input(hwnd, x, y)
        GameEngine.click(hwnd, x, y)  # 补一点，确保焦点
        time.sleep(0.2)
        GameEngine.paste_text(hwnd, text)

    @staticmethod
    def click(hwnd, x, y):
        """带坐标缩放的点击"""
        try:
            curr_w, curr_h = GameEngine.get_real_client_size(hwnd)
            if curr_w == 0:
                return
            base_w = GameEngine.get_base_width()
            base_h = GameEngine.get_base_height()
            real_x = int(round(x * (curr_w / base_w)))
            real_y = int(round(y * (curr_h / base_h)))

            GameEngine.activate_window(hwnd)
            point = win32gui.ClientToScreen(hwnd, (real_x, real_y))
            win32api.SetCursorPos(point)
            time.sleep(0.05)
            win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
            time.sleep(0.05)
            win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
        except:
            pass

    @staticmethod
    def key_press(hwnd, vk_code):
        """
        模拟按下并松开一个虚拟键
        :param hwnd: 窗口句柄
        :param vk_code: 虚拟键码（如 win32con.VK_RETURN）
        """
        try:
            # 确保窗口处于激活状态
            GameEngine.activate_window(hwnd)
            time.sleep(0.05)

            # 按下按键
            win32api.keybd_event(vk_code, 0, 0, 0)
            time.sleep(0.05)

            # 松开按键
            win32api.keybd_event(vk_code, 0, win32con.KEYEVENTF_KEYUP, 0)
            return True
        except Exception as e:
            print(f"Key Press Error: {e}")
            return False

    @staticmethod
    def paste_text(hwnd, text):
        try:
            win32clipboard.OpenClipboard()
            win32clipboard.EmptyClipboard()
            win32clipboard.SetClipboardText(text, win32con.CF_UNICODETEXT)
            win32clipboard.CloseClipboard()

            # 确保窗口处于前台再粘贴
            win32gui.SetForegroundWindow(hwnd)
            time.sleep(0.1)

            # 模拟按下 Ctrl+V
            win32api.keybd_event(win32con.VK_CONTROL, 0, 0, 0)
            time.sleep(0.05)  # 必须有微小的停顿
            win32api.keybd_event(ord("V"), 0, 0, 0)
            time.sleep(0.05)
            win32api.keybd_event(ord("V"), 0, win32con.KEYEVENTF_KEYUP, 0)
            win32api.keybd_event(win32con.VK_CONTROL, 0, win32con.KEYEVENTF_KEYUP, 0)
            return True
        except:
            return False

    @staticmethod
    def grab_screen(hwnd, rescale_to_base=False):
        """后台截图 - 添加超时保护和资源清理"""
        import threading
        
        result = [None]
        
        def capture():
            hwndDC = None
            mfcDC = None
            saveDC = None
            saveBitMap = None
            
            try:
                # 检查窗口是否有效
                if not win32gui.IsWindow(hwnd):
                    print(f"[截图错误] 窗口无效: {hwnd}")
                    result[0] = None
                    return
                
                # 检查窗口是否可见
                if not win32gui.IsWindowVisible(hwnd):
                    print(f"[截图警告] 窗口不可见: {hwnd}")
                    
                left, top, right, bot = win32gui.GetClientRect(hwnd)
                w, h = right - left, bot - top
                
                # 检查窗口尺寸
                if w <= 0 or h <= 0:
                    print(f"[截图错误] 窗口尺寸无效: {w}x{h}")
                    result[0] = None
                    return
                
                # 分配GDI资源
                hwndDC = win32gui.GetWindowDC(hwnd)
                if not hwndDC:
                    print(f"[截图错误] GetWindowDC失败")
                    result[0] = None
                    return
                    
                mfcDC = win32ui.CreateDCFromHandle(hwndDC)
                if not mfcDC:
                    raise Exception("CreateDCFromHandle失败")
                    
                saveDC = mfcDC.CreateCompatibleDC()
                if not saveDC:
                    raise Exception("CreateCompatibleDC失败")
                    
                saveBitMap = win32ui.CreateBitmap()
                saveBitMap.CreateCompatibleBitmap(mfcDC, w, h)
                saveDC.SelectObject(saveBitMap)
                
                # 截图
                ctypes.windll.user32.PrintWindow(hwnd, saveDC.GetSafeHdc(), 2)
                bmpstr = saveBitMap.GetBitmapBits(True)
                img = np.frombuffer(bmpstr, dtype="uint8")
                img.shape = (h, w, 4)
                
                # 处理图像
                img_bgr = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
                if rescale_to_base:
                    base_w = GameEngine.get_base_width()
                    base_h = GameEngine.get_base_height()
                    img_bgr = cv2.resize(img_bgr, (int(base_w), int(base_h)))
                result[0] = img_bgr
                
            except Exception as e:
                print(f"[截图错误] {e}")
                result[0] = None
            finally:
                # 确保所有GDI资源被释放
                try:
                    if saveBitMap:
                        win32gui.DeleteObject(saveBitMap.GetHandle())
                except:
                    pass
                try:
                    if saveDC:
                        saveDC.DeleteDC()
                except:
                    pass
                try:
                    if mfcDC:
                        mfcDC.DeleteDC()
                except:
                    pass
                try:
                    if hwndDC:
                        win32gui.ReleaseDC(hwnd, hwndDC)
                except:
                    pass
        
        # 使用线程防止PrintWindow卡住
        t = threading.Thread(target=capture)
        t.daemon = True
        t.start()
        t.join(timeout=2.0)  # 2秒超时
        
        if t.is_alive():
            print(f"[警告] 截图超时，窗口可能无响应 (hwnd: {hwnd})")
            return None
        
        return result[0]

    @staticmethod
    def match_template(hwnd, img_path, threshold=0.75, roi=None):
        if not img_path or not os.path.exists(img_path):
            return (False, 0.0, None)

        # 1. 缓存加载并强制转为 3 通道 BGR
        if img_path not in GameEngine._template_cache:
            tmpl = cv2.imread(img_path, cv2.IMREAD_COLOR) # 强制 3 通道
            if tmpl is None: 
                return (False, 0.0, None)
            GameEngine._template_cache[img_path] = tmpl

        template = GameEngine._template_cache[img_path]
        screen = GameEngine.grab_screen(hwnd, rescale_to_base=True)

        if screen is None or screen.size == 0:
            return (False, 0.0, None)

        # 2. 【关键修复】确保 screen 也是 3 通道（有时 PrintWindow 会产生异常格式）
        if len(screen.shape) == 2: # 灰度图转 BGR
            screen = cv2.cvtColor(screen, cv2.COLOR_GRAY2BGR)
        elif screen.shape[2] == 4: # BGRA 转 BGR
            screen = cv2.cvtColor(screen, cv2.COLOR_BGRA2BGR)

        # 3. 应用ROI区域搜索
        # 支持两种格式：[x, y, width, height] 或 [x1, y1, x2, y2]
        if roi and len(roi) == 4:
            # 判断格式：如果第3个值 > 第1个值 且 第4个值 > 第2个值，则是 (x1, y1, x2, y2) 格式
            if roi[2] > roi[0] and roi[3] > roi[1]:
                # [x1, y1, x2, y2] 格式
                x, y, x2, y2 = roi
                w, h = x2 - x, y2 - y
            else:
                # [x, y, width, height] 格式
                x, y, w, h = roi
            screen = screen[y:y+h, x:x+w]

        # 4. 尺寸校验：如果模板比屏幕还大，直接返回（防止 OpenCV 崩溃）
        if screen.shape[0] < template.shape[0] or screen.shape[1] < template.shape[1]:
            return (False, 0.0, None)

        max_val = 0.0
        try:
            res = cv2.matchTemplate(screen, template, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, max_loc = cv2.minMaxLoc(res)
            if max_val >= threshold:
                h, w = template.shape[:2]
                center_x = max_loc[0] + w // 2
                center_y = max_loc[1] + h // 2
                
                # 如果使用了ROI，需要转换回全屏坐标
                if roi and len(roi) == 4:
                    center_x += roi[0]
                    center_y += roi[1]
                    
                return (True, max_val, (center_x, center_y))
        except Exception as e:
            # 捕获 C++ 层的各种 OpenCV 异常
            print(f"Match Error [{os.path.basename(img_path)}]: {e}")
            
        return (False, max_val, None)


    @staticmethod
    def ctrl_a_c(hwnd):
        """模拟全选和复制"""
        try:
            GameEngine.activate_window(hwnd)
            time.sleep(0.1)
            # Ctrl+A
            win32api.keybd_event(win32con.VK_CONTROL, 0, 0, 0)
            win32api.keybd_event(ord("A"), 0, 0, 0)
            time.sleep(0.05)
            win32api.keybd_event(ord("A"), 0, win32con.KEYEVENTF_KEYUP, 0)
            win32api.keybd_event(win32con.VK_CONTROL, 0, win32con.KEYEVENTF_KEYUP, 0)
            time.sleep(0.2)
            # Ctrl+C
            win32api.keybd_event(win32con.VK_CONTROL, 0, 0, 0)
            win32api.keybd_event(ord("C"), 0, 0, 0)
            time.sleep(0.05)
            win32api.keybd_event(ord("C"), 0, win32con.KEYEVENTF_KEYUP, 0)
            win32api.keybd_event(win32con.VK_CONTROL, 0, win32con.KEYEVENTF_KEYUP, 0)
            time.sleep(0.3)
            return True
        except:
            return False

    @staticmethod
    def get_clipboard_text():
        """读取剪贴板文字"""
        try:
            win32clipboard.OpenClipboard()
            t = win32clipboard.GetClipboardData(win32con.CF_UNICODETEXT)
            win32clipboard.CloseClipboard()
            return t
        except:
            return ""
# --- 在 GameEngine 类中添加 ---
    @staticmethod
    def blind_login(self, hwnd, username, password, coords):
        """
        通用盲打登录逻辑：供 LoginModule 和 TaskController 共同调用
        """
        import win32gui, win32con, time # 局部引用，防止循环导入

        try:
            # 1. 强力激活 (确保窗口在前)
            if not win32gui.IsWindow(hwnd): return False
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
            time.sleep(0.2)
            win32gui.SetForegroundWindow(hwnd)
            time.sleep(0.2)

            # 2. 盲按空格跳动画
            self.key_press(hwnd, win32con.VK_SPACE)
            time.sleep(0.5)

            # 3. 输入账号
            acc_pos = coords.get('acc_input', [520, 300])
            self.type_text(hwnd, acc_pos[0], acc_pos[1], username)
            time.sleep(0.5)

            # 4. 输入密码
            pwd_pos = coords.get('pwd_input', [520, 350])
            self.type_text(hwnd, pwd_pos[0], pwd_pos[1], password)
            time.sleep(0.5)

            # 5. 回车
            self.key_press(hwnd, win32con.VK_RETURN)
            return True
        except Exception as e:
            print(f"盲打登录失败: {e}")
            return False