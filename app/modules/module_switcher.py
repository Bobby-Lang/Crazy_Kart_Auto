# app/modules/module_switcher.py
# -*- coding: utf-8 -*-
import os
import json
import time
from datetime import datetime

class ModeSwitcher:
    def __init__(self, config_manager, engine):
        self.cfg = config_manager
        self.engine = engine
        
        # 路径配置 - 使用与 MainWindow 一致的 DATA_DIR
        self.state_path = os.path.join(self.cfg.DATA_DIR, "switcher_state.json")
        
        # 加载并检查是否需要重置
        self.state = self._load_and_check_daily_reset()
        
        # 房主开关 - 默认启用模式切换
        self.enabled = self.cfg.get_user_config('mode_control', {}).get('enabled', True)
        
        # 初始化当前目标
        self.current_target = 0
        self.refresh_config()

    def _load_and_check_daily_reset(self):
        """加载状态，并检查是否是新的一天"""
        today_str = datetime.now().strftime("%Y-%m-%d")
        
        default_state = {
            "update_date": today_str,
            "current_mode": "mode_item",
            # 使用字典记录每个模式的今日完成数
            "daily_progress": {
                "mode_item": 0,
                "mode_speed": 0
            }
        }

        if os.path.exists(self.state_path):
            try:
                with open(self.state_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    
                    # === 核心逻辑：日期比对 ===
                    last_date = data.get("update_date", "")
                    if last_date != today_str:
                        print(f"📅 [新的一天] 检测到日期变更 ({last_date} -> {today_str})，计数器已重置。")
                        return default_state  # 返回全新的初始状态
                    
                    # 如果是同一天，补全缺失字段并返回
                    if "daily_progress" not in data:
                        data["daily_progress"] = default_state["daily_progress"]
                    return data
            except:
                pass
        
        return default_state

    def _save_state(self):
        try:
            os.makedirs(os.path.dirname(self.state_path), exist_ok=True)
            with open(self.state_path, 'w', encoding='utf-8') as f:
                json.dump(self.state, f, indent=4)
        except: pass

    def refresh_config(self):
        """刷新当前模式的目标局数"""
        curr_id = self.state.get('current_mode', 'mode_item')
        self.current_target = self._get_target_for_mode(curr_id)
        
        # 打印当前进度
        progress = self.state["daily_progress"].get(curr_id, 0)
        # print(f"   [Switcher] 当前模式 {curr_id}: {progress}/{self.current_target}")

    def _get_mode_id_mapping(self, mode_or_name):
        """获取模式ID映射：支持中文和英文"""
        mode_configs = self.cfg.get_config('mode_configs', [])
        
        # 先尝试直接匹配英文ID
        for m in mode_configs:
            if m['id'] == mode_or_name:
                return m['id']
        
        # 再尝试匹配中文名称
        for m in mode_configs:
            if m['name'] == mode_or_name:
                return m['id']
        
        return mode_or_name  # 兜底返回原值

    def _get_target_for_mode(self, mode_id):
        """获取指定模式的目标局数"""
        # 标准化模式ID
        mode_id = self._get_mode_id_mapping(mode_id)
        
        tasks = self.cfg.get_user_config('mode_control', {}).get('tasks', [])
        # 优先读 user_config - 支持中英文ID
        for t in tasks:
            task_mode_id = self._get_mode_id_mapping(t['id'])
            if task_mode_id == mode_id:
                return t.get('target', 5)
        
        # 兜底读 config
        base_modes = self.cfg.get_config('mode_configs', [])
        for m in base_modes:
            if m['id'] == mode_id:
                return m.get('target_games', 5)
        return 5

    def sync_current_mode(self, detected_mode_id):
        """视觉同步：当提取到房间信息时调用"""
        if detected_mode_id == "unknown" or not detected_mode_id:
            return

        if self.state['current_mode'] != detected_mode_id:
            # print(f"🎯 [视觉同步] 修正模式: {self.state['current_mode']} -> {detected_mode_id}")
            self.state['current_mode'] = detected_mode_id
            self._save_state()
            self.refresh_config()

    def report_game_finished(self):
        """游戏结束调用：增加计数"""
        curr_id = self.state['current_mode']
        
        # 确保字典里有这个key
        if curr_id not in self.state["daily_progress"]:
            self.state["daily_progress"][curr_id] = 0
            
        self.state["daily_progress"][curr_id] += 1
        
        # 刷新配置，确保 current_target 是最新的
        self.refresh_config()
        
        # 显示所有模式的进度
        mode_configs = self.cfg.get_config("mode_configs", [])
        progress_parts = []
        for m in mode_configs:
            mode_id = m["id"]
            mode_name = m["name"]
            target = self._get_target_for_mode(mode_id)
            progress = self.state["daily_progress"].get(mode_id, 0)
            progress_parts.append(f"{mode_name}: {progress}/{target}")
        
        print(f"计数 {' | '.join(progress_parts)}")
        
        self._save_state()

    def manual_set_mode(self, mode_id):
        """TaskController 切换成功后调用"""
        self.state['current_mode'] = mode_id
        self._save_state()
        self.refresh_config()
        print(f"✅ [Switcher] 模式已更新为: {mode_id}")

    # ==========================================
    # 核心决策逻辑：告诉 Controller 该不该切模式
    # ==========================================
# app/modules/module_switcher.py

    def check_switch_condition(self):
        """检查是否应该切换模式"""
        curr_id = self.state['current_mode']
        curr_progress = self.state["daily_progress"].get(curr_id, 0)
        
        print(f"[Switcher] 检查切换条件 - 当前模式: {curr_id}, 进度: {curr_progress}/{self.current_target}, enabled={self.enabled}")
        
        # 如果当前模式还没做完，绝对不切（除非强制切换）
        if curr_progress < self.current_target:
            if not self.enabled:
                print(f"[Switcher] 当前模式未完成且切换已禁用，继续当前模式")
            else:
                print(f"[Switcher] 当前模式未完成，继续当前模式")
            return False, None

        # 当前模式做完了，寻找下一个
        mode_configs = self.cfg.get_config("mode_configs", [])
        all_ids = [m['id'] for m in mode_configs]
        
        print(f"[Switcher] 当前模式已完成，寻找下一个未完成模式 - 所有模式: {all_ids}")
        
        try:
            start_idx = (all_ids.index(curr_id) + 1) % len(all_ids)
        except ValueError:
            print(f"[Switcher] 警告: 当前模式 {curr_id} 不在配置列表中，从第一个开始")
            start_idx = 0
                
        for i in range(len(all_ids)):
            idx = (start_idx + i) % len(all_ids)
            check_id = all_ids[idx]
            
            # 这里的关键：如果试图切向的目标就是当前模式，说明转了一圈都没别的可做了
            if check_id == curr_id:
                print(f"[Switcher] 已遍历所有模式，都已完成，无需切换")
                break

            target = self._get_target_for_mode(check_id)
            done = self.state["daily_progress"].get(check_id, 0)
            
            print(f"[Switcher] 检查模式 {check_id}: 进度 {done}/{target}")
            
            if done < target:
                print(f"[Switcher] 找到未完成模式: {check_id}，准备切换")
                return True, mode_configs[idx]
        
        print(f"[Switcher] 所有模式都已完成，无需切换")
        return False, None
        
    def is_all_tasks_finished(self):
            """
            检查是否所有模式的任务进度都已经达到目标值
            """
            mode_configs = self.cfg.get_config("mode_configs", [])

            for m in mode_configs:
                check_id = m['id']
                target = self._get_target_for_mode(check_id)
                done = self.state["daily_progress"].get(check_id, 0)

                if done < target:
                    return False

            return True    