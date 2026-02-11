# -*- coding: utf-8 -*-
"""
主窗口 - Auto Game 图形界面
整合所有功能模块的统一入口
"""

import sys
import os
import json
import time
import threading
from pathlib import Path

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QTabWidget,
    QPushButton, QLabel, QTextEdit, QPlainTextEdit, QLineEdit, QSpinBox,
    QGroupBox, QFormLayout, QMessageBox, QFileDialog,
    QTableWidget, QTableWidgetItem, QHeaderView, QSplitter,
    QProgressBar, QCheckBox, QComboBox, QStatusBar, QMenuBar, QMenu,
    QApplication, QScrollBar
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QAction, QIcon, QFont, QColor, QTextCharFormat, QCloseEvent

# 导入项目核心模块
project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from app.core.config_manager import ConfigManager
from app.core.game_engine import GameEngine
from app.modules.state_machine import AutoGameStateMachine


class LogRedirector:
    """重定向标准输出到UI日志框"""
    def __init__(self, signal):
        self.signal = signal
        self.original_stdout = sys.stdout
        
    def write(self, text):
        if text.strip():
            self.signal.emit(text)
        self.original_stdout.write(text)
        
    def flush(self):
        self.original_stdout.flush()


class FlowWorker(QThread):
    """后台运行游戏流程的工作线程（启动+运行）"""
    log_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(bool)
    progress_signal = pyqtSignal(int, str)

    def __init__(self, config_manager):
        super().__init__()
        self.cfg_mgr = config_manager
        self.flow = None
        self.running = False

    def run(self):
        self.running = True
        try:
            redirector = LogRedirector(self.log_signal)
            sys.stdout = redirector

            # 确保使用最新的分辨率配置
            from app.core.game_engine import GameEngine
            GameEngine._update_resolution()

            self.progress_signal.emit(10, "正在启动游戏...")
            self.flow = AutoGameStateMachine(self.cfg_mgr)

            self.progress_signal.emit(20, "游戏启动完成，开始运行...")
            result = self.flow.execute_full_flow()

            self.progress_signal.emit(100, "任务完成")
            self.finished_signal.emit(result)
        except Exception as e:
            self.log_signal.emit(f"[错误] 流程异常: {str(e)}")
            self.progress_signal.emit(0, f"运行错误: {str(e)}")
            self.finished_signal.emit(False)
        finally:
            sys.stdout = sys.__stdout__
            self.running = False

    def stop(self):
        self.running = False
        if self.flow and self.flow.controller:
            self.flow.controller.running = False


class LaunchOnlyWorker(QThread):
    """仅启动游戏窗口，不运行任务"""
    log_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(bool, int)  # success, window_count
    progress_signal = pyqtSignal(int, str)

    def __init__(self, config_manager):
        super().__init__()
        self.cfg_mgr = config_manager
        self.launcher = None
        self.running = False

    def run(self):
        self.running = True
        try:
            redirector = LogRedirector(self.log_signal)
            sys.stdout = redirector

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
                self.log_signal.emit("[错误] 没有配置账号，请先添加账号")
                self.finished_signal.emit(False, 0)
                return

            self.progress_signal.emit(10, "正在启动游戏...")

            # 获取路径配置
            box_path = self.cfg_mgr.get_user_config('paths.box_path',
                                                   r'D:\DataBase\game\auto_game\app\2Box.exe')
            game_path = self.cfg_mgr.get_user_config('paths.game_path',
                                                    r'D:\CrazyKart\CrazyKart\CrazyKart.exe')

            # 导入 LauncherModule
            from app.modules.launcher_module import LauncherModule

            self.launcher = LauncherModule(
                box_path=box_path,
                game_path=game_path,
                accounts=accounts,
                config_manager=self.cfg_mgr,
                logger=None,
            )

            self.launcher.log_signal.connect(
                lambda hwnd, level, msg: self.log_signal.emit(f"[{level}] {msg}")
            )

            # 启动 launcher
            from PyQt6.QtWidgets import QApplication
            if not QApplication.instance():
                self.qapp = QApplication(sys.argv)
            else:
                self.qapp = QApplication.instance()

            self.launcher.start()

            # 等待启动完成
            timeout = 300
            start_time = time.time()
            results_path = self.cfg_mgr.get_path("window_results")
            success = False
            window_count = 0

            while time.time() - start_time < timeout and self.running:
                if self.qapp:
                    self.qapp.processEvents()

                if results_path and os.path.exists(results_path):
                    try:
                        with open(results_path, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                        if len(data) >= len(accounts):
                            window_count = len(data)
                            self.progress_signal.emit(100, f"启动完成: {window_count} 个窗口")
                            success = True
                            break
                    except:
                        pass

                time.sleep(0.5)

            if not success and self.running:
                self.log_signal.emit("[警告] 启动超时或未完成")

            self.finished_signal.emit(success, window_count)

        except Exception as e:
            self.log_signal.emit(f"[错误] 启动异常: {str(e)}")
            import traceback
            self.log_signal.emit(traceback.format_exc())
            self.finished_signal.emit(False, 0)
        finally:
            sys.stdout = sys.__stdout__
            self.running = False

    def stop(self):
        self.running = False
        if self.launcher:
            self.launcher.running = False


class TaskOnlyWorker(QThread):
    """仅运行任务，使用已启动的窗口"""
    log_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(bool)
    progress_signal = pyqtSignal(int, str)

    def __init__(self, config_manager):
        super().__init__()
        self.cfg_mgr = config_manager
        self.controller = None
        self.running = False

    def rescan_windows(self, saved_accounts):
        """重新扫描当前运行的游戏窗口并匹配账号"""
        import win32gui
        
        target_title = self.cfg_mgr.get_config('target_window_title', '疯狂赛车怀旧版')
        found_windows = []
        
        def enum_callback(hwnd, _):
            if win32gui.IsWindowVisible(hwnd) and target_title in win32gui.GetWindowText(hwnd):
                found_windows.append(hwnd)
        
        win32gui.EnumWindows(enum_callback, None)
        
        if not found_windows:
            return []
        
        self.log_signal.emit(f"[信息] 扫描到 {len(found_windows)} 个游戏窗口")
        
        # 匹配账号（按顺序匹配）
        matched = []
        for i, hwnd in enumerate(found_windows):
            if i < len(saved_accounts):
                acc = saved_accounts[i]
                matched.append({
                    'index': i,
                    'hwnd': hwnd,
                    'username': acc.get('username', ''),
                    'password': acc.get('password', '')
                })
                self.log_signal.emit(f"[匹配] 窗口 {hwnd} -> 账号 {acc.get('username', 'unknown')}")
            else:
                matched.append({
                    'index': i,
                    'hwnd': hwnd,
                    'username': '',
                    'password': ''
                })
        
        return matched

    def run(self):
        self.running = True
        try:
            redirector = LogRedirector(self.log_signal)
            sys.stdout = redirector

            # 检查 window_results.json 是否存在
            results_path = self.cfg_mgr.get_path("window_results")
            if not results_path or not os.path.exists(results_path):
                self.log_signal.emit("[错误] 未找到已启动的窗口，请先启动游戏")
                self.finished_signal.emit(False)
                return

            # 读取窗口信息
            try:
                with open(results_path, 'r', encoding='utf-8') as f:
                    window_data = json.load(f)

                if not window_data:
                    self.log_signal.emit("[错误] 窗口数据为空，请重新启动游戏")
                    self.finished_signal.emit(False)
                    return

                self.log_signal.emit(f"[信息] 找到 {len(window_data)} 个已启动的窗口记录")

                # 检查窗口是否仍然有效
                import win32gui
                valid_windows = []
                for item in window_data:
                    hwnd = item.get('hwnd')
                    if hwnd and win32gui.IsWindow(hwnd):
                        valid_windows.append(item)
                    else:
                        self.log_signal.emit(f"[警告] 窗口 {item.get('username', 'unknown')} (句柄:{hwnd}) 已失效")

                # 如果所有窗口都失效，尝试重新扫描
                if not valid_windows:
                    self.log_signal.emit("[信息] 所有窗口已失效，尝试重新扫描当前游戏窗口...")
                    
                    # 提取保存的账号信息
                    saved_accounts = [
                        {'username': item.get('username', ''), 'password': item.get('password', '')}
                        for item in window_data
                    ]
                    
                    # 重新扫描
                    valid_windows = self.rescan_windows(saved_accounts)
                    
                    if not valid_windows:
                        self.log_signal.emit("[错误] 未能扫描到任何游戏窗口，请确保游戏已运行")
                        self.finished_signal.emit(False)
                        return
                    
                    # 保存新的窗口信息
                    with open(results_path, 'w', encoding='utf-8') as f:
                        json.dump(valid_windows, f, ensure_ascii=False, indent=4)
                    self.log_signal.emit("[信息] 窗口信息已更新")

                self.log_signal.emit(f"[信息] {len(valid_windows)} 个窗口有效，开始任务...")

            except Exception as e:
                self.log_signal.emit(f"[错误] 读取窗口数据失败: {e}")
                self.finished_signal.emit(False)
                return

            self.progress_signal.emit(10, "正在初始化任务控制器...")

            # 准备窗口列表
            window_results = []
            for item in valid_windows:
                hwnd = item.get('hwnd')
                username = item.get('username', '')
                password = item.get('password', '')
                index = item.get('index', 0)
                window_results.append((index, hwnd, {'user': username, 'pass': password}))

            # 启动 TaskController
            from app.controllers.task_controller import TaskController
            from app.core.game_engine import GameEngine
            from app.modules.module_switcher import ModeSwitcher

            # 确保使用最新的分辨率配置
            GameEngine._update_resolution()
            engine = GameEngine(self.cfg_mgr)
            self.controller = TaskController(window_results, self.cfg_mgr, engine)

            # 获取总目标局数用于计算进度
            mode_control = self.cfg_mgr.user_config_data.get('mode_control', {})
            tasks = mode_control.get('tasks', [])
            total_target = 0
            mode_targets = {}
            for task in tasks:
                target = task.get('target', 0)
                total_target += target
                mode_targets[task.get('id', '')] = target
            
            if total_target == 0:
                total_target = 20  # 默认值
                mode_targets = {'mode_item': 5, 'mode_speed': 15}

            self.progress_signal.emit(20, "任务控制器运行中...")
            
            # 在单独线程中运行控制器
            import threading
            controller_thread = threading.Thread(target=self.controller.start_monitor)
            controller_thread.daemon = True
            controller_thread.start()
            
            # 实时更新进度
            last_progress = 20
            while controller_thread.is_alive() and self.running:
                try:
                    # 读取当前进度
                    state_path = os.path.join(self.cfg_mgr.DATA_DIR, "switcher_state.json")
                    if os.path.exists(state_path):
                        with open(state_path, 'r', encoding='utf-8') as f:
                            state = json.load(f)
                        daily_progress = state.get('daily_progress', {})
                        
                        # 计算已完成局数
                        item_done = daily_progress.get('mode_item', 0)
                        speed_done = daily_progress.get('mode_speed', 0)
                        total_done = item_done + speed_done
                        
                        # 计算进度百分比 (20%起始, 到100%)
                        if total_target > 0:
                            game_progress = min(total_done / total_target, 1.0)
                            current_progress = int(20 + game_progress * 80)
                        else:
                            current_progress = 20
                        
                        # 只更新进度变化时
                        if current_progress != last_progress:
                            self.progress_signal.emit(current_progress, 
                                f"进行中 - 道具赛:{item_done}/{mode_targets.get('mode_item', 5)} 疾爽赛:{speed_done}/{mode_targets.get('mode_speed', 15)}")
                            last_progress = current_progress
                        
                        # 检查是否已完成所有任务
                        if total_done >= total_target:
                            self.progress_signal.emit(100, "所有任务已完成")
                            break
                except Exception as e:
                    pass
                
                time.sleep(2)  # 每2秒检查一次
            
            # 等待控制器结束
            controller_thread.join(timeout=5)
            result = True

            self.progress_signal.emit(100, "任务完成" if result else "任务失败")
            self.finished_signal.emit(result)

        except Exception as e:
            self.log_signal.emit(f"[错误] 任务异常: {str(e)}")
            import traceback
            self.log_signal.emit(traceback.format_exc())
            self.progress_signal.emit(0, f"运行错误: {str(e)}")
            self.finished_signal.emit(False)
        finally:
            sys.stdout = sys.__stdout__
            self.running = False

    def stop(self):
        self.running = False
        if self.controller:
            self.controller.running = False


class MainWindow(QMainWindow):
    """主窗口类"""
    
    def __init__(self):
        super().__init__()
        self.cfg_mgr = ConfigManager()
        self.flow_worker = None
        self.launch_worker = None
        self.task_worker = None
        self.stats_timer = None
        self.init_ui()
        self.load_data()
        self.init_stats_timer()
        # 加载全局主题样式
        theme_path = os.path.join(os.path.dirname(__file__), '..', 'resources', 'theme.qss')
        if os.path.exists(theme_path):
            try:
                with open(theme_path, 'r', encoding='utf-8') as f:
                    self.setStyleSheet(f.read())
            except Exception as e:
                print(f"[WARN] 加载主题失败: {e}")

        
    def init_ui(self):
        """初始化UI界面"""
        self.setWindowTitle("疯狂赛车自动游戏控制器")
        self.setGeometry(100, 100, 1200, 800)
        
        # 创建中央部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # 主布局
        main_layout = QVBoxLayout(central_widget)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(10, 10, 10, 10)
        
        # 创建菜单栏
        self.create_menu_bar()
        
        # 创建标签页
        self.tab_widget = QTabWidget()
        main_layout.addWidget(self.tab_widget)
        
        # 控制面板标签
        self.control_tab = self.create_control_tab()
        self.tab_widget.addTab(self.control_tab, "任务控制")
        
        # 账号管理标签
        self.account_tab = self.create_account_tab()
        self.tab_widget.addTab(self.account_tab, "账号管理")
        
        # 配置管理标签
        self.config_tab = self.create_config_tab()
        self.tab_widget.addTab(self.config_tab, "配置管理")
        
        # 日志显示区域
        self.log_group = self.create_log_group()
        main_layout.addWidget(self.log_group)
        
        # 状态栏
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("就绪")
        
    def create_menu_bar(self):
        """创建菜单栏"""
        menubar = QMenuBar(self)
        self.setMenuBar(menubar)
        
        # 文件菜单
        file_menu = menubar.addMenu("文件")  # type: ignore
        
        exit_action = QAction("退出", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)  # type: ignore
        
        # 工具菜单
        tools_menu = menubar.addMenu("工具")  # type: ignore
        
        clear_log_action = QAction("清空日志", self)
        clear_log_action.triggered.connect(self.clear_log)
        tools_menu.addAction(clear_log_action)  # type: ignore
        
        open_dir_action = QAction("打开数据目录", self)
        open_dir_action.triggered.connect(self.open_data_directory)
        tools_menu.addAction(open_dir_action)  # type: ignore
        
    def create_control_tab(self):
        """创建控制面板标签页"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(15)
        
        # 状态信息组
        status_group = QGroupBox("运行状态")
        status_layout = QHBoxLayout(status_group)
        
        self.status_label = QLabel("状态: 待机")
        self.status_label.setStyleSheet("font-size: 14px; font-weight: bold;")
        status_layout.addWidget(self.status_label)
        
        status_layout.addStretch()
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        status_layout.addWidget(QLabel("进度:"))
        status_layout.addWidget(self.progress_bar)
        status_layout.setStretchFactor(self.progress_bar, 1)
        
        layout.addWidget(status_group)
        
        # 操作按钮区域 - 使用两个独立的组
        operation_layout = QHBoxLayout()
        operation_layout.setSpacing(15)

        # 游戏启动组（左）
        launch_group = QGroupBox("游戏启动")
        launch_layout = QHBoxLayout(launch_group)
        launch_layout.setSpacing(10)

        self.launch_btn = QPushButton("🚀 启动游戏")
        self.launch_btn.setObjectName("launch_btn")
        self.launch_btn.setToolTip("仅启动游戏窗口，不开始任务\n用于先启动游戏，稍后手动开始任务")
        self.launch_btn.setMinimumWidth(120)
        self.launch_btn.clicked.connect(self.launch_game_only)
        launch_layout.addWidget(self.launch_btn)

        self.launch_run_btn = QPushButton("🚀▶ 启动并运行")
        self.launch_run_btn.setObjectName("launch_run_btn")
        self.launch_run_btn.setToolTip("启动游戏并开始任务\n全新开始，会重置任务进度")
        self.launch_run_btn.setMinimumWidth(140)
        self.launch_run_btn.clicked.connect(self.launch_and_run)
        launch_layout.addWidget(self.launch_run_btn)

        launch_layout.addStretch()
        operation_layout.addWidget(launch_group, 1)

        # 任务控制组（右）
        task_group = QGroupBox("任务控制")
        task_layout = QHBoxLayout(task_group)
        task_layout.setSpacing(10)

        self.start_btn = QPushButton("▶ 开始任务")
        self.start_btn.setObjectName("start_btn")
        self.start_btn.setToolTip("使用已启动的游戏窗口开始任务\n继续之前的进度")
        self.start_btn.setMinimumWidth(120)
        self.start_btn.clicked.connect(self.start_task)
        task_layout.addWidget(self.start_btn)

        self.stop_btn = QPushButton("⏹ 停止")
        self.stop_btn.setObjectName("stop_btn")
        self.stop_btn.setToolTip("停止当前任务")
        self.stop_btn.setEnabled(False)
        self.stop_btn.setMinimumWidth(80)
        self.stop_btn.clicked.connect(self.stop_task)
        task_layout.addWidget(self.stop_btn)

        self.reset_btn = QPushButton("🔄 重置")
        self.reset_btn.setObjectName("reset_btn")
        self.reset_btn.setToolTip("重置任务进度为0\n用于重新开始计数")
        self.reset_btn.setMinimumWidth(80)
        self.reset_btn.clicked.connect(self.reset_progress)
        task_layout.addWidget(self.reset_btn)

        task_layout.addStretch()
        operation_layout.addWidget(task_group, 1)

        layout.addLayout(operation_layout)
        
        # 手动功能组（新添加）
        manual_group = QGroupBox("手动功能")
        manual_layout = QHBoxLayout(manual_group)
        manual_layout.setSpacing(10)

        self.claim_reward_btn = QPushButton("🎁 领取任务奖励")
        self.claim_reward_btn.setObjectName("claim_reward_btn")
        self.claim_reward_btn.setToolTip("手动触发领取任务奖励\n需要确保游戏窗口已在大厅")
        self.claim_reward_btn.setMinimumWidth(140)
        self.claim_reward_btn.clicked.connect(self.manual_claim_reward)
        manual_layout.addWidget(self.claim_reward_btn)

        self.check_in_btn = QPushButton("📅 签到")
        self.check_in_btn.setObjectName("check_in_btn")
        self.check_in_btn.setToolTip("执行每日签到\n需要确保游戏窗口已在大厅")
        self.check_in_btn.setMinimumWidth(100)
        self.check_in_btn.clicked.connect(self.manual_check_in)
        # 签到功能预留，暂时禁用（等待模块实现）
        # self.check_in_btn.setEnabled(False)
        manual_layout.addWidget(self.check_in_btn)

        manual_layout.addStretch()
        layout.addWidget(manual_group)
        
        # 统计信息组
        stats_group = QGroupBox("任务统计")
        stats_layout = QFormLayout(stats_group)
        
        self.mode_item_count = QLabel("0 / 5")
        self.mode_speed_count = QLabel("0 / 15")
        
        stats_layout.addRow("道具赛进度:", self.mode_item_count)
        stats_layout.addRow("疾爽赛进度:", self.mode_speed_count)
        
        layout.addWidget(stats_group)
        layout.addStretch()
        
        return tab
        
    def create_account_tab(self):
        """创建账号管理标签页"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(10)
        
        # 说明标签
        info_label = QLabel("账号格式: 用户名,密码 (每行一个)")
        info_label.setStyleSheet("color: gray;")
        layout.addWidget(info_label)
        
        # 账号编辑区
        self.account_edit = QTextEdit()
        self.account_edit.setPlaceholderText("例如:\nuser1,password1\nuser2,password2")
        layout.addWidget(self.account_edit)
        
        # 按钮区域
        btn_layout = QHBoxLayout()
        
        save_account_btn = QPushButton("💾 保存账号")
        save_account_btn.clicked.connect(self.save_accounts)
        btn_layout.addWidget(save_account_btn)
        
        load_account_btn = QPushButton("📂 加载账号")
        load_account_btn.clicked.connect(self.load_accounts)
        btn_layout.addWidget(load_account_btn)
        
        clear_account_btn = QPushButton("🗑️ 清空")
        clear_account_btn.clicked.connect(self.account_edit.clear)
        btn_layout.addWidget(clear_account_btn)
        
        btn_layout.addStretch()
        
        layout.addLayout(btn_layout)
        
        return tab
        
    def create_config_tab(self):
        """创建配置管理标签页"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(15)
        
        # 基本配置组
        basic_group = QGroupBox("基本配置")
        basic_layout = QFormLayout(basic_group)
        
        # 游戏路径
        path_layout = QHBoxLayout()
        self.game_path_edit = QLineEdit()
        path_layout.addWidget(self.game_path_edit)
        browse_game_btn = QPushButton("浏览...")
        browse_game_btn.clicked.connect(lambda: self.browse_file(self.game_path_edit, "选择游戏程序"))
        path_layout.addWidget(browse_game_btn)
        basic_layout.addRow("游戏路径:", path_layout)
        
        # 沙盒路径
        box_layout = QHBoxLayout()
        self.box_path_edit = QLineEdit()
        box_layout.addWidget(self.box_path_edit)
        browse_box_btn = QPushButton("浏览...")
        browse_box_btn.clicked.connect(lambda: self.browse_file(self.box_path_edit, "选择沙盒程序"))
        box_layout.addWidget(browse_box_btn)
        basic_layout.addRow("沙盒路径:", box_layout)
        
        # 房间密码
        self.room_pwd_edit = QLineEdit()
        self.room_pwd_edit.setEchoMode(QLineEdit.EchoMode.Password)
        basic_layout.addRow("房间密码:", self.room_pwd_edit)
        
        # 目标局数
        self.item_target_spin = QSpinBox()
        self.item_target_spin.setRange(1, 100)
        self.item_target_spin.setValue(5)
        basic_layout.addRow("道具赛目标:", self.item_target_spin)
        
        self.speed_target_spin = QSpinBox()
        self.speed_target_spin.setRange(1, 100)
        self.speed_target_spin.setValue(15)
        basic_layout.addRow("疾爽赛目标:", self.speed_target_spin)

        # 分辨率选择
        self.resolution_combo = QComboBox()
        self.resolution_combo.setToolTip("选择游戏运行分辨率\n根据您的显示器选择合适的分辨率")
        # 预设分辨率选项
        resolutions = [
            (1920, 1080, "1920x1080 (推荐)"),
            (1600, 900, "1600x900"),
            (1366, 768, "1366x768"),
            (1280, 720, "1280x720"),
            (1024, 576, "1024x576 (小屏幕)"),
        ]
        for w, h, name in resolutions:
            self.resolution_combo.addItem(name, {"width": w, "height": h})
        basic_layout.addRow("游戏分辨率:", self.resolution_combo)

        layout.addWidget(basic_group)
        
        # 快捷键配置组
        hotkey_group = QGroupBox("快捷键配置")
        hotkey_layout = QFormLayout(hotkey_group)
        
        self.pause_key_edit = QLineEdit("f9")
        hotkey_layout.addRow("暂停/恢复:", self.pause_key_edit)
        
        self.stop_key_edit = QLineEdit("f10")
        hotkey_layout.addRow("停止:", self.stop_key_edit)
        
        self.reset_key_edit = QLineEdit("f8")
        hotkey_layout.addRow("重置:", self.reset_key_edit)
        
        layout.addWidget(hotkey_group)
        
        # 保存按钮
        save_config_btn = QPushButton("💾 保存配置")
        save_config_btn.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                padding: 10px;
                font-weight: bold;
            }
        """)
        save_config_btn.clicked.connect(self.save_config)
        layout.addWidget(save_config_btn)
        
        layout.addStretch()
        
        return tab
        
    def create_log_group(self):
        """创建日志显示组"""
        group = QGroupBox("运行日志")
        layout = QVBoxLayout(group)
        
        self.log_text: QPlainTextEdit = QPlainTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumBlockCount(1000)  # 限制最大行数
        self.log_text.setStyleSheet("""
            QPlainTextEdit {
                background-color: #1e1e1e;
                color: #d4d4d4;
                font-family: Consolas, Monaco, monospace;
                font-size: 12px;
                border: 1px solid #3e3e3e;
            }
        """)
        layout.addWidget(self.log_text)
        
        # 日志操作按钮
        log_btn_layout = QHBoxLayout()
        
        clear_btn = QPushButton("清空日志")
        clear_btn.clicked.connect(self.clear_log)
        log_btn_layout.addWidget(clear_btn)
        
        save_log_btn = QPushButton("保存日志")
        save_log_btn.clicked.connect(self.save_log)
        log_btn_layout.addWidget(save_log_btn)
        
        log_btn_layout.addStretch()
        
        auto_scroll_check = QCheckBox("自动滚动")
        auto_scroll_check.setChecked(True)
        self.auto_scroll = True
        auto_scroll_check.stateChanged.connect(lambda state: setattr(self, 'auto_scroll', bool(state)))
        log_btn_layout.addWidget(auto_scroll_check)
        
        layout.addLayout(log_btn_layout)
        
        return group
        
    def load_data(self):
        """加载现有数据"""
        # 加载账号
        account_path = self.cfg_mgr.get_path("accounts")
        if account_path and os.path.exists(account_path):
            try:
                with open(account_path, 'r', encoding='utf-8') as f:
                    self.account_edit.setPlainText(f.read())
            except Exception as e:
                self.append_log(f"[警告] 加载账号失败: {e}")
        
        # 加载配置
        user_config = self.cfg_mgr.user_config_data
        
        paths = user_config.get("paths", {})
        self.game_path_edit.setText(paths.get("game_path", ""))
        self.box_path_edit.setText(paths.get("box_path", ""))
        
        self.room_pwd_edit.setText(user_config.get("room_password", ""))
        
        mode_control = user_config.get("mode_control", {})
        tasks = mode_control.get("tasks", [])
        for task in tasks:
            if task.get("id") == "mode_item":
                self.item_target_spin.setValue(task.get("target", 5))
            elif task.get("id") == "mode_speed":
                self.speed_target_spin.setValue(task.get("target", 15))

        # 加载分辨率配置
        resolution = user_config.get("resolution", {})
        saved_width = resolution.get("width", 1920)
        saved_height = resolution.get("height", 1080)
        # 查找匹配的分辨率选项
        for i in range(self.resolution_combo.count()):
            data = self.resolution_combo.itemData(i)
            if data and data.get("width") == saved_width and data.get("height") == saved_height:
                self.resolution_combo.setCurrentIndex(i)
                break

        # 快捷键
        config = self.cfg_mgr.config_data
        self.pause_key_edit.setText(config.get("pause_hotkey", "f9"))
        self.stop_key_edit.setText(config.get("stop_hotkey", "f10"))
        self.reset_key_edit.setText(config.get("reset_hotkey", "f8"))
        
        # 加载统计
        self.load_stats()
        
    def load_stats(self):
        """加载任务统计"""
        try:
            state_path = os.path.join(self.cfg_mgr.DATA_DIR, "switcher_state.json")
            if os.path.exists(state_path):
                with open(state_path, 'r', encoding='utf-8') as f:
                    state = json.load(f)
                    # 使用 daily_progress 字段（与 module_switcher.py 保持一致）
                    progress = state.get("daily_progress", {})
                    item_done = progress.get('mode_item', 0)
                    speed_done = progress.get('mode_speed', 0)
                    
                    # 从配置管理标签页获取当前目标值
                    item_target = self.item_target_spin.value()
                    speed_target = self.speed_target_spin.value()
                    
                    # 更新UI
                    self.mode_item_count.setText(f"{item_done} / {item_target}")
                    self.mode_speed_count.setText(f"{speed_done} / {speed_target}")
                    
                    # 调试日志（每10次刷新输出一次，避免日志过多）
                    if not hasattr(self, '_stats_refresh_count'):
                        self._stats_refresh_count = 0
                    self._stats_refresh_count += 1
                    if self._stats_refresh_count % 10 == 0:
                        self.append_log(f"[调试] 统计刷新 - 道具赛: {item_done}/{item_target}, 疾爽赛: {speed_done}/{speed_target}")
            else:
                # 如果没有状态文件，显示 0 / 目标值
                self.mode_item_count.setText(f"0 / {self.item_target_spin.value()}")
                self.mode_speed_count.setText(f"0 / {self.speed_target_spin.value()}")
        except Exception as e:
            self.append_log(f"[警告] 加载统计失败: {e}")

    def init_stats_timer(self):
        """初始化统计刷新定时器"""
        self.stats_timer = QTimer(self)
        self.stats_timer.timeout.connect(self.load_stats)
        self.stats_timer.start(2000)  # 每2秒刷新一次统计
        self.append_log("[系统] 统计定时器已启动 (每2秒刷新)")

    def launch_game_only(self):
        """仅启动游戏窗口"""
        # 检查账号
        account_text = self.account_edit.toPlainText().strip()
        if not account_text:
            QMessageBox.warning(self, "警告", "请先配置账号信息！")
            self.tab_widget.setCurrentIndex(1)
            return

        self.status_label.setText("状态: 启动中")
        self.status_label.setStyleSheet("font-size: 14px; font-weight: bold; color: orange;")
        self.launch_btn.setEnabled(False)
        self.launch_run_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.progress_bar.setValue(5)

        # 创建启动线程（不清理旧文件，保留已有进度）
        self.launch_worker = LaunchOnlyWorker(self.cfg_mgr)
        self.launch_worker.log_signal.connect(self.append_log)
        self.launch_worker.finished_signal.connect(self.on_launch_finished)
        self.launch_worker.progress_signal.connect(self.update_progress)
        self.launch_worker.start()

        self.append_log("="*50)
        self.append_log("正在启动游戏窗口...")
        self.status_bar.showMessage("启动游戏中")

    def on_launch_finished(self, success, window_count):
        """游戏启动完成回调"""
        if success:
            self.status_label.setText(f"状态: 已启动 ({window_count}窗口)")
            self.status_label.setStyleSheet("font-size: 14px; font-weight: bold; color: green;")
            self.append_log(f"[成功] 游戏启动完成，共 {window_count} 个窗口")
            QMessageBox.information(self, "成功", f"游戏已启动！\n共 {window_count} 个窗口\n\n现在可以点击「开始任务」按钮运行任务。")
        else:
            self.status_label.setText("状态: 启动失败")
            self.status_label.setStyleSheet("font-size: 14px; font-weight: bold; color: red;")
            self.append_log("[错误] 游戏启动失败")
            QMessageBox.warning(self, "失败", "游戏启动失败，请检查配置和日志。")

        self.launch_btn.setEnabled(True)
        self.launch_run_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)

    def launch_and_run(self):
        """启动游戏并开始任务（完整流程）"""
        # 检查账号
        account_text = self.account_edit.toPlainText().strip()
        if not account_text:
            QMessageBox.warning(self, "警告", "请先配置账号信息！")
            self.tab_widget.setCurrentIndex(1)
            return

        # 询问是否清理旧进度
        reply = QMessageBox.question(
            self, "确认",
            "启动并开始任务会重置任务进度，是否继续？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply != QMessageBox.StandardButton.Yes:
            return

        self.status_label.setText("状态: 运行中")
        self.status_label.setStyleSheet("font-size: 14px; font-weight: bold; color: green;")
        self.launch_btn.setEnabled(False)
        self.launch_run_btn.setEnabled(False)
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.progress_bar.setValue(5)

        # 创建工作线程（完整流程）
        self.flow_worker = FlowWorker(self.cfg_mgr)
        self.flow_worker.log_signal.connect(self.append_log)
        self.flow_worker.finished_signal.connect(self.on_full_flow_finished)
        self.flow_worker.progress_signal.connect(self.update_progress)
        self.flow_worker.start()

        self.append_log("="*50)
        self.append_log("启动游戏并开始任务...")
        self.status_bar.showMessage("启动并运行中")

    def on_full_flow_finished(self, success):
        """完整流程完成回调"""
        self.status_label.setText("状态: 已完成" if success else "状态: 失败")
        self.status_label.setStyleSheet("font-size: 14px; font-weight: bold; color: " + ("green" if success else "red"))
        self.launch_btn.setEnabled(True)
        self.launch_run_btn.setEnabled(True)
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.progress_bar.setValue(100 if success else 0)
        self.load_stats()

    def start_task(self):
        """开始任务（使用已启动的窗口）"""
        # 检查 window_results.json 是否存在
        results_path = self.cfg_mgr.get_path("window_results")
        if not results_path or not os.path.exists(results_path):
            QMessageBox.warning(self, "警告", "未找到已启动的游戏窗口！\n\n请先点击「启动游戏」按钮启动游戏窗口。")
            return

        self.status_label.setText("状态: 运行中")
        self.status_label.setStyleSheet("font-size: 14px; font-weight: bold; color: green;")
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.progress_bar.setValue(10)

        # 创建任务线程（使用已有窗口）
        self.task_worker = TaskOnlyWorker(self.cfg_mgr)
        self.task_worker.log_signal.connect(self.append_log)
        self.task_worker.finished_signal.connect(self.on_task_finished)
        self.task_worker.progress_signal.connect(self.update_progress)
        self.task_worker.start()

        self.append_log("="*50)
        self.append_log("开始任务（使用已启动窗口）...")
        self.status_bar.showMessage("任务运行中")
        
    def stop_task(self):
        """停止任务"""
        stopped = False

        if hasattr(self, 'flow_worker') and self.flow_worker and self.flow_worker.running:
            self.flow_worker.stop()
            stopped = True

        if hasattr(self, 'task_worker') and self.task_worker and self.task_worker.running:
            self.task_worker.stop()
            stopped = True

        if hasattr(self, 'launch_worker') and self.launch_worker and self.launch_worker.running:
            self.launch_worker.stop()
            stopped = True

        if stopped:
            self.append_log("正在停止...")

        self.status_label.setText("状态: 已停止")
        self.status_label.setStyleSheet("font-size: 14px; font-weight: bold; color: red;")
        self.launch_btn.setEnabled(True)
        self.launch_run_btn.setEnabled(True)
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.status_bar.showMessage("已停止")
        
    def on_task_finished(self, success):
        """任务完成回调"""
        self.status_label.setText("状态: 已完成" if success else "状态: 失败")
        self.status_label.setStyleSheet("font-size: 14px; font-weight: bold; color: " + ("green" if success else "red"))
        self.launch_btn.setEnabled(True)
        self.launch_run_btn.setEnabled(True)
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.progress_bar.setValue(100 if success else 0)
        self.load_stats()
        
    def update_progress(self, progress, message):
        """更新进度条"""
        self.progress_bar.setValue(progress)
        if message:
            self.status_bar.showMessage(message)
        # 同时刷新统计
        self.load_stats()
        
    def reset_progress(self):
        """重置进度"""
        reply = QMessageBox.question(
            self, "确认", 
            "确定要重置所有任务进度吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            try:
                state_path = os.path.join(self.cfg_mgr.DATA_DIR, "switcher_state.json")
                if os.path.exists(state_path):
                    os.remove(state_path)
                
                session_path = self.cfg_mgr.get_path("room_session")
                if session_path and os.path.exists(session_path):
                    os.remove(session_path)
                    
                self.mode_item_count.setText(f"0 / {self.item_target_spin.value()}")
                self.mode_speed_count.setText(f"0 / {self.speed_target_spin.value()}")
                
                self.append_log("[系统] 任务进度已重置")
                QMessageBox.information(self, "成功", "进度已重置！")
            except Exception as e:
                QMessageBox.critical(self, "错误", f"重置失败: {e}")
                
    def manual_claim_reward(self):
        """手动领取任务奖励"""
        # 检查是否有已启动的窗口
        results_path = self.cfg_mgr.get_path("window_results")
        if not results_path or not os.path.exists(results_path):
            QMessageBox.warning(self, "警告", "未找到已启动的游戏窗口！\n\n请先启动游戏窗口。")
            return
        
        try:
            with open(results_path, 'r', encoding='utf-8') as f:
                window_data = json.load(f)
            
            if not window_data:
                QMessageBox.warning(self, "警告", "窗口数据为空！")
                return
            
            # 检查窗口有效性
            import win32gui
            valid_windows = []
            for item in window_data:
                hwnd = item.get('hwnd')
                if hwnd and win32gui.IsWindow(hwnd):
                    valid_windows.append((hwnd, item.get('username', 'unknown')))
            
            if not valid_windows:
                QMessageBox.warning(self, "警告", "没有有效的游戏窗口！")
                return
            
            reply = QMessageBox.question(
                self, "确认", 
                f"确定要为 {len(valid_windows)} 个窗口领取任务奖励吗？\n\n请确保游戏已在大厅界面！",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            
            if reply != QMessageBox.StandardButton.Yes:
                return
            
            self.append_log("[系统] 开始手动领取任务奖励...")
            self.status_label.setText("状态: 领取奖励中")
            self.status_label.setStyleSheet("font-size: 14px; font-weight: bold; color: orange;")
            self.claim_reward_btn.setEnabled(False)
            
            # 导入TaskModule
            from app.modules.task_module import TaskModule
            from app.core.game_engine import GameEngine
            
            engine = GameEngine(self.cfg_mgr)
            task_mod = TaskModule(self.cfg_mgr, engine)
            
            success_count = 0
            for hwnd, username in valid_windows:
                try:
                    self.append_log(f"[领取] 正在为账号 {username} 领取奖励...")
                    task_mod.run(hwnd)
                    success_count += 1
                    self.append_log(f"[领取] 账号 {username} 领取成功")
                    time.sleep(1)  # 间隔1秒，避免操作过快
                except Exception as e:
                    self.append_log(f"[领取] 账号 {username} 领取失败: {e}")
            
            self.append_log(f"[系统] 奖励领取完成: {success_count}/{len(valid_windows)} 成功")
            QMessageBox.information(self, "完成", f"奖励领取完成！\n成功: {success_count}/{len(valid_windows)}")
            
        except Exception as e:
            self.append_log(f"[错误] 领取奖励失败: {e}")
            QMessageBox.critical(self, "错误", f"领取奖励失败: {e}")
        finally:
            self.status_label.setText("状态: 待机")
            self.status_label.setStyleSheet("font-size: 14px; font-weight: bold;")
            self.claim_reward_btn.setEnabled(True)
                
    def manual_check_in(self):
        """手动签到功能"""
        # 检查是否有已启动的窗口
        results_path = self.cfg_mgr.get_path("window_results")
        if not results_path or not os.path.exists(results_path):
            QMessageBox.warning(self, "警告", "未找到已启动的游戏窗口！\n\n请先启动游戏窗口。")
            return
        
        try:
            with open(results_path, 'r', encoding='utf-8') as f:
                window_data = json.load(f)
            
            if not window_data:
                QMessageBox.warning(self, "警告", "窗口数据为空！")
                return
            
            # 检查窗口有效性
            import win32gui
            valid_windows = []
            for item in window_data:
                hwnd = item.get('hwnd')
                if hwnd and win32gui.IsWindow(hwnd):
                    valid_windows.append((hwnd, item.get('username', 'unknown')))
            
            if not valid_windows:
                QMessageBox.warning(self, "警告", "没有有效的游戏窗口！")
                return
            
            reply = QMessageBox.question(
                self, "确认", 
                f"确定为 {len(valid_windows)} 个窗口执行签到吗？\n\n请确保游戏已在大厅界面！",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            
            if reply != QMessageBox.StandardButton.Yes:
                return
            
            self.append_log("[系统] 开始执行签到...")
            self.status_label.setText("状态: 签到中")
            self.status_label.setStyleSheet("font-size: 14px; font-weight: bold; color: orange;")
            self.check_in_btn.setEnabled(False)
            
            # 导入签到模块
            from app.modules.check_in_module import CheckInModule
            from app.core.game_engine import GameEngine
            
            engine = GameEngine(self.cfg_mgr)
            check_in_mod = CheckInModule(self.cfg_mgr, engine)
            
            success_count = 0
            for hwnd, username in valid_windows:
                try:
                    self.append_log(f"[签到] 正在为账号 {username} 执行签到...")
                    result = check_in_mod.run(hwnd)
                    if result:
                        success_count += 1
                        self.append_log(f"[签到] 账号 {username} 签到成功")
                    else:
                        self.append_log(f"[签到] 账号 {username} 签到失败或已签到")
                    time.sleep(1)  # 间隔1秒，避免操作过快
                except Exception as e:
                    self.append_log(f"[签到] 账号 {username} 签到异常: {e}")
            
            self.append_log(f"[系统] 签到完成: {success_count}/{len(valid_windows)} 成功")
            QMessageBox.information(self, "完成", f"签到完成！\n成功: {success_count}/{len(valid_windows)}")
            
        except Exception as e:
            self.append_log(f"[错误] 签到失败: {e}")
            QMessageBox.critical(self, "错误", f"签到失败: {e}")
        finally:
            self.status_label.setText("状态: 待机")
            self.status_label.setStyleSheet("font-size: 14px; font-weight: bold;")
            self.check_in_btn.setEnabled(True)
                
    def save_accounts(self):
        """保存账号"""
        try:
            account_path = self.cfg_mgr.get_path("accounts")
            if not account_path:
                QMessageBox.critical(self, "错误", "账号路径未配置")
                return
            with open(account_path, 'w', encoding='utf-8') as f:
                f.write(self.account_edit.toPlainText())
            QMessageBox.information(self, "成功", "账号已保存！")
            self.append_log("[系统] 账号配置已保存")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"保存失败: {e}")
            
    def load_accounts(self):
        """从文件加载账号"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择账号文件", "", "文本文件 (*.txt);;所有文件 (*.*)"
        )
        if file_path:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    self.account_edit.setPlainText(f.read())
                self.append_log(f"[系统] 已从文件加载账号: {file_path}")
            except Exception as e:
                QMessageBox.critical(self, "错误", f"加载失败: {e}")
                
    def save_config(self):
        """保存配置"""
        try:
            # 更新用户配置
            user_config = self.cfg_mgr.user_config_data
            
            user_config["paths"] = {
                "game_path": self.game_path_edit.text(),
                "box_path": self.box_path_edit.text()
            }
            
            user_config["room_password"] = self.room_pwd_edit.text()
            
            user_config["mode_control"] = {
                "tasks": [
                    {"id": "mode_item", "target": self.item_target_spin.value()},
                    {"id": "mode_speed", "target": self.speed_target_spin.value()}
                ]
            }

            # 保存分辨率配置
            res_data = self.resolution_combo.currentData()
            if res_data:
                user_config["resolution"] = {
                    "width": res_data["width"],
                    "height": res_data["height"]
                }

            self.cfg_mgr.save_user_config()
            
            # 更新快捷键配置
            config = self.cfg_mgr.config_data
            config["pause_hotkey"] = self.pause_key_edit.text()
            config["stop_hotkey"] = self.stop_key_edit.text()
            config["reset_hotkey"] = self.reset_key_edit.text()
            
            config_path = self.cfg_mgr.get_path("config")
            if not config_path:
                self.append_log("[错误] 配置路径未找到，无法保存")
                return
            # 确保路径非空后打开
            assert config_path is not None
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=4, ensure_ascii=False)
            
            QMessageBox.information(self, "成功", "配置已保存！")
            self.append_log("[系统] 配置已保存")
            self.load_stats()
            
        except Exception as e:
            QMessageBox.critical(self, "错误", f"保存失败: {e}")
            
    def browse_file(self, line_edit, title):
        """浏览文件"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, title, "", "可执行文件 (*.exe);;所有文件 (*.*)"
        )
        if file_path:
            line_edit.setText(file_path)
            
    def append_log(self, text):
        """添加日志"""
        self.log_text.appendPlainText(text.strip())
        if self.auto_scroll:
            scrollbar = self.log_text.verticalScrollBar()
            if scrollbar:
                scrollbar.setValue(scrollbar.maximum())
            
    def clear_log(self):
        """清空日志"""
        self.log_text.clear()
        
    def save_log(self):
        """保存日志"""
        file_path, _ = QFileDialog.getSaveFileName(
            self, "保存日志", f"log_{time.strftime('%Y%m%d_%H%M%S')}.txt",
            "文本文件 (*.txt)"
        )
        if file_path:
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(self.log_text.toPlainText())
                QMessageBox.information(self, "成功", "日志已保存！")
            except Exception as e:
                QMessageBox.critical(self, "错误", f"保存失败: {e}")
                
    def open_data_directory(self):
        """打开数据目录"""
        import subprocess
        data_dir = self.cfg_mgr.DATA_DIR
        if os.path.exists(data_dir):
            subprocess.Popen(f'explorer "{data_dir}"')
        else:
            QMessageBox.warning(self, "警告", "数据目录不存在！")
            
    def closeEvent(self, a0):
        """关闭事件"""
        if not a0:
            return

        # 检查是否有任何任务在运行
        has_running = (
            (self.flow_worker and self.flow_worker.running) or
            (self.launch_worker and self.launch_worker.running) or
            (self.task_worker and self.task_worker.running)
        )

        if has_running:
            reply = QMessageBox.question(
                self, "确认",
                "任务正在运行中，确定要退出吗？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )

            if reply == QMessageBox.StandardButton.Yes:
                self.stop_task()
                a0.accept()
            else:
                a0.ignore()
        else:
            a0.accept()


def main():
    """主入口"""
    app = QApplication(sys.argv)
    
    # 设置应用程序样式
    app.setStyle('Fusion')
    
    # 创建并显示主窗口
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
