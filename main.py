import sys
import os
import win32gui
import json
import traceback
# 导入你之前写的核心组件
from app.core.game_engine import GameEngine
from app.core.config_manager import ConfigManager  # 使用你写的管理类
from app.controllers.task_controller import TaskController
from app.modules.room_in_module import RoomModule
from app.modules.module_switcher import ModeSwitcher
from app.modules.emergency_module import EmergencyModule

# 1. 设置路径
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)


def get_accurate_window_list(cfg_manager):
    """
    优先从 window_results.json 获取带账号信息的窗口列表
    """
    results_path = cfg_manager.get_path("window_results")

    if os.path.exists(results_path):
        print(f"发现窗口记录文件: {results_path}")
        with open(results_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            # 这里的 i 包含: index, hwnd, username, password
            return [(i["index"], i["hwnd"], i) for i in data]

    # 如果没找到 json，说明可能是手动开启的，尝试通过标题查找
    print("未发现窗口记录文件，将通过标题查找（此时不支持自动登录输入）")
    title = cfg_manager.get_config("target_window_title", "疯狂赛车怀旧版")
    hwnds = []

    def callback(hwnd, _):
        if win32gui.IsWindowVisible(hwnd) and title in win32gui.GetWindowText(hwnd):
            hwnds.append(hwnd)
        return True

    win32gui.EnumWindows(callback, None)

    # 返回格式兼容: (index, hwnd, account_dict)
    return [(i, hwnd, {"username": "", "password": ""}) for i, hwnd in enumerate(hwnds)]


def main():
    # 1. 初始化配置和引擎
    cfg_mgr = ConfigManager() # 假设你的配置类名
    engine = GameEngine(cfg_mgr)
    
    try:
        # 2. 启动时不再强制重置 Session。Session 将在程序正常退出时清理，或通过手动删除文件。
        # cfg_mgr.reset_session()
        
        # 3. 初始化并运行控制器
        combined_list = get_accurate_window_list(cfg_mgr)
        controller = TaskController(combined_list, cfg_mgr, engine)
        controller.start_monitor()

    except KeyboardInterrupt:
        print("\n[系统] 用户手动停止了脚本")
    except Exception as e:
        print(f"\n运行异常终止: {e}")
    finally:
        # 停止Emergency检测线程
        if 'controller' in dir():
            controller.emergency_mod.stop()
        # 退出前重置 Session
        print("正在执行退出清理...")
        cfg_mgr.reset_session()
        print("房间 Session 已清理，脚本已安全退出。")

if __name__ == "__main__":
    main()