# -*- coding: utf-8 -*-
import time
import os
import win32con

class TaskModule:
    def __init__(self, config_manager, engine):
        self.cfg_mgr = config_manager
        self.engine = engine
        self.cfg = self.cfg_mgr.get_config("task_automation") or {}
        self.imgs = self.cfg.get("images", {})

    def run(self, hwnd):
        """执行完整的领取流程"""
        
        # 在大厅点击任务图标
        if not self._click_entry(hwnd):
            return

        # 日常任务页
        if self._wait_for_img(hwnd, self.imgs.get("daily_page_flag"), timeout=5):
            # 先循环点击所有黄底领取按钮，直到没有为止
            self._loop_click_claim(hwnd, max_clicks=10)
            # 再点击宝箱
            self._scan_and_click_boxes(hwnd)
        
        # 点击车队任务页签
        self._click_team_tab(hwnd)

        # 等待车队任务页加载，然后领取
        if self._wait_for_img(hwnd, self.imgs.get("team_page_flag"), timeout=5):
            # 循环点击所有黄底领取按钮，直到没有为止
            self._loop_click_claim(hwnd, max_clicks=10)

        # 按 Backspace 返回大厅
        self.engine.key_press(hwnd, win32con.VK_BACK)
        time.sleep(2.0)

    def _click_entry(self, hwnd):
        """找到并点击主界面任务按钮"""
        img_name = self.imgs.get("entry_icon")
        if not img_name: return False
        
        path = self.cfg_mgr.get_template_path(img_name)
        result = self.engine.match_template(hwnd, path, 0.8)
        if not result or not result[0]:
            return False
            
        found, score, (x, y) = result
        if found:
            self.engine.click(hwnd, x, y)
            time.sleep(2.0)
            return True
        return False

    def _wait_for_img(self, hwnd, img_name, timeout=5):
        """等待某个标志性图片出现（弹窗由独立Emergency线程处理）"""
        if not img_name: return False
        path = self.cfg_mgr.get_template_path(img_name)
        
        for _ in range(timeout):
            result = self.engine.match_template(hwnd, path, 0.8)
            if result and result[0]:
                return True
            time.sleep(0.5)
        return False

    def _loop_click_claim(self, hwnd, max_clicks=10):
        """循环点击领取按钮，直到没有或达到最大次数"""
        img_name = self.imgs.get("claim_btn_yellow")
        if not img_name: return
        
        btn_path = self.cfg_mgr.get_template_path(img_name)
        threshold = self.cfg.get("settings", {}).get("claim_threshold", 0.85)
        
        clicked_count = 0
        
        while clicked_count < max_clicks:
            result = self.engine.match_template(hwnd, btn_path, threshold)
            if not result or not result[0]:
                break  # 没有找到领取按钮，退出循环
                
            found, score, (x, y) = result
            if found:
                self.engine.click(hwnd, x, y)
                clicked_count += 1
                time.sleep(0.3)
                # 按空格键关闭可能的弹窗
                self.engine.key_press(hwnd, win32con.VK_SPACE)
                time.sleep(0.8)  # 等待掉落动画和弹窗关闭
            else:
                break  # 没找到，退出

    def _scan_and_click_boxes(self, hwnd):
        """扫描并点击点券宝箱"""
        boxes = self.imgs.get("reward_boxes", [])
        
        for box_img in boxes:
            path = self.cfg_mgr.get_template_path(box_img)
            result = self.engine.match_template(hwnd, path, 0.85)
            if not result or not result[0]:
                continue
                
            found, score, (x, y) = result
            if found:
                self.engine.click(hwnd, x, y)
                time.sleep(0.3)
                # 按空格键关闭可能的弹窗
                self.engine.key_press(hwnd, win32con.VK_SPACE)
                time.sleep(0.8)

    def _click_team_tab(self, hwnd):
        """点击'车队任务'页签"""
        coord = self.cfg.get("coords", {}).get("team_tab", [46, 810])
        self.engine.click(hwnd, coord[0], coord[1])
        time.sleep(1.5)
