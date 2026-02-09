# -*- coding: utf-8 -*-
"""
Auto Game UI 启动入口
"""

import sys
import os

# 确保项目根目录在路径中
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from app.ui.main_window import main

if __name__ == "__main__":
    main()
