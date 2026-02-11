# -*- coding: utf-8 -*-
"""
签到模块 - 每日签到自动化
适配项目现有架构，使用 GameEngine 和 ConfigManager

签到流程说明：
1. 点击签到入口 (check_in.png 或配置坐标)
2. 等待签到界面加载 (检测 page_flag 图片)
3. 截图整个签到界面
4. 按顺序扫描每个签到格子（4行 x 7列）
5. 对每个格子检测是否有绿色对勾（已签到标志 #4AF638）
6. 找到第一个没有绿色对勾的格子（未签到）
7. 点击该格子进行签到
8. 等待2秒，检测是否回到大厅（lobby_feature.png）
9. 如果没回到大厅，按一次Backspace，再次检测

注意：点击签到后不会有弹窗，直接返回大厅
"""
import time
import os
import win32con
import numpy as np
from app.core.game_engine import GameEngine

class CheckInModule:
    """每日签到自动化模块 - 项目规范版本"""
    
    def __init__(self, config_manager, engine):
        """
        初始化签到模块
        
        Args:
            config_manager: ConfigManager 实例
            engine: GameEngine 实例
        """
        self.cfg_mgr = config_manager
        self.engine = engine
        # 从配置中读取签到相关配置
        self.cfg = self.cfg_mgr.get_config("check_in_automation") or {}
        self.imgs = self.cfg.get("images", {})
        
    def run(self, hwnd):
        """
        执行签到流程
        
        Args:
            hwnd: 游戏窗口句柄
            
        Returns:
            bool: 是否成功完成签到
        """
        self._log(hwnd, "开始执行签到流程...")
        
        if not self.cfg.get('enabled', True):
            self._log(hwnd, "签到功能已禁用")
            return False
        
        try:
            # 步骤1: 点击进入签到界面
            if not self._click_entry(hwnd):
                self._log(hwnd, "未找到签到入口，可能界面未加载")
                return False
            
            # 步骤2: 等待签到界面加载
            if not self._wait_for_check_in_page(hwnd):
                self._log(hwnd, "等待签到界面超时")
            
            # 步骤3: 执行签到 - 扫描并点击未签到的天数
            signed = self._perform_check_in(hwnd)
            
            # 步骤4: 等待并检测是否回到大厅（点击签到后不会有弹窗，直接返回大厅）
            if signed:
                self._wait_and_return_to_lobby(hwnd)
            
            return signed
            
        except Exception as e:
            self._log(hwnd, f"签到过程出错: {e}")
            import traceback
            traceback.print_exc()
            # 出错时按Backspace尝试返回大厅
            self._log(hwnd, "出错，尝试返回大厅...")
            self.engine.key_press(hwnd, win32con.VK_BACK)
            time.sleep(1.0)
            return False
    
    def _click_entry(self, hwnd):
        """
        步骤1: 点击签到入口
        
        操作：
        - 优先使用图片匹配找到签到入口图标
        - 如果图片匹配失败，使用配置的固定坐标
        - 点击后等待1.5秒让界面打开
        """
        # 方式1: 图片匹配
        entry_img = self.imgs.get("entry_icon")
        if entry_img:
            path = self.cfg_mgr.get_template_path(entry_img)
            result = self.engine.match_template(hwnd, path, 0.8)
            if result and result[0]:
                found, score, (x, y) = result
                if found:
                    self._log(hwnd, f"步骤1: 通过图片匹配点击签到入口: ({x}, {y})")
                    self.engine.click(hwnd, x, y)
                    time.sleep(1.5)
                    return True
        
        # 方式2: 固定坐标（备选）
        coords = self.cfg.get("coords", {})
        entry_coord = coords.get("entry")
        if entry_coord:
            self._log(hwnd, f"步骤1: 使用固定坐标点击签到入口: {entry_coord}")
            self.engine.click(hwnd, entry_coord[0], entry_coord[1])
            time.sleep(1.5)
            return True
            
        return False
    
    def _wait_for_check_in_page(self, hwnd, timeout=5):
        """
        步骤2: 等待签到界面加载完成
        
        操作：
        - 检测 page_flag 图片（签到界面特征图）
        - 每0.5秒检测一次，最多检测timeout秒
        - 如果检测到，说明界面已打开
        """
        page_flag_img = self.imgs.get("page_flag")
        if not page_flag_img:
            self._log(hwnd, "步骤2: 未配置页面特征图，跳过等待")
            return True
        
        path = self.cfg_mgr.get_template_path(page_flag_img)
        
        for i in range(timeout * 2):  # 每0.5秒检查一次
            result = self.engine.match_template(hwnd, path, 0.75)
            if result and result[0]:
                self._log(hwnd, "步骤2: 签到界面已加载")
                return True
            time.sleep(0.5)
        
        return False
    
    def _perform_check_in(self, hwnd):
        """
        步骤3: 执行签到点击
        
        操作流程：
        1. 截图整个签到界面（一次性截图，提高效率）
        2. 按顺序扫描每个格子（第1行从左到右，第2行从左到右...）
        3. 对每个格子检测是否有绿色对勾（已签到标志）
           - 绿色对勾颜色: #4AF638 (RGB: 74, 246, 56)
           - 检测范围：格子中心周围40x40像素
           - 容差：±30
        4. 如果检测到绿色对勾 → 该天已签到，继续扫描
        5. 如果没检测到绿色对勾 → 该天未签到，记录下来
        6. 找到第一个未签到的格子后，点击它
        7. 等待并检测是否返回大厅（步骤4处理）
        
        格子布局（4行 x 7列）：
        第1行: 第1天 第2天 第3天 第4天 第5天 第6天 第7天
        第2行: 第8天 第9天 第10天 ...
        ...以此类推
        
        坐标计算：
        - 第一个格子(first_day): [400, 240]
        - 横向偏移(offset_x): 170像素
        - 纵向偏移(offset_y): 230像素
        - 第N天坐标 = [first_day[0] + (列号 * offset_x), first_day[1] + (行号 * offset_y)]
        """
        coords = self.cfg.get("coords", {})
        first_day = coords.get("first_day", [400, 240])
        
        # 获取偏移量
        offset_x = 170  # 横向偏移
        offset_y = 230  # 纵向偏移
        
        # 获取目标颜色（绿色对勾）
        target_color_hex = self.cfg.get("settings", {}).get("target_color_hex", "#4AF638")
        target_rgb = self._hex_to_rgb(target_color_hex)
        
        self._log(hwnd, f"步骤3: 开始扫描签到格子")
        self._log(hwnd, f"       目标颜色: {target_color_hex} (RGB: {target_rgb})")
        self._log(hwnd, f"       扫描范围: 4行 x 7列，起始点: {first_day}")
        
        # 截图整个签到界面（只截图一次）
        screen = self.engine.grab_screen(hwnd)
        if screen is None:
            self._log(hwnd, "步骤3: 截图失败，无法检测签到状态")
            return False
        
        signed_today = False
        first_unsigned_day = None
        
        # 扫描所有格子（4行 x 7列 = 28天）
        for row in range(4):
            for col in range(7):
                day_num = row * 7 + col + 1
                curr_x = first_day[0] + (col * offset_x)
                curr_y = first_day[1] + (row * offset_y)
                
                # 检测该格子是否有绿色对勾
                has_green_check = self._check_green_check_in_screen(
                    screen, hwnd, curr_x, curr_y, target_rgb
                )
                
                if has_green_check:
                    self._log(hwnd, f"       第 {day_num:2d} 天 (坐标: {curr_x}, {curr_y}): 已签到 ✓")
                else:
                    self._log(hwnd, f"       第 {day_num:2d} 天 (坐标: {curr_x}, {curr_y}): 未签到")
                    if first_unsigned_day is None:
                        first_unsigned_day = {
                            'day': day_num,
                            'x': curr_x,
                            'y': curr_y
                        }
        
        # 点击第一个未签到的格子
        if first_unsigned_day:
            day_num = first_unsigned_day['day']
            curr_x = first_unsigned_day['x']
            curr_y = first_unsigned_day['y']
            
            self._log(hwnd, f"步骤3: 点击第 {day_num} 天进行签到...")
            self.engine.click(hwnd, curr_x, curr_y)
            signed_today = True
            time.sleep(0.8)
            
            # 注意：点击签到后不会有弹窗，直接返回大厅
            # 返回大厅的逻辑在步骤4中处理
        else:
            self._log(hwnd, "步骤3: 今日所有天数都已签到过了。")
        
        return signed_today
    
    def _check_green_check_in_screen(self, screen, hwnd, x, y, target_rgb):
        """
        在已截图的图像中检查坐标点周围是否有绿色对勾
        
        原理：
        1. 将基准分辨率坐标转换为当前截图的实际像素坐标
        2. 在该坐标周围40x40像素区域内搜索
        3. 检查每个像素的颜色是否与目标颜色（绿色）匹配
        4. 容差设置为±30，只要有一个像素匹配就返回True
        
        Args:
            screen: OpenCV 截图 (BGR格式 numpy array)
            hwnd: 窗口句柄（用于日志）
            x, y: 基准分辨率下的坐标
            target_rgb: 目标颜色 RGB 元组 (R, G, B)
            
        Returns:
            bool: 是否检测到绿色对勾
        """
        try:
            # 获取窗口实际尺寸
            curr_w, curr_h = self.engine.get_real_client_size(hwnd)
            if curr_w == 0 or curr_h == 0:
                return False
            
            # 获取基准分辨率
            base_w = float(GameEngine.get_base_width())
            base_h = float(GameEngine.get_base_height())
            
            # 将基准分辨率坐标转换为实际截图坐标
            real_x = int(round(x * (curr_w / base_w)))
            real_y = int(round(y * (curr_h / base_h)))
            
            # 检查范围是否有效
            h, w = screen.shape[:2]
            if real_x >= w or real_y >= h or real_x < 0 or real_y < 0:
                return False
            
            # 检查周围 40x40 区域
            check_range = 20
            x_start = max(0, real_x - check_range)
            x_end = min(w, real_x + check_range)
            y_start = max(0, real_y - check_range)
            y_end = min(h, real_y + check_range)
            
            # 提取区域
            region = screen[y_start:y_end, x_start:x_end]
            
            if region.size == 0:
                return False
            
            # 每隔2个像素检查一次（性能优化）
            for px_y in range(0, region.shape[0], 2):
                for px_x in range(0, region.shape[1], 2):
                    # 转换为 Python int 避免 uint8 溢出
                    b = int(region[px_y, px_x, 0])
                    g = int(region[px_y, px_x, 1])
                    r = int(region[px_y, px_x, 2])
                    
                    # 颜色容差判断（绿色对勾颜色 #4AF638）
                    if abs(r - target_rgb[0]) < 30 and \
                       abs(g - target_rgb[1]) < 30 and \
                       abs(b - target_rgb[2]) < 30:
                        return True
            
            return False
            
        except Exception as e:
            self._log(hwnd, f"颜色检测出错: {e}")
            return False
    
    def _wait_and_return_to_lobby(self, hwnd):
        """
        步骤4: 等待并检测是否回到大厅
        
        操作流程：
        1. 点击签到后，等待2秒
        2. 检测是否已回到大厅（lobby_feature.png出现）
        3. 如果已回到大厅，签到完成
        4. 如果没回到大厅，按一次Backspace
        5. 再次检测是否回到大厅
        
        说明：点击签到后不会有弹窗，直接返回大厅
        """
        self._log(hwnd, "步骤4: 等待签到完成并检测是否回到大厅...")
        
        # 等待2秒，让签到完成并返回大厅
        time.sleep(2.0)
        
        # 检测是否已回到大厅
        end_flag = self.imgs.get("end_flag")
        if end_flag:
            path = self.cfg_mgr.get_template_path(end_flag)
            
            # 检测是否回到大厅
            result = self.engine.match_template(hwnd, path, 0.8)
            if result and result[0]:
                # 检测到lobby_feature.png，说明已回到大厅
                self._log(hwnd, "步骤4: 已检测到大厅特征，签到完成！")
                return
            else:
                # 未检测到，说明还在签到界面，按一次Backspace
                self._log(hwnd, "步骤4: 未检测到大厅特征，按Backspace返回...")
                self.engine.key_press(hwnd, win32con.VK_BACK)
                time.sleep(1.0)
                
                # 再次检测
                result = self.engine.match_template(hwnd, path, 0.8)
                if result and result[0]:
                    self._log(hwnd, "步骤4: 已回到大厅，签到完成！")
                else:
                    self._log(hwnd, "步骤4: 警告：可能未成功返回大厅")
        else:
            # 没有配置结束标志图，直接按一次Backspace
            self._log(hwnd, "步骤4: 按Backspace确保返回大厅...")
            self.engine.key_press(hwnd, win32con.VK_BACK)
            time.sleep(1.0)
    
    def _hex_to_rgb(self, hex_str):
        """将十六进制颜色转换为 RGB 元组"""
        hex_str = hex_str.lstrip('#')
        return tuple(int(hex_str[i:i+2], 16) for i in (0, 2, 4))
    
    def _log(self, hwnd, msg):
        """输出日志"""
        print(f"[签到][窗口{hwnd}] {msg}")


# 兼容函数接口，供直接调用
def run_check_in(hwnd, config_manager, engine):
    """
    快速执行签到的便捷函数
    
    使用示例:
        from app.modules.check_in_module import run_check_in
        run_check_in(hwnd, cfg_mgr, engine)
    """
    module = CheckInModule(config_manager, engine)
    return module.run(hwnd)
