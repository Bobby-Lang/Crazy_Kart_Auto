# 游戏自动化助手 - 模块化架构

## 项目结构

```
app/
├── core/                          # 核心模块
│   ├── __init__.py                # 模块初始化
│   ├── game_engine.py             # 统一游戏引擎
│   ├── config_manager.py          # 配置管理器
│   ├── state_manager.py           # 游戏状态管理器
│   ├── global_pause_controller.py # 全局暂停控制器
│   └── window_monitor.py          # 窗口监控器
├── modules/                       # 业务模块
│   ├── __init__.py                # 模块初始化
│   ├── launcher_module.py         # 启动器模块
│   ├── login_module.py            # 登录模块
│   ├── create_room_module.py      # 创建房间模块
│   ├── join_room_module.py        # 加入房间模块
│   ├── lobby_module.py            # 大厅模块
│   └── flow_module.py             # 流程控制模块
├── ui/                            # UI界面模块
│   └── __init__.py                # 模块初始化
├── data/                          # 数据文件
│   ├── accounts.txt               # 账号文件
│   └── mode_counts.json           # 模式计数文件
├── templates/                     # 图片模板目录
├── logger.py                      # 日志记录器
├── recovery_waiter.py            # 对局结束等候器
├── test_full_auto.py             # 完整自动化测试脚本
└── docs/                         # 文档目录
    └── README.md                 # 本文档
```

## 已完成模块

### 1. 核心模块 (core/)

#### GameEngine (game_engine.py)
统一的游戏自动化引擎，提供以下功能：
- ✅ `grab_screen(hwnd, roi)` - 后台截图，支持ROI区域
- ✅ `click(hwnd, x, y)` - 物理模拟点击
- ✅ `paste_text(hwnd, text)` - 剪贴板粘贴文本
- ✅ `match_template(hwnd, img_path, threshold, roi)` - 模板匹配识别图片
- ✅ `activate_window(hwnd)` - 强力激活窗口
- ✅ `find_windows(keyword)` - 查找包含关键词的窗口
- ✅ `cascade_windows(hwnds, offset_x, offset_y)` - 窗口阶梯排列

#### ConfigManager (config_manager.py)
配置管理器，负责加载和管理配置：
- ✅ 加载游戏配置 (config.json)
- ✅ 加载/保存用户配置 (user_config.json)
- ✅ 支持点号分隔的配置访问 (如 'mode_configs.0.name')
- ✅ 自定义配置默认值

#### GameStateManager (state_manager.py)
游戏状态管理器，负责管理游戏状态：
- ✅ 房主窗口句柄管理
- ✅ 房间号管理
- ✅ 对局计数（按模式分别计数）
- ✅ 窗口进度管理
- ✅ 支持检查模式是否完成
- ✅ 提供状态摘要

#### GlobalPauseController (global_pause_controller.py)
全局暂停控制器，负责控制全局暂停状态：
- ✅ 暂停/恢复控制
- ✅ 异常窗口追踪
- ✅ 检查是否所有窗口异常
- ✅ 更新异常句柄（窗口重启后）

#### WindowMonitor (window_monitor.py)
窗口状态监控器，每10秒检测一次：
- ✅ 监控循环检测（可配置检测间隔）
- ✅ 检测窗口掉线/崩溃
- ✅ 发送状态更新信号
- ✅ 发送窗口异常信号
- ✅ 检测所有窗口异常情况
- ✅ 支持暂停/恢复监控

### 2. 业务模块 (modules/)

#### LauncherModule (launcher_module.py)
游戏启动模块，负责启动游戏窗口：
- ✅ 启动指定数量的游戏窗口
- ✅ 窗口位置自动排列
- ✅ 支持多开启动
- ✅ 窗口句柄收集与管理

#### LoginModule (login_module.py)
登录模块，负责账号登录：
- ✅ 从accounts.txt读取账号信息
- ✅ 自动输入账号密码
- ✅ 支持多账号轮换登录
- ✅ 登录状态检测

#### CreateRoomModule (create_room_module.py)
创建房间模块：
- ✅ 房主创建房间
- ✅ 设置房间密码
- ✅ 房间模式选择
- ✅ 房间状态维护

#### JoinRoomModule (join_room_module.py)
加入房间模块：
- ⏳ 成员加入指定房间（待测试）
- ⏳ 密码自动输入（待测试）
- ⏳ 房间人数检测（待测试）
- ⏳ 加入状态反馈（待测试）

#### LobbyModule (lobby_module.py)
大厅模块：
- ✅ 窗口排列功能（阶梯排列）
- ✅ 登录序列执行（配置化点击流程）
- ✅ 智能点击重试（带图片校验）
- ✅ 大厅状态检测（图片模板匹配）

#### FlowModule (flow_module.py)
流程控制模块：
- ⏳ 整合启动、登录、大厅模块（待测试）
- ⏳ 完整流程执行（待测试）
- ⏳ 结果统计和报告（待测试）
- ⏳ 异常处理和状态跟踪（待测试）

### 3. 辅助模块

#### Logger (logger.py)
简单日志记录器
- ✅ 标准化日志格式（[时间] [级别] 消息）
- ✅ 支持带hwnd的日志输出
- ✅ 中文编码兼容（Windows GBK）
- ✅ 支持日志回调函数

#### RecoveryWaiter (recovery_waiter.py)
对局结束等候器
- ✅ 检测房主是否在房间（通过房主标识）
- ✅ 检测对局是否结束（通过开始按钮）
- ✅ 可配置检测间隔（默认5秒）
- ✅ 可配置最长等待时间（默认10分钟）

### 4. 测试脚本

#### test_full_auto.py
完整自动化测试脚本，用于测试整个自动化流程：
```bash
# 运行完整自动化测试
python test_full_auto.py
```

### 5. 配置文件

#### config.json
游戏配置文件，包含坐标、图片模板等

#### user_config.json
用户配置文件，包含路径、局数设置等

#### accounts.txt
账号密码文件，格式为每行一个账号密码，用空格分隔

## 快速开始

### 1. 运行完整自动化测试

```bash
cd D:\DataBase\game\auto_game\app
python test_full_auto.py
```

### 2. 单独测试某个模块

```bash
# 例如：测试游戏引擎（查看窗口截图）
python -c "from core.game_engine import GameEngine; engine = GameEngine(); print(engine.find_windows('疯狂赛车怀旧版'))"

# 例如：测试配置管理器（查看配置加载）
python -c "from core.config_manager import ConfigManager; config = ConfigManager(); print(config.get_config('target_window_title'))"
```

### 3. 在Python中使用模块

```python
# 游戏引擎示例
from core import GameEngine

engine = GameEngine()

# 查找窗口
hwnds = engine.find_windows("疯狂赛车怀旧版")
print(f"找到 {len(hwnds)} 个窗口")

# 截图
if hwnds:
    frame = engine.grab_screen(hwnds[0])
    print(f"截图尺寸: {frame.shape}")

# 配置管理示例
from core import ConfigManager

config = ConfigManager()
title = config.get_config('target_window_title')
print(f"目标窗口: {title}")

# 状态管理示例
from core import GameStateManager, ConfigManager
from logger import SimpleLogger

config = ConfigManager()
logger = SimpleLogger()
state = GameStateManager(config, logger)

# 设置模式
state.set_current_mode('mode_item')

# 模拟对局完成
state.increment_game_count()
current, target = state.get_progress()
print(f"进度: {current}/{target}")
```

## 测试结果

当前测试状态（基于实际运行）：

### ✅ 已通过测试的模块

1. **Logger** - 日志记录正常，中文编码兼容
2. **ConfigManager** - 配置加载正常，能读取config.json
3. **GameEngine** - 窗口查找正常，截图功能正常（找到2个窗口，截图尺寸1080x1920x3）
4. **GameStateManager** - 状态管理正常，计数功能正常
5. **GlobalPauseController** - 暂停控制正常，异常追踪正常
6. **LauncherModule** - 窗口启动正常，位置排列正常
7. **LoginModule** - 账号登录正常，多账号切换正常
8. **CreateRoomModule** - 房间创建正常，密码设置正常
9. **LobbyModule** - 大厅功能正常，签到任务正常

### ⏳ 待测试模块

1. **JoinRoomModule** - 加入房间模块待测试
2. **FlowModule** - 流程控制模块待测试

### ⚠️ 已知问题

1. **JoinRoomModule** 中的房主识别逻辑缺少亮度检测和黑屏判断，可能导致黑屏窗口被误识别为房主
2. **FlowModule** 缺少完整的异常处理机制，需要完善流程中断和恢复逻辑

### ⏳ 待完成模块

- ui/ 目录下的UI组件
- 异常处理器 (exception_handler.py)
- 主工作流 (main_workflow.py)
- 主界面 (main_gui.py)

## 配置说明

### 默认用户配置 (user_config.json)

```json
{
  "paths": {
    "box_path": "",
    "game_path": "",
    "account_file": "accounts.txt"
  },
  "room_password": "9527",
  "daily_tasks": {
    "mode_item": {
      "enabled": True,
      "target_games": 8
    },
    "mode_speed": {
      "enabled": True,
      "target_games": 8
    }
  },
  "extra_features": {
    "auto_checkin": False,
    "auto_claim_tasks": False
  },
  "post_task": {
    "close_game": False,
    "shutdown": False
  },
  "window_monitor": {
    "enabled": True,
    "check_interval": 10,
    "auto_recovery": True
  },
  "recovery_config": {
    "force_close": True,
    "close_timeout": 5,
    "restart_timeout": 90,
    "retry_count": 1,
    "game_end_check_interval": 5,
    "max_wait_time": 600
  }
}
```

## 调试建议

### 1. 逐模块调试
建议按以下顺序调试：
1. 先确保核心模块正常（已在test_all中验证）
2. 然后调试窗口监控（WindowMonitor）
3. 再调试业务模块（launcher, login等）
4. 最后集成所有模块

### 2. 使用日志
每个模块都支持日志输出，可以通过修改SimpleLogger来查看详细日志

### 3. 配置调整
遇到问题时，可以先检查配置文件是否正确：
- config.json：确认图片模板路径、坐标配置正确
- user_config.json：确认路径、间隔、超时等设置合理
- accounts.txt：确认账号密码格式正确

## 下一步计划

待开发的模块（可根据需要逐步添加）：

1. **UI组件** (ui/)
   - main_window.py - 主窗口
   - config_widget.py - 配置控件
   - mode_combo_widget.py - 模式下拉控件
   - status_table_widget.py - 状态表格
   - log_widget.py - 日志控件

2. **主程序**
   - main_workflow.py - 主工作流
   - main_gui.py - 主程序入口

## 注意事项

1. **配置文件路径**：默认使用config.json和user_config.json，需确保文件存在
2. **图片模板**：config.json中配置的图片路径需要在templates目录下存在
3. **窗口标题**：确保游戏窗口标题包含"疯狂赛车怀旧版"
4. **依赖库**：需要安装cv2, numpy, win32gui, win32api等依赖
5. **账号文件**：accounts.txt需要按照正确的格式填写账号密码

## 问题反馈

如有问题，可以：
1. 运行 `python test_full_auto.py` 查看完整自动化测试结果
2. 查看日志输出定位问题

---

**创建时间**: 2025-01-29
**版本**: v1.1 - 业务模块基本完成
**状态**: 核心模块和LauncherModule、LoginModule、CreateRoomModule、LobbyModule已通过测试，JoinRoomModule和FlowModule待测试，可进入UI开发阶段