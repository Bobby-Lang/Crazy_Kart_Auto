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
    """后台运行游戏流程的工作线程"""
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
            # 重定向输出
            redirector = LogRedirector(self.log_signal)
            sys.stdout = redirector
            
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


class MainWindow(QMainWindow):
    """主窗口类"""
    
    def __init__(self):
        super().__init__()
        self.cfg_mgr = ConfigManager()
        self.flow_worker = None
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
        
        # 快捷操作组
        action_group = QGroupBox("快捷操作")
        action_layout = QHBoxLayout(action_group)
        
        self.start_btn = QPushButton("▶ 开始任务")
        self.start_btn.setObjectName("start_btn")
        self.start_btn.setStyleSheet("")  # 使用全局样式
        self.start_btn.clicked.connect(self.start_task)
        action_layout.addWidget(self.start_btn)
        
        self.stop_btn = QPushButton("⏹ 停止任务")
        self.stop_btn.setObjectName("stop_btn")
        self.stop_btn.setStyleSheet("")
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self.stop_task)
        action_layout.addWidget(self.stop_btn)
        
        self.reset_btn = QPushButton("🔄 重置进度")
        self.reset_btn.setObjectName("reset_btn")
        self.reset_btn.setStyleSheet("")
        self.reset_btn.clicked.connect(self.reset_progress)
        action_layout.addWidget(self.reset_btn)
        
        layout.addWidget(action_group)
        
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

    def start_task(self):
        """开始任务"""
        # 检查账号
        account_text = self.account_edit.toPlainText().strip()
        if not account_text:
            QMessageBox.warning(self, "警告", "请先配置账号信息！")
            self.tab_widget.setCurrentIndex(1)
            return
        
        self.status_label.setText("状态: 运行中")
        self.status_label.setStyleSheet("font-size: 14px; font-weight: bold; color: green;")
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.progress_bar.setValue(10)
        
        # 创建工作线程
        self.flow_worker = FlowWorker(self.cfg_mgr)
        self.flow_worker.log_signal.connect(self.append_log)
        self.flow_worker.finished_signal.connect(self.on_task_finished)
        self.flow_worker.progress_signal.connect(self.update_progress)
        self.flow_worker.start()
        
        self.append_log("="*50)
        self.append_log("任务启动...")
        self.status_bar.showMessage("任务运行中")
        
    def stop_task(self):
        """停止任务"""
        if self.flow_worker and self.flow_worker.running:
            self.flow_worker.stop()
            self.append_log("正在停止任务...")
            
        self.status_label.setText("状态: 已停止")
        self.status_label.setStyleSheet("font-size: 14px; font-weight: bold; color: red;")
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.status_bar.showMessage("任务已停止")
        
    def on_task_finished(self, success):
        """任务完成回调"""
        self.status_label.setText("状态: 已完成" if success else "状态: 失败")
        self.status_label.setStyleSheet("font-size: 14px; font-weight: bold; color: " + ("green" if success else "red"))
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
        if self.flow_worker and self.flow_worker.running:
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
