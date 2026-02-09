# app/modules/emergency_module.py
# -*- coding: utf-8 -*-
import time
import os
import win32con
import win32gui
import cv2
import threading

class EmergencyModule:
    def __init__(self, config_manager, engine):
        self.cfg_mgr = config_manager
        self.engine = engine
        
        self.cfg = self.cfg_mgr.get_config("emergency_handler", {})
        self.enabled = self.cfg.get("enabled", False)
        self.threshold = self.cfg.get("match_threshold", 0.75)
        
        self.image_paths = []
        if self.enabled:
            img_cfg = self.cfg.get("image_config", {})
            prefix = img_cfg.get("prefix", "emergency_")
            count = img_cfg.get("count", 0)
            ext = img_cfg.get("extension", ".png")
            
            print(f"紧急监控 正在预检 {count} 张图片资源...")
            valid_count = 0
            
            for i in range(1, count + 1):
                fname = f"{prefix}{i}{ext}"
                path = self.cfg_mgr.get_template_path(fname)
                if path and os.path.exists(path) and os.path.getsize(path) > 0:
                    try:
                        test_img = cv2.imread(path)
                        if test_img is not None:
                            self.image_paths.append(path)
                            valid_count += 1
                    except:
                        pass
            print(f"紧急监控 最终有效加载: {valid_count}/{count} 张")
        
        # 独立检测线程
        self.running = False
        self.detection_interval = 0.1  # 检测间隔0.1秒（更快响应）
        self._lock = threading.Lock()
        self._detected = {}  # 记录每个hwnd的检测状态

    def start(self, windows):
        """启动独立检测线程"""
        if not self.enabled:
            return
        self.running = True
        self.windows = windows
        self._thread = threading.Thread(target=self._detection_loop, daemon=True)
        self._thread.start()
        print("紧急监控 独立检测线程已启动")

    def stop(self):
        """停止检测线程"""
        self.running = False

    def _detection_loop(self):
        """独立检测循环"""
        while self.running:
            try:
                for _, hwnd, _ in self.windows:
                    self._check_single_window(hwnd)
            except Exception:
                pass
            time.sleep(self.detection_interval)

    def _check_single_window(self, hwnd):
        """检查单个窗口的弹窗"""
        # 快速窗口检查
        try:
            if not win32gui.IsWindow(hwnd):
                return False
            if win32gui.IsIconic(hwnd):
                return False
            if not win32gui.IsWindowVisible(hwnd):
                return False
        except Exception:
            return False

        # 检查是否刚刚处理过（避免重复处理）
        now = time.time()
        with self._lock:
            last_time = self._detected.get(hwnd, 0)
            if now - last_time < 0.5:  # 0.5秒内不重复处理同一窗口
                return False

        # 快速匹配所有弹窗图片
        for img_path in self.image_paths:
            try:
                is_match, score, _ = self.engine.match_template(hwnd, img_path, self.threshold)
                
                if is_match:
                    img_name = os.path.basename(img_path)
                    print(f"紧急监控 窗口 {hwnd} 捕获弹窗: {img_name} (置信度:{score:.2f})")
                    
                    # 发送空格键消除
                    key_str = self.cfg.get("action_key", "space").lower()
                    vk_code = win32con.VK_SPACE
                    if key_str == "enter":
                        vk_code = win32con.VK_RETURN
                    elif key_str == "esc":
                        vk_code = win32con.VK_ESCAPE
                    
                    self.engine.key_press(hwnd, vk_code)
                    
                    # 记录处理时间
                    with self._lock:
                        self._detected[hwnd] = now
                    
                    return True
            except Exception:
                continue
        
        return False

    def check_and_handle(self, hwnd):
        """
        兼容旧接口：检测是否有异常弹窗，如果有则处理
        返回: True (已处理异常), False (无异常)
        """
        return self._check_single_window(hwnd)

        # ==================================================
        # 快速窗口状态检查（只做必要检查）
        # ==================================================
        try:
            if not win32gui.IsWindow(hwnd):
                return False
            if win32gui.IsIconic(hwnd):
                return False
            if not win32gui.IsWindowVisible(hwnd):
                return False
        except Exception:
            return False

        # ==================================================
        # 开始视觉检测（快速匹配）
        # ==================================================
        try:
            for img_path in self.image_paths:
                is_match, _, _ = self.engine.match_template(hwnd, img_path, self.threshold)
                
                if is_match:
                    img_name = os.path.basename(img_path)
                    print(f"🚨 [全局监控] 窗口 {hwnd} 捕获异常弹窗: {img_name}")
                    
                    key_str = self.cfg.get("action_key", "space").lower()
                    vk_code = win32con.VK_SPACE
                    
                    if key_str == "enter":
                        vk_code = win32con.VK_RETURN
                    elif key_str == "esc":
                        vk_code = win32con.VK_ESCAPE
                    
                    self.engine.key_press(hwnd, vk_code)
                    return True

        except Exception:
            pass
        
        return False