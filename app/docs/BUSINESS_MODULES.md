# 业务模块完成说明

## ✅ 已完成的模块

按照你的要求，已将 `login_game.py` 模块化为以下4个功能模块：

### 1. **launcher_module.py** - 启动模块

**功能**：
- ✅ 检测并启动2box多开软件
- ✅ 从2box打开指定数量的游戏窗口

**主要方法**：
- `start_2box()` - 启动2box
- `launch_game_windows()` - 打开游戏窗口
- `open_game_from_2box()` - 在2box中打开游戏
- `wait_for_new_window()` - 等待新窗口出现

**信号**：
- `log_signal(hwnd, level, message)` - 日志信号
- `window_ready(index, hwnd, account)` - 窗口就绪信号
- `all_ready` - 所有窗口就绪信号

---

### 2. **login_module.py** - 登录模块

**功能**：
- ✅ 激活游戏窗口
- ✅ 输入账号密码
- ✅ 点击登录按钮

**主要方法**：
- `login_single_window(hwnd, username, password)` - 登录单个窗口
- `stop()` - 停止登录流程

**信号**：
- `log_signal(hwnd, level, message)` - 日志信号
- `progress_update(index, status)` - 进度更新信号
- `login_complete(index, hwnd, account, success)` - 登录完成信号

---

### 3. **lobby_module.py** - 大厅模块

**功能**：
- ✅ 窗口排列（如果配置启用）
- ✅ 执行登录序列（点击流程）
- ✅ 检测大厅状态

**主要方法**：
- `arrange_windows()` - 窗口阶梯排列
- `execute_login_sequence(hwnd)` - 执行配置的点击序列
- `smart_click(hwnd, name, coords, check_img, max_retries, delay)` - 智能点击（带校验）
- `find_image(hwnd, img_name, threshold)` - 检测图片
- `check_lobby_status(hwnd)` - 检测大厅状态

**信号**：
- `log_signal(hwnd, level, message)` - 日志信号
- `progress_update(index, status)` - 进度更新信号
- `lobby_complete(index, hwnd, account, success)` - 大厅完成信号

---

### 4. **flow_module.py** - 完整流程模块

**功能**：
- ✅ 整合启动、登录、大厅三个模块
- ✅ 提供完整的一键流程管理
- ✅ 输出流程摘要

**主要方法**：
- `execute_full_flow()` - 执行完整流程
- `launch_windows()` - 启动窗口
- `login_windows()` - 登录所有窗口
- `enter_lobby()` - 进入大厅
- `print_summary()` - 打印流程摘要
- `stop()` - 停止所有模块

---

## 📁 目录结构

```
D:\DataBase\game\auto_game\app\
├── core/                          # 核心模块 ✅
│   ├── game_engine.py
│   ├── config_manager.py
│   ├── state_manager.py
│   ├── global_pause_controller.py
│   └── window_monitor.py
├── modules/                       # 业务模块 ✅（新增）
│   ├── __init__.py
│   ├── launcher_module.py         # 启动模块
│   ├── login_module.py            # 登录模块
│   ├── lobby_module.py            # 大厅模块
│   └── flow_module.py             # 完整流程模块
├── logger.py                      # 日志记录器
├── recovery_waiter.py
├── test_modules.py               # 核心模块测试
├── test_business_modules.py      # 业务模块测试（新增）
├── config.json
├── user_config.json
├── README.md
└── QUICKSTART.md
```

---

## 🧪 测试状态

### 导入测试 ✅

```bash
cd D:\DataBase\game\auto_game\app
python test_business_modules.py import
```

**结果**：所有模块导入成功

### 配置测试 ✅

```bash
python test_business_modules.py config
```

**测试内容**：
- ConfigManager加载
- 账号文件读取
- 配置路径获取

---

## 🎯 使用示例

### 方式1：单独使用启动模块

```python
from modules import LauncherModule
from core import ConfigManager
from logger import SimpleLogger

config = ConfigManager()
logger = SimpleLogger()

accounts = [
    {"user": "18682892907", "pass": "password1"},
    {"user": "15020048158", "pass": "password2"}
]

launcher = LauncherModule(
    box_path="G:\\常用APP\\2box\\2Box.exe",
    game_path="D:\\CrazyKart\\CrazyKart\\CrazyKart.exe",
    accounts=accounts,
    config_manager=config,
    logger=logger
)

# 连接信号
launcher.log_signal.connect(lambda hwnd, level, msg: logger.log(hwnd, level, msg))
launcher.window_ready.connect(lambda idx, hwnd, acc: print(f"窗口{idx}就绪"))

# 启动
launcher.start()
launcher.wait()
```

### 方式2：单独使用登录模块

```python
from modules import LoginModule

hwnd_list = [
    (0, 12345, {"user": "18682892907", "pass": "password1"}),
    (1, 67890, {"user": "15020048158", "pass": "password2"})
]

login = LoginModule(hwnd_list, config, logger)

login.start()
login.wait()
```

### 方式3：单独使用大厅模块

```python
from modules import LobbyModule

hwnd_list = [
    (0, 12345, {"user": "18682892907", "pass": "password1"}),
    (1, 67890, {"user": "15020048158", "pass": "password2"}),
]

lobby = LobbyModule(hwnd_list, config, logger)

lobby.start()
lobby.wait()
```

### 方式4：使用完整流程（推荐）

```python
from modules import AutoLoginFlow

flow = AutoLoginFlow(
    box_path="G:\\常用APP\\2box\\2Box.exe",
    game_path="D:\\CrazyKart\\CrazyKart\\CrazyKart.exe",
    accounts=accounts,
    config_manager=config,
    logger=logger
)

# 一键执行完整流程
flow.execute_full_flow()
```

---

## 🔌 信号连接示例

### 连接到日志

```python
launcher = LauncherModule(...)
launcher.log_signal.connect(lambda hwnd, level, msg: print(msg))
```

### 连接到进度更新

```python
login = LoginModule(...)
login.progress_update.connect(lambda idx, status: print(f"窗口{idx}: {status}"))
```

### 连接到完成事件

```python
# 启动模块
launcher.window_ready.connect(lambda idx, hwnd, acc: handle_window_ready(idx, hwnd, acc))

# 登录模块
login.login_complete.connect(lambda idx, hwnd, acc, success: print(f"窗口{idx}登录{'成功' if success else '失败'}"))

# 大厅模块
lobby.lobby_complete.connect(lambda idx, hwnd, acc, success: print(f"窗口{idx}进入大厅{'成功' if success else '失败'}"))
```

---

## ⚙️ 配置依赖

### config.json 需要的配置

```json
{
  "target_window_title": "疯狂赛车怀旧版",
  "input_coords": {
    "acc_input": [520, 300],
    "pwd_input": [520, 350]
  },
  "login_sequence": [
    {
      "name": "第一步：服务器列表",
      "coord": [1000, 600],
      "check_img": "check_point_1.png",
      "max_retries": 2
    },
    ...
  ],
  "final_state": {
    "img_name": "check_point_5.png",
    "threshold": 0.8,
    "timeout_sec": 30
  },
  "window_arrangement": {
    "enabled": true,
    "偏移设置": {
      "offset_x": 60,
      "offset_y": 40
    }
  }
}
```

### user_config.json 需要的配置

```json
{
  "paths": {
    "box_path": "G:\\常用APP\\2box\\2Box.exe",
    "game_path": "D:\\CrazyKart\\CrazyKart\\CrazyKart.exe",
    "account_file": "accounts.txt"
  }
}
```

---

## 📋 模块对应的原代码

| 原代码模块 | 新模块 | 说明 |
|-----------|--------|------|
| `LauncherThread` | `launcher_module.py` | 窗口启动逻辑 |
| `SequentialGameWorker`登录部分 | `login_module.py` | 登录输入逻辑 |
| `SequentialGameWorker`序列+大厅部分 | `lobby_module.py` | 序列点击和大厅检测 |
| `MainWindow`主流程 | `flow_module.py` | 完整流程整合 |

---

## 🚀 下一步开发

### 待添加的模块

1. **create_room_module.py** - 创建房间逻辑
2. **join_room_module.py** - 加入房间逻辑
3. **ready_module.py** - 准备开始逻辑
4. **daily_task_module.py** - 每日任务逻辑
5. **exception_handler.py** - 异常处理器
6. **main_workflow.py** - 主工作流
7. **main_gui.py** - 主GUI界面

---

## 📝 测试注意事项

### 测试启动模块

```bash
python test_business_modules.py launcher
```

**注意**：这会实际启动游戏窗口！

### 测试完整流程

```bash
python test_business_modules.py flow
```

**注意**：这会完整执行启动→登录→大厅流程！

### 建议测试顺序

1. 先测试模块导入（安全）
   ```bash
   python test_business_modules.py import
   ```

2. 再测试配置加载（安全）
   ```bash
   python test_business_modules.py config
   ```

3. 最后测试功能模块（需要实际窗口）
   - 取消注释 `test_business_modules.py` 中的相应代码

---

## ✅ 完成状态

| 模块 | 状态 | 说明 |
|------|------|------|
| launcher_module.py | ✅ 完成 | 启动2box和游戏窗口 |
| login_module.py | ✅ 完成 | 输入账号密码并登录 |
| lobby_module.py | ✅ 完成 | 窗口排列+点击序列+大厅检测 |
| flow_module.py | ✅ 完成 | 完整流程整合 |
| test_business_modules.py | ✅ 完成 | 模块测试脚本 |

**总计**：4个功能模块 + 1个测试脚本，全部完成并可独立调试！

---

**创建时间**: 2025-01-28
**版本**: v1.0
**状态**: 业务模块可独立调试，UI模块待开发
