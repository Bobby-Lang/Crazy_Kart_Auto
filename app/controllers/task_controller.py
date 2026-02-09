# -*- coding: utf-8 -*-
import time
import win32con
import os
import re
import json
import traceback
import threading
import win32api

from app.modules.room_in_module import RoomModule
from app.modules.module_switcher import ModeSwitcher
from app.modules.emergency_module import EmergencyModule
from app.modules.task_module import TaskModule

class WindowState:
    UNKNOWN  = "UNKNOWN"
    LOGIN    = "LOGIN"
    LOBBY    = "LOBBY"
    ROOM     = "ROOM"
    INGAME = "INGAME"
    CLAIMING = "CLAIMING"
    FINISHED = "FINISHED"

class TaskController:
    def __init__(self, combined_hwnd_list, config_manager, engine):
        self.windows = combined_hwnd_list
        self.cfg_mgr = config_manager
        self.engine = engine
        
        # 模块加载
        self.room_mod = RoomModule(config_manager, self.engine)
        self.switcher = ModeSwitcher(config_manager, self.engine)
        self.emergency_mod = EmergencyModule(config_manager, self.engine)
        self.task_mod = TaskModule(config_manager, self.engine)

        self.running = True
        self.active = True
        self.win_states = {}
        self.action_cd = {}
        self.last_log = {}
        self.mode_switching = {hwnd: False for _, hwnd, _ in self.windows}

        # 热键
        self.pause_key = self._get_vk_code(self.cfg_mgr.get_config("pause_hotkey", "f9"))
        self.stop_key = self._get_vk_code(self.cfg_mgr.get_config("stop_hotkey", "f10"))
        self.reset_key = self._get_vk_code(self.cfg_mgr.get_config("reset_hotkey", "f8"))

        self._cleanup_session()
        self._init_window_states()
        self._start_hotkey_listener()
        # 记录每局开始的时间，用于超时锁定保护（防止游戏崩溃后永久卡在 INGAME）
        self.game_start_time = {}
        # 记录房主进入房间的时间，用于检测游戏异常中断后的房间死锁
        self.host_room_enter_time = {}
        # 【新增】记录本局已回到房间的窗口，用于同步
        self.back_to_room_set = set()
        # 【新增】游戏结束后的同步等待标记
        self.waiting_for_all_back = False
        # 【新增】记录当前房主，避免重复日志
        self._current_host = None
        
        # 启动Emergency独立检测线程
        self.emergency_mod.start(self.windows)
        
        print(f"调度中心就绪 | 窗口总数: {len(self.windows)}")

    def _init_window_states(self):
        for idx, hwnd, acc in self.windows:
            self.win_states[hwnd] = {
                "index": idx,
                "account": acc,
                "state": WindowState.UNKNOWN,
                "login_step_idx": 0,
                "retry_count": 0
            }

    def _get_vk_code(self, key_str):
        ks = str(key_str).lower().strip()
        if ks.startswith("f"): return getattr(win32con, f"VK_F{ks[1:]}")
        return win32con.VK_SPACE

    def _cleanup_session(self):
        """重置房间 Session 和任务进度"""
        # 清理房间 session
        p = self.cfg_mgr.get_path("room_session")
        if p and os.path.exists(p):
            try:
                os.remove(p)
                print("已重置房间 Session 记录")
            except: pass
        
        # 【新增】清理任务进度文件，支持手动重置任务
        switcher_state_path = os.path.join(
            os.path.dirname(p) if p else os.getcwd(),
            "switcher_state.json"
        )
        if os.path.exists(switcher_state_path):
            try:
                os.remove(switcher_state_path)
                print("已重置任务进度记录")
            except: pass
        
        # 【新增】重新初始化 ModeSwitcher 状态
        try:
            self.switcher.state = self.switcher._load_and_check_daily_reset()
            self.switcher.refresh_config()
            print("任务进度已重置，可重新开始任务")
        except Exception as e:
            print(f"重置进度时出错: {e}")

    def _log(self, hwnd, msg, ctx=None):
        data = self.win_states[hwnd]
        # 角色识别：优先使用 ctx 中的 host_h，其次使用 self._current_host
        if ctx and ctx.get("host_h"):
            role = "host" if hwnd == ctx.get("host_h") else "member"
        else:
            role = "host" if hwnd == self._current_host else "member"
        full = f"[窗口{data['index']}][{role}] {msg}"
        if self.last_log.get(hwnd) != full:
            print(full)
            self.last_log[hwnd] = full

    def start_monitor(self):
        loop_count = 0
        print("[系统] 主监控循环已启动")
        
        while self.running:
            loop_count += 1
            
            if not self.active:
                time.sleep(1.0); continue

            try:
                ctx = self._get_global_context()
                
                # 检查是否所有任务都已完成且已领奖结束
                if ctx.get("all_done"):
                    all_finished = all(
                        self.win_states[hwnd]["state"] == WindowState.FINISHED 
                        for _, hwnd, _ in self.windows
                    )
                    if all_finished:
                        print("[系统] 所有任务已完成，脚本自动停止")
                        self.running = False
                        break

                for _, hwnd, _ in self.windows:
                    # 1. 常规逻辑的冷却判断（emergency由独立线程处理，不再重复检测）
                    if time.time() < self.action_cd.get(hwnd, 0):
                        continue

                    self._process_fsm(hwnd, ctx)

            except Exception as e:
                print(f"逻辑异常: {e}")
                traceback.print_exc()
            
            time.sleep(0.1)  # 加快扫描频率到0.1秒
        
        # 停止Emergency检测线程
        self.emergency_mod.stop()
        print("[系统] 脚本已安全退出")

    def _get_global_context(self):
        session = self._load_session_file()
        ctx = {
            "sid": session.get("room_id"),
            "host_h": session.get("host_hwnd"),
            "curr_mode_id": session.get("mode"),
            "members_in_room": [],
            "members_ready": [],
            "all_done": self.switcher.is_all_tasks_finished()
        }
        
        # 【关键修复】动态识别房主：在房间状态下总是重新检测"开始"按钮
        # 游戏结束后房主可能变化，需要实时识别
        detected_host = None
        for _, hwnd, _ in self.windows:
            if self.room_mod.has_start_button(hwnd):
                detected_host = hwnd
                break
        
        # 如果检测到了新房主，更新上下文（只在真正变化时打印）
        if detected_host:
            if self._current_host != detected_host:
                print(f"[系统] 房主识别：窗口 {detected_host} 有开始按钮，设为新房主")
                self._current_host = detected_host
            ctx["host_h"] = detected_host
        
        # 记录候选房主（用于大厅状态创房）
        ctx["candidate_host"] = ctx["host_h"] or (self.windows[0][1] if self.windows else None)
        
        for _, hwnd, _ in self.windows:
            state_data = self.win_states[hwnd]
            prev_state = state_data["state"] # 记录上一次的状态，用于逻辑推导

            # --- 步骤 1： 视觉事实检测 (依靠图片匹配) ---
            is_room = self.room_mod.is_in_room(hwnd)
            is_lobby = self.room_mod.is_in_lobby(hwnd)

            # --- 步骤 2： 状态机判定逻辑 ---
            
            # A. 确定在房间里
            if is_room:
                # 【修复】检测窗口是否在游戏中且现在回到了房间
                # 记录该窗口已回到房间（无论从什么状态过来）
                # 简化逻辑：只要 waiting_for_all_back 为 True，说明上一局刚结束，此时在房间的都算回来了
                should_record = (hwnd in self.game_start_time or 
                                prev_state == WindowState.INGAME or 
                                self.waiting_for_all_back)
                
                if should_record and hwnd not in self.back_to_room_set:
                    self.back_to_room_set.add(hwnd)
                    # 检查是否所有窗口都已回到房间
                    total_windows = len(self.windows)
                    back_count = len(self.back_to_room_set)
                    
                    if back_count >= total_windows:
                        # 所有窗口都回来了，清除游戏开始时间，准备下一局
                        self._log(hwnd, f"所有窗口已回到房间 ({back_count}/{total_windows})，准备下一局", ctx)
                        for _, h, _ in self.windows:
                            if h in self.game_start_time:
                                del self.game_start_time[h]
                        # 清空集合，为下一局做准备
                        self.back_to_room_set.clear()
                        self.waiting_for_all_back = False
                    else:
                        # 还有窗口没回来，标记等待状态
                        self.waiting_for_all_back = True
                        self._log(hwnd, f"游戏结束，等待其他窗口回到房间 ({back_count}/{total_windows})...", ctx)
                state_data["state"] = WindowState.ROOM
                # 【修复】基于动态识别的房主判断成员（非房主即为成员）
                if hwnd != ctx.get("host_h"):
                    ctx["members_in_room"].append(hwnd)
                    if self.room_mod.is_member_ready(hwnd):
                        ctx["members_ready"].append(hwnd)

            # B. 确定在大厅里
            elif is_lobby:
                # 【修复】不覆盖领奖中和已完成的状态，避免视觉检测干扰领奖流程
                if state_data["state"] not in [WindowState.CLAIMING, WindowState.FINISHED]:
                    state_data["state"] = WindowState.LOBBY

            # C. 视觉匹配失败时的【逻辑推导】
            else:
                # 情况 1：从房间突然消失 -> 说明"开跑了" (INGAME)
                if prev_state == WindowState.ROOM:
                    self._log(hwnd, "画面转换：从房间进入比赛", ctx)
                    state_data["state"] = WindowState.INGAME
                    self.game_start_time[hwnd] = time.time()
                
                # 情况 2：维持 INGAME 状态
                elif prev_state == WindowState.INGAME:
                    # 检查是否超时（10分钟），防止游戏奔溃卡死
                    if time.time() - self.game_start_time.get(hwnd, 0) > 600:
                        self._log(hwnd, "比赛时间过长，强制重置为未知状态", ctx)
                        state_data["state"] = WindowState.UNKNOWN
                    else:
                        state_data["state"] = WindowState.INGAME # 保持

                # 情况 3：既不是开跑，也不在大厅房间 -> 尝试识别登录界面
                else:
                    if self._check_is_login_ui(hwnd): # 需要在下方定义这个辅助方法
                        state_data["state"] = WindowState.LOGIN
                    else:
                        state_data["state"] = WindowState.UNKNOWN

        return ctx

    def _check_is_login_ui(self, hwnd):
        """
        【修复核心】检查是否在登录流程中 (包括：账号输入、登录序列中的任意一步)
        只要匹配到配置中定义的任何一张登录相关图片，即返回 True
        """
        # 1. 检查 pre_login (最底层：大区选择、账号输入框)
        login_cfg = self.cfg_mgr.get_config("pre_login", {})
        if login_cfg:
            for key, step_cfg in login_cfg.items():
                img_name = step_cfg.get("check_img")
                if not img_name: continue
                img_path = self.cfg_mgr.get_template_path(img_name)
                threshold = step_cfg.get("match_threshold", 0.7)
                if self.engine.match_template(hwnd, img_path, threshold)[0]:
                    return True
        
        # 2. 【关键新增】检查 login_sequence (登录按钮、服务器、进入游戏等)
        # 如果游戏停在登录序列的任何一步，都 应该被识别为 LOGIN，否则会变成 UNKNOWN 卡死
        seq = self.cfg_mgr.get_config("login_sequence", [])
        for step in seq:
            img_name = step.get("check_img")
            if not img_name: continue
            img_path = self.cfg_mgr.get_template_path(img_name)
            threshold = step.get("match_threshold", 0.7)
            if self.engine.match_template(hwnd, img_path, threshold)[0]:
                return True

        return False

    def _process_fsm(self, hwnd, ctx):
        data = self.win_states[hwnd]
        s = data["state"]
        
        if ctx.get("all_done") :
            if s== WindowState.FINISHED:
                # 任务已完全结束，不再执行任何操作，只保持长冷却
                self.action_cd[hwnd] = time.time() + 10.0
                return
            if s == WindowState.INGAME:
                self._log(hwnd, "任务已达成，正在游戏中，等待回到房间...", ctx)
                return
            if s== WindowState.ROOM:
                self._log(hwnd, "任务已达成，正在退出房间准备领奖...", ctx)
                self.engine.key_press(hwnd, win32con.VK_BACK)
                self.action_cd[hwnd] = time.time() + 3.0
                return
            if s == WindowState.LOBBY:
                self._log(hwnd, "任务已达成，准备领奖...", ctx)
                data["state"] = WindowState.CLAIMING
                return
            if s == WindowState.CLAIMING:
                # 执行领奖流程
                self._handle_claiming(hwnd, data, ctx)
                return

        if s == WindowState.INGAME:
            # 检查游戏是否结束（回到房间）
            is_room = self.room_mod.is_in_room(hwnd)
            is_lobby = self.room_mod.is_in_lobby(hwnd)
            
            # 如果不在房间且不在大厅，尝试等待一小段时间后再检测
            if not is_room and not is_lobby:
                # 快速重试检测（游戏结束画面加载可能有延迟）
                time.sleep(0.3)
                is_room = self.room_mod.is_in_room(hwnd)
                if not is_room:
                    is_lobby = self.room_mod.is_in_lobby(hwnd)
            
            if is_room or is_lobby:
                self._log(hwnd, f"游戏结束，回到{'房间' if is_room else '大厅'}", ctx)
                data["state"] = WindowState.ROOM if is_room else WindowState.LOBBY
                # 重置游戏开始时间
                for _, h, _ in self.windows:
                    if h in self.game_start_time:
                        del self.game_start_time[h]
                return
            else:
                # 如果游戏开始时间超过一定时间，强制重置为ROOM（防止卡死）
                if hwnd in self.game_start_time:
                    elapsed = time.time() - self.game_start_time[hwnd]
                    if elapsed > 360:  # 6分钟超时（游戏正常4-5分钟）
                        self._log(hwnd, "游戏超时，重置状态为房间", ctx)
                        del self.game_start_time[hwnd]
                        data["state"] = WindowState.ROOM  # 超时后假定回到房间
                        return
                return
        if s == WindowState.ROOM:
            self._handle_room(hwnd, data, ctx)
        elif s == WindowState.LOBBY:
            self._handle_lobby(hwnd, data, ctx)
        elif s == WindowState.LOGIN:
            self._handle_login(hwnd, data, ctx)
        elif s == WindowState.CLAIMING:
            self._handle_claiming(hwnd, data, ctx)

    def _handle_login(self, hwnd, data, ctx):
        """修复登录流程，添加诊断日志"""
        
        # 1. 检查大区/闪屏跳过
        skip_cfg = self.cfg_mgr.get_config("pre_login.region_skip")
        if skip_cfg:
            img = self.cfg_mgr.get_template_path(skip_cfg["check_img"])
            found, _, _ = self.engine.match_template(hwnd, img, skip_cfg.get("match_threshold", 0.7))
            if found:
                self._log(hwnd, f"诊断：匹配到 {skip_cfg['check_img']}，执行跳过动作", ctx)
                self.engine.key_press(hwnd, win32con.VK_SPACE)
                self.action_cd[hwnd] = time.time() + 1.0
                return

        # 2. 检查账号输入框
        input_cfg = self.cfg_mgr.get_config("pre_login.account_input")
        idx_img = self.cfg_mgr.get_template_path(input_cfg["check_img"])
        if self.engine.match_template(hwnd, idx_img, 0.75)[0]:
            self._log(hwnd, "诊断：发现账号输入界面，开始录入...", ctx)
            self._execute_account_input(hwnd, data["account"])
            data["login_step_idx"] = 0
            self.action_cd[hwnd] = time.time() + 2.0
            return

        # 3. 登录步进序列 (login_sequence)
        seq = self.cfg_mgr.get_config("login_sequence", [])
        if data["login_step_idx"] < len(seq):
            step = seq[data["login_step_idx"]]
            img_path = self.cfg_mgr.get_template_path(step["check_img"])
            found, score, _ = self.engine.match_template(hwnd, img_path, step.get("match_threshold", 0.7))
            
            if found:
                self._log(hwnd, f"阶段：{step['name']} | 匹配成功({score:.2f})", ctx)
                self.engine.click(hwnd, step["coord"][0], step["coord"][1])
                data["login_step_idx"] += 1
                self.action_cd[hwnd] = time.time() + 1.0
            else:
                # 盲按空格尝试唤醒可能被遮挡的画面
                self.engine.key_press(hwnd, win32con.VK_SPACE)
                self.action_cd[hwnd] = time.time() + 1.0

    def _handle_room(self, hwnd, data, ctx):
        if ctx["all_done"]:
            self._log(hwnd, "任务全达成，功德圆满。", ctx)
            self.engine.key_press(hwnd, win32con.VK_BACK)
            self.action_cd[hwnd] = time.time() + 5.0
            return
        
        # 【修复】游戏结束后等待所有窗口回到房间再执行操作
        # 避免新房主抢先点击开始，而旧房主还没回来的情况
        if self.waiting_for_all_back:
            back_count = len(self.back_to_room_set)
            total = len(self.windows)
            self._log(hwnd, f"等待同步中... ({back_count}/{total} 窗口已回到房间)", ctx)
            self.action_cd[hwnd] = time.time() + 1.0
            return
        
        # 【修复】如果房主还没识别（比如刚从大厅创房回来），等待识别完成
        if ctx.get("host_h") is None:
            self._log(hwnd, "等待房主识别...", ctx)
            self.action_cd[hwnd] = time.time() + 0.5
            return
        
        # 动态判断是否是房主（使用host_hwnd而不是静态role）
        is_host = (hwnd == ctx.get("host_h"))
        
        if is_host:
            # 【修复】房主房间超时保护：检测游戏异常中断后的房间死锁
            # 【修复】增加 host_h 检查：如果房主还没识别（host_h为None），不执行超时检测
            if ctx["sid"] and ctx.get("host_h") and len(ctx["members_in_room"]) == 0:
                now = time.time()
                enter_time = self.host_room_enter_time.get(hwnd, now)
                self.host_room_enter_time[hwnd] = enter_time
                if now - enter_time > 20.0:  # 20秒无成员加入，判定为异常房间
                    self._log(hwnd, "房间异常：长时间无成员加入，重置并重新创房", ctx)
                    self._cleanup_session()
                    self.host_room_enter_time.pop(hwnd, None)
                    self.action_cd[hwnd] = time.time() + 3.0
                    return
            else:
                # 成员已加入或host_h未识别，重置计时器
                self.host_room_enter_time.pop(hwnd, None)
            
            # 1. 如果没有存过房间信息，识别一次（模式可以为空）
            if not ctx["sid"]:
                rid, mode_id = self.extract_room_info_logic(hwnd)
                if rid:
                    self.save_room_session(rid, hwnd, mode_id)
                    if mode_id: self.switcher.sync_current_mode(mode_id)
                return
            # 2. 判断是否需要切换模型 (由 Switcher 内部状态决定)
            should_switch, target_cfg = self.switcher.check_switch_condition()
            
            # 关键：识别到当前在跑的模式确实和目标不一样，才切
            if should_switch and ctx['curr_mode_id'] and target_cfg and target_cfg['id'] != ctx['curr_mode_id']:
                self._log(hwnd, f"切换模式: {ctx['curr_mode_id'] or '未知'} -> {target_cfg['id']}", ctx)
                if self._perform_mode_switch(hwnd, target_cfg):
                    # 切换成功后手动更新 Session 里的模式，防止下一秒又切
                    if ctx["sid"]:
                        self.save_room_session(ctx["sid"], hwnd, target_cfg['id'])
                    # 同步切换器状态
                    self.switcher.sync_current_mode(target_cfg['id'])
                else:
                    # 切换失败，保持当前模式
                    self._log(hwnd, f"模式切换失败，保持当前模式: {ctx['curr_mode_id'] or '未知'}", ctx)
                self.action_cd[hwnd] = time.time() + 5.0
                return
            # 3. 起跑逻辑
            needed = len(self.windows) - 1
            if len(ctx["members_in_room"]) >= needed and len(ctx["members_ready"]) >= needed:
                # 获取模式中文名
                mode_name = ctx['curr_mode_id'] or '未知模式'
                for m in self.cfg_mgr.get_config("mode_configs", []):
                    if m["id"] == ctx['curr_mode_id']:
                        mode_name = m["name"]
                        break
                self._log(hwnd, f"确认无误，房主起跑 ({mode_name})", ctx)
                if self.room_mod.click_start(hwnd):
                    # 广播开始时间
                    for _, h, _ in self.windows: 
                        self.game_start_time[h] = time.time()
                    self.switcher.report_game_finished()
                    # 清除房间进入计时器
                    self.host_room_enter_time.pop(hwnd, None)
                    self.action_cd[hwnd] = time.time() + 8.0
            else:
                self._log(hwnd, f"等待准备: {len(ctx['members_ready'])}/{needed}", ctx)
        else:
            # 成员逻辑
            # 多重检查：如果游戏已经开始，绝对不要点击准备
            if data["state"] == WindowState.INGAME:
                self._log(hwnd, "游戏进行中，跳过准备操作", ctx)
                return
            
            # 检查是否有窗口已经开始游戏了
            has_game_started = any(self.game_start_time.get(h, 0) > 0 for _, h, _ in self.windows)
            if has_game_started:
                self._log(hwnd, "检测到游戏已开始，跳过准备操作", ctx)
                return
                
            # 双重检查：既要在房间内，又不能是准备状态
            if data["state"] == WindowState.ROOM and not self.room_mod.is_member_ready(hwnd):
                # 点击准备按钮并检查是否成功
                if self.room_mod.click_ready(hwnd):
                    self._log(hwnd, "准备成功", ctx)
                else:
                    self._log(hwnd, "准备点击失败，重试中", ctx)
                self.action_cd[hwnd] = time.time() + 1.0

    def _handle_lobby(self, hwnd, data, ctx):
        if ctx.get("all_done"):
            return
        
        # 【修复】大厅状态使用候选房主创房，进入房间后通过"开始"按钮确认真实房主
        is_host = (hwnd == ctx.get("host_h")) or (ctx.get("host_h") is None and hwnd == ctx.get("candidate_host"))
        
        if is_host:
            if not ctx["sid"]:
                self._log(hwnd, "创房中...", ctx)
                for s in self.cfg_mgr.get_config("room_creation", []):
                    self._execute_config_step(hwnd, s)
                    time.sleep(0.8)
                
                # 【修复】创房后使用当前目标模式，不强制重置为道具赛
                current_mode = self.switcher.state.get('current_mode', 'mode_item')
                self._log(hwnd, f"创房使用当前模式: {current_mode}", ctx)
                
                # 创房后提取房间号并保存session
                self._log(hwnd, "提取房间号...", ctx)
                room_id = self._extract_room_number(hwnd)
                if room_id:
                    self._log(hwnd, f"创房成功，房间号: {room_id}", ctx)
                    self.save_room_session(room_id, hwnd, current_mode)
                else:
                    self._log(hwnd, "提取房间号失败，使用默认ID", ctx)
                    self.save_room_session("unknown", hwnd, current_mode)
                
                # 创房后需要等待成员加入，所以设置短暂延迟
                self._log(hwnd, "等待成员加入房间...", ctx)
                time.sleep(1.5)  # 等待成员加房
        else:
            # 成员逻辑
            if ctx["sid"] and ctx["sid"] != "unknown":
                self._log(hwnd, f"加入房间: {ctx['sid']}", ctx)
                self._execute_join_cmd(hwnd, ctx["sid"])
                self.action_cd[hwnd] = time.time() + 2.0

    def _handle_claiming(self, hwnd, data, ctx):
        # 只让第一个到达领奖状态的窗口执行领奖
        # 检查是否已有其他窗口在执行领奖
        claiming_windows = [h for h, d in self.win_states.items() if d["state"] == WindowState.CLAIMING]
        if len(claiming_windows) > 1 and hwnd != claiming_windows[0]:
            # 不是第一个，等待
            self._log(hwnd, "等待其他窗口领奖...", ctx)
            self.action_cd[hwnd] = time.time() + 1.0
            return
        
        # 检查是否在大厅，如果不在则先回到大厅
        is_lobby = self.room_mod.is_in_lobby(hwnd)
        if not is_lobby:
            self._log(hwnd, "不在大厅，尝试返回...", ctx)
            self.engine.key_press(hwnd, win32con.VK_BACK)
            time.sleep(1.0)
            is_lobby = self.room_mod.is_in_lobby(hwnd)
            if not is_lobby:
                self._log(hwnd, "返回大厅失败，稍后重试", ctx)
                self.action_cd[hwnd] = time.time() + 1.0
                return
        
        try:
            self._log(hwnd, "开始执行领奖流程...", ctx)
            self.task_mod.run(hwnd)
            data["state"] = WindowState.FINISHED
            self._log(hwnd, "领奖完成，任务结束。", ctx)
        except Exception as e:
            self._log(hwnd, f"领奖过程出错: {e}", ctx)
            traceback.print_exc()
        # 领奖完成后设置冷却时间，防止重复执行
        self.action_cd[hwnd] = time.time() + 10.0

    def _perform_mode_switch(self, hwnd, target_mode_cfg):
        self.mode_switching[hwnd] = True
        c = self.cfg_mgr.get_config("coords")
        self.engine.click(hwnd, c["room_management"][0], c["room_management"][1])
        time.sleep(1.5)
        
        # 获取ROI区域
        mode_selection_roi = self.cfg_mgr.get_config("rois", {}).get("mode_selection", None)
        
        # 获取所有模式配置，用于识别当前模式
        all_mode_configs = self.cfg_mgr.get_config("mode_configs", [])
        
        # 模式切换：点击切换坐标，然后验证是否是目标模式
        switched = False
        
        for attempt in range(3):
            # 1. 点击模式切换坐标
            self.engine.click(hwnd, target_mode_cfg["click_coord"][0], target_mode_cfg["click_coord"][1])
            time.sleep(0.8)
            
            # 2. 识别当前模式
            current_mode_id = None
            for mode_cfg in all_mode_configs:
                check_img_path = self.cfg_mgr.get_template_path(mode_cfg["rule_img"])
                found, score, _ = self.engine.match_template(hwnd, check_img_path, 0.8, mode_selection_roi)
                if found:
                    current_mode_id = mode_cfg["id"]
                    self._log(hwnd, f"识别到当前模式: {mode_cfg['name']} (置信度: {score:.4f})")
                    break
            
            # 3. 判断是否切换成功
            if current_mode_id == target_mode_cfg["id"]:
                self._log(hwnd, f"模式切换成功: {target_mode_cfg['name']}")
                switched = True
                break
            else:
                self._log(hwnd, f"尝试 {attempt + 1}/3: 当前是 {current_mode_id or '未知'}，目标 {target_mode_cfg['name']}")
                if attempt < 2:
                    time.sleep(0.5)  # 等待界面更新
        
        if not switched:
            self._log(hwnd, f"模式切换失败，未能切换到 {target_mode_cfg['name']}")
        
        # 点击确认
        time.sleep(0.5)
        self.engine.click(hwnd, c["confirm"][0], c["confirm"][1])
        time.sleep(1.0)
        
        self.mode_switching[hwnd] = False
        return switched

    def _execute_config_step(self, hwnd, step):
        c = step.get("coord")
        self.engine.click(hwnd, c[0], c[1])
        if step.get("type") == "input_text":
            time.sleep(0.5)
            self.engine.type_text(hwnd, 0, 0, str(self.cfg_mgr.current_password))

    def _execute_join_cmd(self, hwnd, rid):
        chat = self.cfg_mgr.get_config("chat_input_coord", [300, 1060])
        self.engine.click(hwnd, chat[0], chat[1])
        time.sleep(0.5)
        self.engine.type_text(hwnd, 0, 0, f"##{rid} {self.cfg_mgr.current_password}")
        self.engine.key_press(hwnd, win32con.VK_RETURN)

    def _execute_account_input(self, hwnd, acc):
        c = self.cfg_mgr.get_config("input_coords")
        u, p = acc.get("username") or acc.get("user"), acc.get("password") or acc.get("pass")
        self.engine.type_text(hwnd, c["acc_input"][0], c["acc_input"][1], u)
        time.sleep(0.5)
        self.engine.type_text(hwnd, c["pwd_input"][0], c["pwd_input"][1], p)
        self.engine.key_press(hwnd, win32con.VK_RETURN)

    def extract_room_info_logic(self, hwnd, skip_menu=False):
        seq = self.cfg_mgr.get_config("get_room_name_sequence", [])
        for i, s in enumerate(seq):
            if i == 0 and skip_menu: continue
            self.engine.click(hwnd, s["coord"][0], s["coord"][1])
            if s.get("type") == "select_and_copy":
                time.sleep(0.5)
                self.engine.ctrl_a_c(hwnd)
            time.sleep(1.0)
        
        text = self.engine.get_clipboard_text()
        rid_list = re.findall(r"\d+", str(text))
        rid = rid_list[-1] if rid_list else None
        
        # 【修复】尝试识别当前模式，识别不到则使用 switcher 中的当前模式
        cur_mode = None
        for m in self.cfg_mgr.get_config("mode_configs", []):
            img_p = self.cfg_mgr.get_template_path(m["rule_img"])
            if img_p and self.engine.match_template(hwnd, img_p, 0.8)[0]:
                cur_mode = m["id"]
                self._log(hwnd, f"识别到模式: {m['name']}", None)
                break
        
        if not cur_mode:
            # 识别不到，使用 switcher 中记录的模式
            cur_mode = self.switcher.state.get('current_mode', 'mode_item')
            self._log(hwnd, f"识别不到模式，使用记录的模式: {cur_mode}", None)
        
        return rid, cur_mode
    
    def _extract_room_number(self, hwnd):
        """提取房间号（简化版，只提取房间号）"""
        seq = self.cfg_mgr.get_config("get_room_name_sequence", [])
        for i, s in enumerate(seq):
            coord = s.get("coord", [0, 0])
            self.engine.click(hwnd, coord[0], coord[1])
            if s.get("type") == "select_and_copy":
                time.sleep(0.5)
                self.engine.ctrl_a_c(hwnd)
            time.sleep(0.8)
        
        # 提取房间号
        text = self.engine.get_clipboard_text()
        rid_list = re.findall(r"\d+", str(text))
        return rid_list[-1] if rid_list else None
    
    def save_room_session(self, rid, hwnd, mode):
        p = self.cfg_mgr.get_path("room_session")
        with open(p, "w", encoding="utf-8") as f:
            json.dump({"room_id": str(rid), "host_hwnd": int(hwnd), "mode": mode, "timestamp": time.time()}, f)
        self._log(hwnd, f"广播 Session: {rid}")

    def _load_session_file(self):
        p = self.cfg_mgr.get_path("room_session")
        if p and os.path.exists(p):
            try:
                with open(p, "r", encoding="utf-8") as f:
                    d = json.load(f)
                    if time.time() - d.get("timestamp", 0) < 600: return d
            except: pass
        return {}

    def _start_hotkey_listener(self):
        def listener():
            last_p = False
            last_r = False
            while self.running:
                # 暂停/恢复热键
                p_down = win32api.GetAsyncKeyState(self.pause_key) & 0x8000
                if p_down and not last_p:
                    self.active = not self.active
                    print(f"\n[系统] {'恢复' if self.active else '暂停'}")
                last_p = bool(p_down)
                
                # 停止热键
                if win32api.GetAsyncKeyState(self.stop_key) & 0x8000:
                    os._exit(0)
                
                # 【新增】重置任务热键
                r_down = win32api.GetAsyncKeyState(self.reset_key) & 0x8000
                if r_down and not last_r:
                    print("\n[系统] 重置任务进度...")
                    self._cleanup_session()
                    # 重置所有窗口状态
                    for _, hwnd, _ in self.windows:
                        if hwnd in self.win_states:
                            self.win_states[hwnd]["state"] = WindowState.UNKNOWN
                            self.win_states[hwnd]["login_step_idx"] = 0
                            self.win_states[hwnd]["retry_count"] = 0
                        if hwnd in self.action_cd:
                            del self.action_cd[hwnd]
                        if hwnd in self.game_start_time:
                            del self.game_start_time[hwnd]
                        if hwnd in self.host_room_enter_time:
                            del self.host_room_enter_time[hwnd]
                    print("[系统] 任务已重置，将重新开始")
                last_r = bool(r_down)
                
                time.sleep(0.05)
        threading.Thread(target=listener, daemon=True).start()
