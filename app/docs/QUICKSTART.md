# 快速开始指南

## 已完成的工作

### 核心模块 (core/) ✅

1. **game_engine.py** - 统一游戏引擎
   - 后台截图、点击、输入、匹配等基础功能

2. **config_manager.py** - 配置管理器
   - 加载config.json和user_config.json

3. **state_manager.py** - 状态管理器
   - 管理房间号、对局计数、房主等

4. **global_pause_controller.py** - 全局暂停控制器
   - 处理全局暂停、异常追踪

5. **window_monitor.py** - 窗口监控器
   - 10秒监控一次，检测异常窗口

### 辅助模块 ✅

1. **logger.py** - 日志记录器
2. **recovery_waiter.py** - 对局结束等候器
3. **test_modules.py** - 模块测试脚本

### 测试结果 ✅

所有核心模块已通过测试：
- ✅ Logger: 日志正常
- ✅ ConfigManager: 配置加载正常
- ✅ GameEngine: 窗口查找、截图正常
- ✅ GameStateManager: 状态管理正常
- ✅ GlobalPauseController: 暂停控制正常

## 如何使用

### 1. 测试所有模块

```bash
cd app
python test_modules.py all
```

### 2. 单独测试某个模块

```bash
# 测试游戏引擎
python test_modules.py engine

# 测试配置管理器
python test_modules.py config

# 测试状态管理器
python test_modules.py state
```

### 3. 在Python代码中导入使用

```python
# 导入核心模块
from core import GameEngine, ConfigManager, GameStateManager, GlobalPauseController
from logger import SimpleLogger

# 创建实例
logger = SimpleLogger()
config = ConfigManager()
engine = GameEngine()
state = GameStateManager(config, logger)
```

## 目录结构

```
app/
├── core/                          # 核心模块 ✅
│   ├── __init__.py
│   ├── game_engine.py
│   ├── config_manager.py
│   ├── state_manager.py
│   ├── global_pause_controller.py
│   └── window_monitor.py
├── modules/                       # 业务模块 (待添加)
│   └── __init__.py
├── ui/                            # UI组件 (待添加)
│   └── __init__.py
├── logger.py                      # 日志 ✅
├── recovery_waiter.py            # 等候器 ✅
├── test_modules.py               # 测试脚本 ✅
├── config.json                   # 游戏配置
├── user_config.json              # 用户配置
├── README.md                      # 详细文档
└── QUICKSTART.md                  # 本文档
```

## 配置文件

### config.json
位于 `D:\DataBase\game\auto_game\app\config.json`
包含：坐标、图片模板路径、模式配置等

### user_config.json
位于 `D:\DataBase\game\auto_game\app\user_config.json`
包含：路径设置、局数设置、监控配置等

## 下一步开发

### 待开发的模块（按优先级）

**高优先级：业务模块 (modules/)**
1. `launcher_module.py` - 启动窗口逻辑
2. `login_module.py` - 登录逻辑
3. `create_room_module.py` - 创建房间逻辑
4. `join_room_module.py` - 加入房间逻辑
5. `ready_module.py` - 准备开始逻辑

**中优先级：异常恢复**
6. `exception_handler.py` - 异常处理器

**低优先级：UI组件 (ui/)**
7. `main_window.py` - 主窗口UI
8. `config_widget.py` - 配置控件
9. `status_table_widget.py` - 状态表格

## 调试建议

### 逐模块测试

1. **先测试核心模块**（已完成 ✅）
2. **再测试单个业务模块**
   - 把业务逻辑从现有文件迁移到modules/*.py
   - 使用test_modules.py的方式创建测试函数
   - 单独运行测试验证

3. **最后集成测试**
   - 把各模块串联起来
   - 测试完整流程

### 如何调试业务模块

以launcher_module为例：

1. 创建 `app/modules/launcher_module.py`
2. 编写启动窗口的逻辑
3. 在`test_modules.py`中添加测试函数：
```python
def test_launcher_module():
    print_separator("测试启动模块")
    logger = SimpleLogger()
    engine = GameEngine()
    # ... 你的测试代码
```
4. 运行测试：`python test_modules.py launcher`

## 关键功能说明

### 1. 游戏引擎 (GameEngine)

```python
from core import GameEngine

engine = GameEngine()

# 查找窗口
hwnds = engine.find_windows("疯狂赛车怀旧版")

# 截图
frame = engine.grab_screen(hwnds[0])

# 点击
engine.click(hwnds[0], 100, 200)

# 输入文本
engine.paste_text(hwnds[0], "测试文本")

# 模板匹配
found, score, loc = engine.match_template(hwnds[0], "template.png", threshold=0.8)
```

### 2. 配置管理器 (ConfigManager)

```python
from core import ConfigManager

config = ConfigManager()

# 获取配置值
title = config.get_config('target_window_title')
password = config.get_config('room_password')

# 获取用户配置
box_path = config.get_user_config('paths.box_path')
interval = config.get_user_config('window_monitor.check_interval')

# 设置用户配置
config.set_user_config('room_password', '123456')
config.save_user_config()
```

### 3. 状态管理器 (GameStateManager)

```python
from core import GameStateManager, ConfigManager
from logger import SimpleLogger

config = ConfigManager()
logger = SimpleLogger()
state = GameStateManager(config, logger)

# 设置房主
state.set_host_hwnd(12345)

# 设置房间号
state.set_room_id('##12345')

# 设置当前模式
state.set_current_mode('mode_item')

# 对局计数+1
state.increment_game_count()

# 获取进度
current, target = state.get_progress()

# 检查是否完成
if state.is_mode_completed():
    print("模式已完成")
```

### 4. 窗口监控器 (WindowMonitor)

```python
from core import WindowMonitor
from PyQt6.QtCore import QCoreApplication
import sys

# 创建应用（监控器需要Qt）
app = QCoreApplication(sys.argv)

# 创建监控器
hwnds = [12345, 67890]  # 你的窗口句柄
monitor = WindowMonitor(hwnds, engine, config_manager, logger)

# 连接信号
monitor.window_exception.connect(lambda hwnd, etype: print(f"异常: {hwnd}"))
monitor.status_update.connect(lambda states: print("状态更新"))

# 启动监控
monitor.start()

# 保持运行
sys.exit(app.exec())
```

## 常见问题

### Q1: 模块找不到？

A: 确保在app目录下运行，或正确设置PYTHONPATH：
```bash
cd app
python test_modules.py all
```

### Q2: 配置文件不存在？

A: 初始化时会自动创建user_config.json，config.json需要从父目录复制。

### Q3: 中文乱码？

A: Logger已处理中文编码，但仍可能有部分显示问题，不影响功能。

### Q4: 模块测试失败？

A: 先运行 `python test_modules.py all` 看是哪个模块失败，然后单独测试该模块。

## 下一步

现在可以开始开发和调试业务模块了！建议按以下顺序：

1. 先把现有的login_game.py、creat_room.py等逻辑迁移到modules/
2. 使用test_modules.py的方式逐个测试
3. 确认每个模块独立运行正常
4. 最后集成到主GUI中

---

**当前版本**: v1.0
**完成度**: 核心模块100%，业务模块0%，UI组件0%
**状态**: 可以开始业务模块开发和调试
