# -*- coding: utf-8 -*-
"""
完整流程集成模块 (Updated)
整合 LauncherModule 启动器与 TaskController 调度中心，实现一键启动并挂机。
"""

import os
import sys
import time
import json
import traceback
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QCoreApplication

# 确保项目根目录 (auto_game) 在路径中，以便识别 app 包
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, "..", ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from app.core.config_manager import ConfigManager
from app.core.game_engine import GameEngine
from app.controllers.task_controller import TaskController
from app.modules.launcher_module import LauncherModule


class AutoGameFlow:
    """
    全自动运行流管理器
    负责：环境清理 -> 窗口启动 -> 调度中心接管
    """

    def __init__(self, config_manager=None):
        self.cfg_mgr = config_manager or ConfigManager()
        self.engine = GameEngine(self.cfg_mgr)
        self.launcher = None
        self.controller = None
        self.qapp = None
        self.launcher_finished = False
        self.launcher_success = False

    def execute_full_flow(self):
        """
        执行一键启动全流程
        """
        os.system('cls' if os.name == 'nt' else 'clear')
        print("自动游戏全集成启动流程")

        try:
            self._cleanup_environment()

            print(f"启动游戏窗口...")
            if not self._launch_windows():
                print("窗口启动失败，流程终止")
                if self.qapp:
                    self.qapp.quit()
                return False

            print(f"初始化调度中心...")
            if not self._start_controller():
                print("❌ 调度中心启动失败")
                if self.qapp:
                    self.qapp.quit()
                return False

            return True

        except Exception as e:
            print(f"流程异常中断: {e}")
            traceback.print_exc()
            if self.qapp:
                self.qapp.quit()
            return False

    def _cleanup_environment(self):
        """清理旧的 session 和结果文件"""
        p_session = self.cfg_mgr.get_path("room_session")
        p_results = self.cfg_mgr.get_path("window_results")
        
        for p in [p_session, p_results]:
            if p and os.path.exists(p):
                try:
                    os.remove(p)
                    print(f"清理旧文件: {os.path.basename(p)}")
                except:
                    pass

    def _launch_windows(self):
        """调用 Launcher 启动窗口"""
        # 加载账号
        account_path = self.cfg_mgr.get_path('accounts')
        accounts = []
        if os.path.exists(account_path):
            with open(account_path, 'r', encoding='utf-8') as f:
                for line in f:
                    if "," in line:
                        u, p = line.strip().split(",")
                        accounts.append({"username": u, "password": p})
        
        if not accounts:
            print("❌ 错误: accounts.txt 为空或不存在")
            return False

            print(f"待启动账号数: {len(accounts)}")

        # 初始化 Launcher
        box_path = self.cfg_mgr.get_user_config('paths.box_path', 'D:\\DataBase\\game\\auto_game\\app\\2Box.exe')
        game_path = self.cfg_mgr.get_user_config('paths.game_path', 'D:\\CrazyKart\\CrazyKart\\CrazyKart.exe')

        # 创建 QApplication 实例（如果尚未创建）
        if not QCoreApplication.instance():
            self.qapp = QApplication(sys.argv)
        else:
            self.qapp = QCoreApplication.instance()

        self.launcher = LauncherModule(
            box_path=box_path,
            game_path=game_path,
            accounts=accounts,
            config_manager=self.cfg_mgr,
            logger=None
        )

        # 连接信号
        self.launcher.all_ready.connect(self._on_launcher_ready)
        self.launcher.finished.connect(self._on_launcher_finished)

        # 执行启动逻辑
        try:
            self.launcher.start()
            
            # 等待启动完成（使用超时机制）
            timeout = 300  # 5分钟
            start_time = time.time()
            results_path = self.cfg_mgr.get_path("window_results")
            
            # 处理 Qt 事件循环，同时等待文件生成
            while time.time() - start_time < timeout and not self.launcher_finished:
                if self.qapp:
                    self.qapp.processEvents()
                
                if results_path and os.path.exists(results_path):
                    try:
                        with open(results_path, 'r') as f:
                            data = json.load(f)
                            if len(data) >= len(accounts):
                                print(f"所有窗口已就绪 ({len(data)}/{len(accounts)})")
                                self.launcher_finished = True
                                self.launcher_success = True
                    except:
                        pass
                time.sleep(0.5)
            
            if self.launcher_finished and self.launcher_success:
                return True
            elif not self.launcher_finished:
                print("⏳ 启动窗口超时")
                return False
            else:
                print("❌ Launcher 执行失败")
                return False
            
        except Exception as e:
            print(f"❌ Launcher 运行异常: {e}")
            traceback.print_exc()
            return False

    def _on_launcher_ready(self):
        """Launcher 完成准备时的回调"""
        self.launcher_finished = True
        self.launcher_success = True

    def _on_launcher_finished(self):
        """Launcher 线程完成时的回调"""
        if not self.launcher_finished:
            self.launcher_finished = True
            self.launcher_success = False

    def _start_controller(self):
        """初始化调度中心并接管"""
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
        except:
            return False


if __name__ == "__main__":
    flow = AutoGameFlow()
    result = flow.execute_full_flow()
    
    # 清理 QApplication
    if flow.qapp:
        flow.qapp.quit()
    
    sys.exit(0 if result else 1)
