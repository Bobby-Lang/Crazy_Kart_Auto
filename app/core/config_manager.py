# -*- coding: utf-8 -*-
import os
import json

class ConfigManager:
    def __init__(self):
        # 基础目录定位
        # __file__ 是 app/core/config_manager.py
        self.CORE_DIR = os.path.dirname(os.path.abspath(__file__))
        self.APP_DIR = os.path.dirname(self.CORE_DIR)
        self.DATA_DIR = os.path.join(self.APP_DIR, "data")
        
        # 确保 data 目录存在
        if not os.path.exists(self.DATA_DIR):
            os.makedirs(self.DATA_DIR)

        # 定义各个文件的绝对路径
        self.paths = {
            "config": os.path.join(self.DATA_DIR, "config.json"),
            "user_config": os.path.join(self.DATA_DIR, "user_config.json"),
            "accounts": os.path.join(self.DATA_DIR, "accounts.txt"),
            "window_results": os.path.join(self.DATA_DIR, "window_results.json"),
            "room_session": os.path.join(self.DATA_DIR, "room_session.json"),
            "mode_counts": os.path.join(self.DATA_DIR, "mode_counts.json"),
            "templates": os.path.join(self.APP_DIR, "templates")
        }

        # 内存缓存
        self.config_data = self._load_json(self.paths["config"])
        self.user_config_data = self._load_json(self.paths["user_config"])

    def _load_json(self, path):
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}

    def get_config(self, key, default=None):
        """获取 config.json 中的值"""
        return self._get_nested(self.config_data, key, default)
    # --- 新增这个方法来解决 RoomModule 的报错 ---
    def get(self, key, default=None):
        """兼容字典的 get 方法，直接调用 get_config"""
        return self.get_config(key, default)

    def get_user_config(self, key, default=None):
        """获取 user_config.json 中的值"""
        return self._get_nested(self.user_config_data, key, default)

    def _get_nested(self, data, key, default):
        keys = key.split('.')
        for k in keys:
            if isinstance(data, dict) and k in data:
                data = data[k]
            else:
                return default
        return data

    def save_user_config(self):
        with open(self.paths["user_config"], 'w', encoding='utf-8') as f:
            json.dump(self.user_config_data, f, indent=4, ensure_ascii=False)

    def get_path(self, name):
        """快速获取文件路径，如 cfg.get_path('window_results')"""
        return self.paths.get(name)

    def get_template_path(self, img_name):
        """获取图片模板路径"""
        if not img_name: return None
        return os.path.join(self.paths["templates"], img_name)
    def get_task_target(self, mode_id):
        """统一获取某个模式的目标局数"""
        mode_control = self.user_config_data.get('mode_control', {})
        tasks = mode_control.get('tasks', [])
        for t in tasks:
            if t['id'] == mode_id:
                return t.get('target', 8)

        daily_tasks = self.user_config_data.get('daily_tasks', {})
        if mode_id in daily_tasks:
            return daily_tasks[mode_id].get('target_games', 8)

        return 5

    def get_resolution(self):
        """获取游戏分辨率配置"""
        res_config = self.user_config_data.get('resolution', {})
        width = res_config.get('width', 1920)
        height = res_config.get('height', 1080)
        return int(width), int(height)
    @property
    def current_password(self):
        """优先取用户设置的密码"""
        return self.user_config_data.get('room_password', self.config_data.get('room_password', '1234'))

    def reset_session(self):
        """重置房间会话文件"""
        p = self.get_path("room_session")
        if p and os.path.exists(p):
            try:
                os.remove(p)
                return True
            except:
                return False
        return False
    