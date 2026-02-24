# -*- coding: utf-8 -*-
import time
import os
import win32con

class TaskModule:
    def __init__(self, config_manager, engine):
        self.cfg_mgr = config_manager
        self.engine = engine
        self.cfg = self.cfg_mgr.get_config("task_automation") or {}
        self.imgs = self.cfg.get("images", {})

    def run(self, hwnd):
        """执行完整的领取流程"""
        
        # 1. 在大厅点击任务图标进入
        if not self._ensure_entry(hwnd, self.imgs.get("daily_page_flag")):
            return

        # 2. ======= 日常任务处理 =======
        daily_flag = self.imgs.get("daily_page_flag")
        
        # 领取日常任务列表奖励
        self._loop_click_claim(hwnd, daily_flag, max_clicks=15)
        
        # 领取日常活跃度宝箱 (左侧)
        daily_boxes = self.imgs.get("daily_reward_boxes", [])
        self._scan_and_click_boxes(hwnd, daily_boxes, daily_flag)
        
        # 领取本周活跃度宝箱 (上方)
        weekly_boxes = self.imgs.get("weekly_reward_boxes", [])
        self._scan_and_click_boxes(hwnd, weekly_boxes, daily_flag)
        
        # 3. ======= 车队任务处理 =======
        # 点击车队任务页签
        self._click_team_tab(hwnd)
        team_flag = self.imgs.get("team_page_flag")

        # 等待车队任务页加载，然后领取
        if self._wait_for_img(hwnd, team_flag, timeout=5):
            # 领取车队任务列表奖励
            self._loop_click_claim(hwnd, team_flag, max_clicks=10)
            
            # (如果有车队宝箱，可以在这里继续加 _scan_and_click_boxes)

        # 4. 流程结束，按 Backspace 返回大厅
        self.engine.key_press(hwnd, win32con.VK_BACK)
        time.sleep(2.0)

    # ------------------ 核心辅助方法 ------------------

    def _ensure_entry(self, hwnd, page_flag):
        """确保进入了任务页面，如果没进则点击进入"""
        if self._wait_for_img(hwnd, page_flag, timeout=1.5):
            return True # 已经在页面内
            
        # 尝试点击大厅入口
        img_name = self.imgs.get("entry_icon")
        if img_name:
            path = self.cfg_mgr.get_template_path(img_name)
            result = self.engine.match_template(hwnd, path, 0.8)
            if result and result[0]:
                _, _, (x, y) = result
                self.engine.click(hwnd, x, y)
                return self._wait_for_img(hwnd, page_flag, timeout=5)
        return False

    def _ensure_page_active(self, hwnd, page_flag):
        """
        页面守护器：检测是否因为误按空格退回了大厅。
        如果退回了，则尝试重新进入该页面。
        """
        if not self._wait_for_img(hwnd, page_flag, timeout=2):
            # 没找到页面标志，说明可能跳出去了
            self._ensure_entry(hwnd, page_flag)
            return False # 返回False让外层重新扫描当前页状态
        return True

    def _trigger_and_close_popup(self, hwnd, x, y, page_flag):
        """执行点击，等待弹窗，按下空格，并确保页面未丢失"""
        self.engine.click(hwnd, x, y)
        
        # 1. 等待掉落动画和弹窗完全展开（这里时间必须给足，防止过早按空格）
        time.sleep(0.5) 
        
        # 2. 按空格关闭弹窗
        self.engine.key_press(hwnd, win32con.VK_SPACE)
        
        # 3. 等待弹窗关闭动画完毕
        time.sleep(0.5) 
        
        # 4. 守护检查：看看是不是把整个任务菜单给关了
        self._ensure_page_active(hwnd, page_flag)

    def _wait_for_img(self, hwnd, img_name, timeout=5):
        """等待某个标志性图片出现"""
        if not img_name: return False
        path = self.cfg_mgr.get_template_path(img_name)
        
        for _ in range(int(timeout * 2)): # 步长0.5秒
            result = self.engine.match_template(hwnd, path, 0.8)
            if result and result[0]:
                return True
            time.sleep(0.5)
        return False

    # ------------------ 业务逻辑方法 ------------------

    def _loop_click_claim(self, hwnd, page_flag, max_clicks=15):
        """循环识别并点击黄色领取按钮（加入抗呼吸动画重试机制）"""
        img_name = self.imgs.get("claim_btn_yellow")
        if not img_name: return
        
        btn_path = self.cfg_mgr.get_template_path(img_name)
        # 【优化】建议将配置中的阈值稍微调低，默认给0.75，增加对特效的宽容度
        threshold = self.cfg.get("settings", {}).get("claim_threshold", 0.75) 
        
        clicked_count = 0
        while clicked_count < max_clicks:
            if not self._ensure_page_active(hwnd, page_flag):
                continue 

            # 【优化】加入重试机制：连续寻找3次，每次间隔0.3秒，对抗呼吸灯特效
            found_btn = False
            for _ in range(3):
                result = self.engine.match_template(hwnd, btn_path, threshold)
                if result and result[0]:
                    found_btn = True
                    _, _, (x, y) = result
                    break # 找到了就跳出寻找循环
                time.sleep(0.3) # 没找到，等0.3秒动画变化再找
                
            if not found_btn:
                break  # 连续3次都没找到，说明真没有了，结束整个领取循环
                
            # 执行点击和弹窗处理
            self._trigger_and_close_popup(hwnd, x, y, page_flag)
            clicked_count += 1
            # 【优化】多等0.5秒，确保上一个弹窗的“渐隐残影”完全消失
            time.sleep(0.5) 

    def _scan_and_click_boxes(self, hwnd, boxes_list, page_flag):
        """扫描并点击传入的宝箱列表（加入抗动画重试机制）"""
        if not boxes_list: return

        # 【优化】宝箱发光特效更夸张，阈值建议同样放宽到0.75
        threshold = self.cfg.get("settings", {}).get("box_threshold", 0.75)
        
        for box_img in boxes_list:
            if not self._ensure_page_active(hwnd, page_flag):
                continue
                
            path = self.cfg_mgr.get_template_path(box_img)
            
            # 【优化】同样给每个宝箱3次识别机会，防止刚好卡在不发光的帧
            for _ in range(3):
                result = self.engine.match_template(hwnd, path, threshold)
                if result and result[0]:
                    _, _, (x, y) = result
                    self._trigger_and_close_popup(hwnd, x, y, page_flag)
                    time.sleep(0.5) # 等待残影消失
                    break # 这个宝箱领过了，跳出重试，检查下一个宝箱
                time.sleep(0.3)
    def _click_team_tab(self, hwnd):
        """点击'车队任务'页签"""
        coord = self.cfg.get("coords", {}).get("team_tab", [46, 810])
        self.engine.click(hwnd, coord[0], coord[1])
        # 切换页签没有奖励弹窗，不需要按空格，等待页面刷新即可
        time.sleep(1.0)