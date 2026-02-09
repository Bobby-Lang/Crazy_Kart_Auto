# 启动模块 - 正式使用指南

## ✅ 已完成的改进

### 主要改进

1. ✅ **移除测试限制**：不再限制只启动第一个账号，现在可以启动所有账号
2. ✅ **配置驱动**：路径配置从 `user_config.json` 读取，不再硬编码
3. ✅ **路径验证**：启动前检查文件是否存在，避免运行时错误
4. **安全确认**：保留 `input()` 确认机制，防止误操作
5. **日志完善**：改进日志输出，更加专业

---

## 🎯 正式使用方式

### 方式1：直接独立运行（测试/调试）

```bash
cd D:\DataBase\game\auto_game\app
python modules\launcher_module.py
```

**适用场景**：快速测试启动模块是否正常工作

---

### 方式2：在其他Python程序中调用

```python
from core import ConfigManager
from logger import SimpleLogger
from modules import LauncherModule

# 初始化
config = ConfigManager()
logger = SimpleLogger()

# 读取账号
accounts = [
    {"user": "18682892907", "pass": "password1"},
    {"user": "15020048158", "pass": "password2"},
]

# 获取路径
box_path = config.get_user_config('paths.box_path')
game_path = config.get_user_config('paths.game_path')

# 创建启动模块
launcher = LauncherModule(box_path, game_path, accounts, config, logger)

# 连接信号（可选）
launcher.log_signal.connect(lambda hwnd, level, msg: logger.log(hwnd, level, msg))
launcher.window_ready.connect(lambda idx, hwnd, acc: print(f"窗口{idx+1}就绪: {acc['user']}"))
launcher.all_ready.connect(lambda: print("所有窗口就绪"))

# 启动
launcher.start()
launcher.wait()

# 获取结果
window_results = launcher.window_results
for idx, hwnd, acc in window_results:
    print(f"窗口{idx+1}: {acc['user']} - hwnd: {hwnd}")
```

---

### 方式3：使用示例文件

我提供了3种使用模式的示例：

```bash
cd D:\DataBase\game\auto_game\app

# 简单模式：直接启动所有账号
python example_launcher.py --mode simple

# 回调模式：使用自定义回调函数
python example_launcher.py --mode callback

# 顺序模式：模拟完整流程
python example_launcher.py --mode sequential
```

---

### 方式4：使用完整流程模块（推荐）

```python
from modules import AutoLoginFlow
from core import ConfigManager
from logger import SimpleLogger

config = ConfigManager()
logger = SimpleLogger()

# 读取账号
accounts = [...]
box_path = config.get_user_config('paths.box_path')
game_path = config.get_user_config('paths.game_path')

# 创建流程
flow = AutoLoginFlow(box_path, game_path, accounts, config, logger)

# 一键执行：启动→登录→大厅
flow.execute_full_flow()

# 获取结果
print(f"启动了 {len(flow.window_results)} 个窗口")
print(f"登录成功: {sum(flow.login_results.values())} 个")
print(f"大厅成功: {sum(flow.lobby_results.values())} 个")
```

---

## 📋 配置要求

### user_config.json 中必须配置

```json
{
  "paths": {
    "box_path": "G:\\常用APP\\2box\\2Box.exe",
    "game_path": "D:\\CrazyKart\\CrazyKart\\CrazyKart.exe",
    "account_file": "accounts.txt"
  }
}
```

### accounts.txt 格式

```
18682892907,password1
15020048158,password2
```

---

## 🔌 信号说明

启动模块提供3个信号，用于接收事件通知：

| 信号 | 参数 | 说明 | 使用场景 |
|------|------|------|----------|
| `log_signal` | (hwnd, level, message) | 日志事件 | 记录到文件或UI |
| `window_ready` | (index, hwnd, account) | 窗口就绪 | 更新状态表格，获取hwnd |
| `all_ready` | (无参数) | 全部就绪 | 触发下一步操作（登录） |

---

## 💡 常见使用模式

### 模式1：启动后立即进行登录

```python
# 等待所有窗口启动完成后
all_ready_event = threading.Event()

def on_all_ready():
    all_ready_event.set()

launcher.all_ready.connect(on_all_ready)
launcher.start()

# 等待所有窗口就绪
all_ready_event.wait()

# 所有窗口就绪后，开始登录
login = LoginModule(...)
login.start()
```

### 模式2：逐个窗口启动并登录

```python
for account in accounts:
    # 单独启动
    launcher = LauncherModule(box_path, game_path, [account], config, logger)
    launcher.start()
    launcher.wait()
    
    # 单独登录
    login = LoginModule([account], config, logger)
    login.start()
    login.wait()
```

---

## ⚠️ 注意事项

1. **路径必须正确**
   - 确保 2Box 和游戏路径正确
   - 程序会检查文件是否存在

2. **账号格式**
   - `accounts.txt` 每行一个账号：`账号,密码`
   - 不要有空行

3. **启动时间**
   - 每个窗口启动需要 3-5 秒
   - N个账号大约需要 N×(3-5) + 额外准备时间

4. **窗口标题**
   - 游戏窗口标题必须包含"疯狂赛车怀旧版"
   - 否则无法识别

5. **2Box 要求**
   - 2Box 必须正常运行
   - 支持快捷键 Alt+F → O（打开文件）

---

## ✅ 状态说明

启动完成后，通过 `launcher.window_results` 可以获取所有窗口信息：

```python
window_results = launcher.window_results

# 格式：[(index, hwnd, account), ...]
# 示例：
# [
#   (0, 12345, {"user": "18682892907", "pass": "..."}),
#   (1, 67890, {"user": "15020048158", "pass": "..."}),
# ]
```

---

## 🎯 与其他模块的集成

启动模块与登录、大厅模块的集成方式：

```python
# 1. 启动
launcher = LauncherModule(...)
launcher.start()
launcher.wait()
hwnds = launcher.window_results  # 获取窗口列表

# 2. 登录
login = LoginModule(hwnds, ...)
login.start()
login.wait()

# 3. 大厅
lobby = LobbyModule(hwnds, ...)
lobby.start()
lobby.wait()

# 4. 创建房间
# create_room = CreateRoomModule(...)
```

或者使用完整流程：

```python
flow = AutoLoginFlow(...)
flow.execute_full_flow()
```

---

**完成状态**：启动模块已完成正式改造并测试通过，可正常调用使用！
