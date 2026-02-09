# -*- coding: utf-8 -*-
import os

class RoomModule:
    def __init__(self, config, engine):
        # config 是 ConfigManager 实例
        self.config = config 
        self.engine = engine
        self.hwnd_ctx = None

    def _is_feature_present(self, config_key, threshold=0.8):
        """通用特征检测函数"""
        img_name = self.config.get_config(config_key)
        if not img_name: 
            return False
        
        path = self.config.get_template_path(img_name)
        
        if not path or not os.path.exists(path):
            return False
        
        return self.engine.match_template(self.hwnd_ctx, path, threshold)[0]

    def is_in_room(self, hwnd):
        self.hwnd_ctx = hwnd
        return self._is_feature_present('room_management_img', 0.8)

    def has_start_button(self, hwnd):
        self.hwnd_ctx = hwnd
        return self._is_feature_present('start_button_img', 0.8)

    def is_member_ready(self, hwnd):
        self.hwnd_ctx = hwnd
        return self._is_feature_present('ready_success_img', 0.8)

    def is_in_lobby(self, hwnd):
        self.hwnd_ctx = hwnd
        return self._is_feature_present('lobby_entry_img', 0.75)

    def click_start(self, hwnd):
        path = self.config.get_template_path(self.config.get_config('start_button_img'))
        found, _, center = self.engine.match_template(hwnd, path, threshold=0.8)
        if found:
            self.engine.click(hwnd, center[0], center[1])
            return True
        return False

    def click_ready(self, hwnd):
        # 从配置获取坐标，如果没有则使用默认值
        coord = self.config.get_config('coord_ready', [1600, 280])
        self.engine.click(hwnd, coord[0], coord[1])
        # 添加短暂延迟让状态更新
        import time
        time.sleep(0.5)
        # 返回点击后是否准备就绪
        return self.is_member_ready(hwnd)