# -*- coding: utf-8 -*-
"""
状态机入口模块（原 AutoGameFlow 重构）
将原 flow_module 中的 AutoGameFlow 重命名为 AutoGameStateMachine，
保持相同的功能接口，供 UI 层调用。
"""

import os
import sys
import time
import json
import traceback
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QCoreApplication

# 确保项目根目录在 sys.path 中
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, "..", ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from app.core.config_manager import ConfigManager
from app.core.game_engine import GameEngine
from app.controllers.task_controller import TaskController
from app.modules.launcher_module import LauncherModule


class AutoGameStateMachine:
    """全自动运行的状态机入口
    功能与旧的 AutoGameFlow 基本一致，只是类名更直观。
    """

    def __init__(self, config_manager=None):
        self.cfg_mgr = config_manager or ConfigManager()
        self.engine = GameEngine(self.cfg_mgr)
        self.launcher = None
        self.controller = None
        self.qapp = None
        self.launcher_finished = False
        self.launcher_success = False

    def execute_full_flow(self) -> bool:
        """执行完整的启动‑调度流程，返回成功与否"""
        os.system('cls' if os.name == 'nt' else 'clear')
        print("自动游戏全集成启动流程")
        try:
            self._cleanup_environment()
            if not self._launch_windows():
                return False
            if not self._start_controller():
                return False
            return True
        except Exception as e:
            print(f"流程异常中断: {e}")
            traceback.print_exc()
            return False

    # ---------------------------------------------------------------------
    # 私有帮助方法
    # ---------------------------------------------------------------------
    def _cleanup_environment(self) -> None:
        """删除旧的 session / 结果文件，以防干扰"""
        for key in ("room_session", "window_results"):
            p = self.cfg_mgr.get_path(key)
            if p and os.path.exists(p):
                try:
                    os.remove(p)
                    print(f"清理旧文件: {os.path.basename(p)}")
                except Exception:
                    pass

    def _launch_windows(self) -> bool:
        """读取账号并启动游戏窗口，返回是否成功"""
        # 读取账号
        accounts_path = self.cfg_mgr.get_path('accounts')
        accounts = []
        if accounts_path and os.path.exists(accounts_path):
            with open(accounts_path, 'r', encoding='utf-8') as f:
                for line in f:
                    if "," in line:
                        u, p = line.strip().split(",")
                        accounts.append({"username": u, "password": p})
        if not accounts:
            print("❌ 错误: accounts.txt 为空或不存在")
            return False
        # 配置路径（若未在 user_config 中设置则使用默认硬编码）
        box_path = self.cfg_mgr.get_user_config('paths.box_path',
                                               r'D:\DataBase\game\auto_game\app\2Box.exe')
        game_path = self.cfg_mgr.get_user_config('paths.game_path',
                                                r'D:\CrazyKart\CrazyKart\CrazyKart.exe')
        # 创建或获取 QApplication 实例
        if not QCoreApplication.instance():
            self.qapp = QApplication(sys.argv)
        else:
            self.qapp = QCoreApplication.instance()
        # 初始化 Launcher
        self.launcher = LauncherModule(
            box_path=box_path,
            game_path=game_path,
            accounts=accounts,
            config_manager=self.cfg_mgr,
            logger=None,
        )
        self.launcher.all_ready.connect(self._on_launcher_ready)
        self.launcher.finished.connect(self._on_launcher_finished)
        # 启动
        try:
            self.launcher.start()
            timeout = 300  # 5 分钟超时
            start_time = time.time()
            results_path = self.cfg_mgr.get_path("window_results")
            while time.time() - start_time < timeout and not self.launcher_finished:
                if self.qapp:
                    self.qapp.processEvents()
                if results_path and os.path.exists(results_path):
                    try:
                        with open(results_path, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                        if len(data) >= len(accounts):
                            print(f"所有窗口已就绪 ({len(data)}/{len(accounts)})")
                            self.launcher_finished = True
                            self.launcher_success = True
                    except Exception:
                        pass
                time.sleep(0.5)
            if self.launcher_finished and self.launcher_success:
                return True
            if not self.launcher_finished:
                print("⏳ 启动窗口超时")
            else:
                print("❌ Launcher 执行失败")
            return False
        except Exception as e:
            print(f"❌ Launcher 运行异常: {e}")
            traceback.print_exc()
            return False

    def _on_launcher_ready(self) -> None:
        self.launcher_finished = True
        self.launcher_success = True

    def _on_launcher_finished(self) -> None:
        if not self.launcher_finished:
            self.launcher_finished = True
            self.launcher_success = False

    def _start_controller(self) -> bool:
        """读取窗口信息并启动任务调度中心"""
        results_path = self.cfg_mgr.get_path("window_results")
        if not results_path or not os.path.exists(results_path):
            return False
        try:
            with open(results_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            combined_list = [(i["index"], i["hwnd"], i) for i in data]
            if not combined_list:
                return False
            print(f"调度中心接管 {len(combined_list)} 个窗口任务")
            self.controller = TaskController(combined_list, self.cfg_mgr, self.engine)
            self.controller.start_monitor()
            return True
        except Exception:
            return False

if __name__ == "__main__":
    sm = AutoGameStateMachine()
    result = sm.execute_full_flow()
    if sm.qapp:
        sm.qapp.quit()
    sys.exit(0 if result else 1)
