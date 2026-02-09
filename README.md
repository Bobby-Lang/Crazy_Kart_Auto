# Crazy Kart Auto Game Controller

🚀 **一键自动化** 运行《疯狂赛车》并完成日常任务的桌面应用

---

## 📖 项目简介

`auto_game` 是一个基于 **PyQt6** 搭建的图形化工具，整合了游戏启动、登录、房间创建/加入、任务执行等模块，实现了对《疯狂赛车》游戏的全自动化控制。

- **模块化**：核心、业务、UI 三层结构，易于扩展
- **可视化**：主窗口提供任务控制、账号管理、配置编辑与日志输出
- **可配置**：所有路径、热键、任务目标均通过 `config.json` / `user_config.json` 管理

---

## 📦 项目结构

```text
auto_game/
├─ app/
│  ├─ core/               # 核心模块（游戏引擎、配置、状态管理）
│  ├─ modules/            # 业务模块（启动、登录、创建房间等）
│  ├─ ui/                 # UI 组件（MainWindow）
│  ├─ data/                # 运行时数据（账户、统计）
│  ├─ templates/          # UI 使用的图片模板
│  ├─ logger.py           # 简易日志实现
│  └─ test_full_auto.py   # 完整自动化测试脚本
├─ gui.py                  # 程序入口（启动 QApplication）
├─ main.py                 # 直接运行入口（兼容旧脚本）
└─ README.md              # 本文件（项目说明）
```

---

## ⚙️ 安装依赖

```bash
# 克隆仓库（已完成）
# 创建虚拟环境（可选）
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate

# 安装 Python 依赖
pip install -r requirements.txt  # 如不存在，可手动安装以下库
pip install pyqt6 opencv-python numpy pywin32
```

> **注意**：本项目在 Windows 上运行，需要 `pywin32` 提供的 `win32gui`、`win32api` 等接口。

---

## ▶️ 快速开始

1. **配置**
   - 将游戏可执行文件路径、沙盒路径填写在 `app/data/config.json` 或 UI 的 **配置管理** 页面。
   - 在 `app/data/accounts.txt` 中按 `用户名,密码`（每行一个）填写账号。
   - 如需修改快捷键，可在 UI **配置管理** 中编辑 `pause_hotkey`、`stop_hotkey`、`reset_hotkey`。
2. **运行**
   ```bash
   python gui.py   # 或直接 double‑click gui.py
   ```
   主窗口会打开，点击 **▶ 开始任务** 即可执行全流程。
3. **日志**
   - 窗口底部的 **运行日志** 实时展示标准输出与错误信息。
   - 支持 **清空日志** 与 **保存日志**（保存为 `log_YYYYMMDD_HHMMSS.txt`）。

---

## 🛠️ 主要功能

| 模块 | 功能 | 状态 |
|------|------|------|
| **GameEngine** | 窗口定位、截图、点击、文字粘贴、模板匹配 | ✅ 完成 |
| **ConfigManager** | 读取/写入 `config.json`、`user_config.json` | ✅ 完成 |
| **GameStateManager** | 任务计数、模式切换、进度统计 | ✅ 完成 |
| **LauncherModule** | 多开游戏窗口并自动排列 | ✅ 完成 |
| **LoginModule** | 自动登录账号、轮换多账号 | ✅ 完成 |
| **CreateRoomModule** | 创建房间、设置密码、选择模式 | ✅ 完成 |
| **JoinRoomModule** | 加入已有房间（待测试） | ⏳ 待测 |
| **LobbyModule** | 大厅自动点击、检测任务完成 | ✅ 完成 |
| **FlowModule** | 整体工作流编排（待完善） | ⏳ 待测 |
| **UI (MainWindow)** | 任务控制、账号管理、配置编辑、日志展示 | ✅ 完成 |

---

## 📚 开发指南

- **代码风格**：PEP 8 + 中文注释。
- **新增模块**：在 `app/modules/` 中创建 `*.py`，并在 `__init__.py` 中导入。
- **UI 扩展**：推荐使用 Qt Designer 生成 `.ui` 文件，再使用 `pyuic6` 转为 Python 类，保持 UI 与逻辑分离。
- **单元测试**：在 `tests/`（若无）添加 pytest 用例，运行 `pytest -q` 进行 CI。

---

## 🤝 贡献指南

1. Fork 本仓库并创建你的分支。
2. 完成修改后提交并推送。
3. 发起 Pull Request，描述清晰的变更内容。
4. 请确保 **所有代码通过本地测试** 并遵循项目的代码规范。

---

## 📜 许可证

本项目采用 **MIT License**（你可以自行在根目录添加 `LICENSE` 文件），详细内容请参考 LICENSE 文件。

---

## 📞 联系方式

如有使用上的问题或功能需求，欢迎提 **Issue** 或联系作者 `langtingbo@hotmail.com`。

---

*Created with ❤️ by the OpenAI‑assisted development team*