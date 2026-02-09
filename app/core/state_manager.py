# -*- coding: utf-8 -*-
"""
游戏状态管理器
负责管理游戏状态、对局计数、房间号、房主等
更新：支持 user_config 优先级，支持断电记忆
"""

import time
import threading
import os
import json
import win32gui

# 获取脚本目录
SCRIPT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

class GameStateManager:
    """游戏状态管理器"""

    def __init__(self, config_manager, logger=None):
        """
        Args:
            config_manager: 配置管理器
            logger: 日志记录器 (可选)
        """
        self.config_manager = config_manager
        self.logger = logger

        # 房主相关
        self.host_hwnd = None
        self.room_id = None
        self.current_mode = None

        # 计数器文件路径
        self.counter_path = os.path.join(self.config_manager.DATA_DIR, "mode_counts.json")

        # 对局计数
        self.game_counters = {}  # {mode_id: current_count}
        self.target_counters = {}  # {mode_id: target_count}

        # 窗口进度
        self.window_progress = {}

        # 线程锁
        self.lock = threading.Lock()

        # 初始化
        self._load_counters_from_file() # 先尝试读取旧存档
        self._init_targets() # 再读取配置文件设定目标

    def _log(self, level, msg):
        """内部简单的日志封装"""
        if self.logger:
            # 适配不同的 logger 接口，这里假设是 standard logging 或自定义的
            try:
                self.logger.log(0, level, msg)
            except:
                print(f"[{level}] {msg}")
        else:
            print(f"[{level}] {msg}")

    def _init_targets(self):
        """
        初始化目标局数
        优先级：user_config (mode_control) > user_config (daily_tasks) > config (mode_configs)
        """
        # 1. 获取所有可用模式 ID
        base_modes = self.config_manager.get_config('mode_configs', [])
        valid_mode_ids = [m['id'] for m in base_modes]

        # 2. 从 user_config 获取配置
        user_cfg = self.config_manager.get_user_config('mode_control', {})
        daily_cfg = self.config_manager.get_user_config('daily_tasks', {})
        
        # 3. 设定目标
        for mode_id in valid_mode_ids:
            target = 0
            
            # 策略A: 检查 mode_control.tasks (你的新配置)
            if user_cfg.get('enabled'):
                tasks = user_cfg.get('tasks', [])
                for t in tasks:
                    if t['id'] == mode_id and t.get('enabled', True):
                        target = t.get('target', 0)
                        break
            
            # 策略B: 如果上面没找到，检查 daily_tasks (旧配置兼容)
            if target == 0 and mode_id in daily_cfg:
                if daily_cfg[mode_id].get('enabled', True):
                    target = daily_cfg[mode_id].get('target_games', 0)

            # 策略C: 如果还没找到，用 config.json 默认值
            if target == 0:
                for m in base_modes:
                    if m['id'] == mode_id:
                        target = m.get('target_games', 5)
                        break
            
            self.target_counters[mode_id] = target
            
            # 确保 game_counters 有这个 key (如果没有从文件加载到的话)
            if mode_id not in self.game_counters:
                self.game_counters[mode_id] = 0

    def _load_counters_from_file(self):
        """从文件加载进度"""
        if os.path.exists(self.counter_path):
            try:
                with open(self.counter_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    # 简单校验，只加载今天的数据（可选：你可以根据需求决定是否跨天重置）
                    # 这里假设每次启动脚本都接着上次跑，除非手动重置
                    self.game_counters = data.get('counts', {})
                    self.current_mode = data.get('last_mode', None)
            except Exception as e:
                self._log("ERROR", f"读取进度文件失败: {e}")

    def _save_counters_to_file(self):
        """保存进度到文件"""
        data = {
            "timestamp": time.time(),
            "last_mode": self.current_mode,
            "counts": self.game_counters
        }
        try:
            with open(self.counter_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4)
        except Exception as e:
            self._log("ERROR", f"保存进度失败: {e}")

    # --- 核心逻辑 ---

    def increment_game_count(self, mode_id: str = None):
        """对局计数+1 并保存"""
        with self.lock:
            mode_id = mode_id or self.current_mode
            if not mode_id: return

            if mode_id not in self.game_counters:
                self.game_counters[mode_id] = 0

            self.game_counters[mode_id] += 1
            self._save_counters_to_file()  # 立即保存

            current = self.game_counters[mode_id]
            target = self.target_counters.get(mode_id, 0)
            mode_name = self._get_mode_name(mode_id)

            self._log("INFO", f"🏁 {mode_name} 第{current}局完成 ({current}/{target})")

    def get_progress(self, mode_id: str = None) -> tuple:
        """获取进度 (当前, 目标)"""
        with self.lock:
            mode_id = mode_id or self.current_mode
            current = self.game_counters.get(mode_id, 0)
            target = self.target_counters.get(mode_id, 0)
            return (current, target)

    def is_mode_completed(self, mode_id: str = None) -> bool:
        """检查当前模式是否达标"""
        current, target = self.get_progress(mode_id)
        return current >= target

    def is_all_modes_completed(self) -> bool:
        """检查是否所有启用的任务都已完成"""
        with self.lock:
            for mode_id, target in self.target_counters.items():
                if target > 0: # 只检查目标大于0的任务
                    current = self.game_counters.get(mode_id, 0)
                    if current < target:
                        return False
            return True

    def reset_all_modes(self):
        """重置所有计数"""
        with self.lock:
            for mode_id in self.game_counters:
                self.game_counters[mode_id] = 0
            self._save_counters_to_file()
            self._log("INFO", "已重置所有模式计数")

    # --- 辅助方法 ---

    def set_host_hwnd(self, hwnd: int):
        with self.lock:
            self.host_hwnd = hwnd

    def set_room_id(self, room_id: str):
        with self.lock:
            self.room_id = room_id

    def set_current_mode(self, mode_id: str):
        with self.lock:
            self.current_mode = mode_id
            self._save_counters_to_file() # 切换模式时也保存一下状态

    def get_current_mode(self) -> str:
        with self.lock:
            return self.current_mode

    def _get_mode_name(self, mode_id: str) -> str:
        modes = self.config_manager.get_config('mode_configs', [])
        for mode in modes:
            if mode.get('id') == mode_id:
                return mode.get('name', mode_id)
        return mode_id