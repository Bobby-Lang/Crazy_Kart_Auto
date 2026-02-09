# -*- coding: utf-8 -*-
"""
截图工具 - 用于制作特征图模板
支持对指定窗口进行截图，保存为1920x1080基准分辨率
"""

import sys
import os
import win32gui
import win32con
import argparse

# 添加项目路径
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

from app.core.game_engine import GameEngine
import cv2


def list_windows(keyword="疯狂赛车"):
    """列出所有包含关键词的窗口"""
    windows = []

    def callback(hwnd, _):
        if win32gui.IsWindowVisible(hwnd):
            title = win32gui.GetWindowText(hwnd)
            if keyword in title:
                rect = win32gui.GetWindowRect(hwnd)
                size = (rect[2] - rect[0], rect[3] - rect[1])
                windows.append({
                    'hwnd': hwnd,
                    'title': title,
                    'size': size,
                    'rect': rect
                })
        return True

    win32gui.EnumWindows(callback, None)
    return windows


def capture_window(hwnd, output_path, resize_to_base=True, region=None):
    """
    截取窗口画面

    参数:
        hwnd: 窗口句柄
        output_path: 输出文件路径
        resize_to_base: 是否resize到1920x1080基准
        region: 裁剪区域 [x, y, w, h]，None表示全屏
    """
    if not win32gui.IsWindow(hwnd):
        print(f"❌ 窗口句柄无效: {hwnd}")
        return False

    # 截图
    screenshot = GameEngine.grab_screen(hwnd, rescale_to_base=resize_to_base)

    if screenshot is None:
        print("❌ 截图失败")
        return False

    # 裁剪指定区域
    if region:
        x, y, w, h = region
        # 裁剪前确保坐标在范围内
        h_img, w_img = screenshot.shape[:2]
        x = max(0, min(x, w_img - 1))
        y = max(0, min(y, h_img - 1))
        w = min(w, w_img - x)
        h = min(h, h_img - y)
        screenshot = screenshot[y:y+h, x:x+w]

    # 保存
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    cv2.imwrite(output_path, screenshot)
    print(f"✅ 截图已保存: {output_path}")
    print(f"   分辨率: {screenshot.shape[1]}x{screenshot.shape[0]}")
    return True


def interactive_capture(keyword="疯狂赛车"):
    """交互式截图模式"""
    print(f"\n🔍 查找包含 '{keyword}' 的窗口...")

    windows = list_windows(keyword)
    if not windows:
        print("❌ 未找到匹配的窗口")
        return

    print(f"\n找到 {len(windows)} 个窗口:")
    for i, win in enumerate(windows):
        print(f"  {i+1}. {win['title']}")
        print(f"     句柄: {win['hwnd']}, 尺寸: {win['size'][0]}x{win['size'][1]}")

    if len(windows) == 1:
        selected = windows[0]
        print(f"\n使用唯一窗口: {selected['title']}")
    else:
        print("\n请选择窗口编号:")
        try:
            idx = int(input("> ")) - 1
            if 0 <= idx < len(windows):
                selected = windows[idx]
            else:
                print("无效选择")
                return
        except ValueError:
            print("无效输入")
            return

    hwnd = selected['hwnd']
    print(f"\n已选择窗口: {selected['title']}")

    # 获取窗口信息
    rect = win32gui.GetWindowRect(hwnd)
    client_rect = win32gui.GetClientRect(hwnd)
    print(f"窗口尺寸: {rect[2]-rect[0]}x{rect[3]-rect[1]}")
    print(f"客户区尺寸: {client_rect[0]}x{client_rect[1]}")

    while True:
        print("\n" + "="*50)
        print("选项:")
        print("  1. 截取全屏 (1920x1080基准)")
        print("  2. 截取全屏 (原始分辨率)")
        print("  3. 自定义区域截图")
        print("  4. 切换窗口")
        print("  q. 退出")
        print("="*50)

        choice = input("\n请选择: ").strip().lower()

        if choice == '1':
            output = input("输出文件名 (如: lobby_feature.png): ").strip()
            if not output.endswith('.png'):
                output += '.png'
            output_path = os.path.join(BASE_DIR, "app", "templates_1", output)
            capture_window(hwnd, output_path, resize_to_base=True)

        elif choice == '2':
            output = input("输出文件名 (如: lobby_feature.png): ").strip()
            if not output.endswith('.png'):
                output += '.png'
            output_path = os.path.join(BASE_DIR, "app", "templates_1", output)
            capture_window(hwnd, output_path, resize_to_base=False)

        elif choice == '3':
            print("\n输入裁剪区域 (基于1920x1080基准坐标):")
            try:
                x = int(input("  x: "))
                y = int(input("  y: "))
                w = int(input("  width: "))
                h = int(input("  height: "))
            except ValueError:
                print("无效输入")
                continue

            output = input("输出文件名: ").strip()
            if not output.endswith('.png'):
                output += '.png'
            output_path = os.path.join(BASE_DIR, "app", "templates_1", output)
            capture_window(hwnd, output_path, resize_to_base=True, region=[x, y, w, h])

        elif choice == '4':
            interactive_capture(keyword)
            return

        elif choice == 'q':
            break


def batch_capture(hwnd, output_dir, count=10, interval=1.0):
    """批量截图（用于录制操作过程）"""
    import time

    os.makedirs(output_dir, exist_ok=True)
    print(f"\n开始批量截图: {count} 张, 间隔 {interval}秒")

    for i in range(count):
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        output_path = os.path.join(output_dir, f"capture_{i:03d}_{timestamp}.png")
        capture_window(hwnd, output_path, resize_to_base=True)
        time.sleep(interval)

    print(f"\n✅ 批量截图完成: {output_dir}")


def capture_all_windows(keyword="疯狂赛车", output_dir=None):
    """截取所有匹配窗口的完整画面"""
    if output_dir is None:
        output_dir = os.path.join(BASE_DIR, "debug_screens")

    windows = list_windows(keyword)
    if not windows:
        print("❌ 未找到匹配的窗口")
        return

    print(f"\n截取 {len(windows)} 个窗口...")
    for i, win in enumerate(windows):
        hwnd = win['hwnd']
        safe_title = "".join(c for c in win['title'] if c.isalnum() or c in (' ', '-', '_'))
        output_path = os.path.join(output_dir, f"win_{i}_{safe_title[:20]}.png")
        capture_window(hwnd, output_path, resize_to_base=True)
        print(f"  [{i+1}/{len(windows)}] {win['title']}")

    print(f"\n✅ 所有窗口截图完成: {output_dir}")


def test_template_matching(hwnd, template_path):
    """测试模板匹配效果"""
    if not os.path.exists(template_path):
        print(f"❌ 模板文件不存在: {template_path}")
        return

    # 截图
    screenshot = GameEngine.grab_screen(hwnd, rescale_to_base=True)
    if screenshot is None:
        print("❌ 截图失败")
        return

    # 加载模板
    template = cv2.imread(template_path)
    if template is None:
        print("❌ 模板加载失败")
        return

    # 匹配
    res = cv2.matchTemplate(screenshot, template, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, max_loc = cv2.minMaxLoc(res)

    print(f"\n📊 模板匹配测试: {os.path.basename(template_path)}")
    print(f"   最高匹配度: {max_val:.4f}")
    print(f"   位置: {max_loc}")

    # 保存标记后的截图
    h, w = template.shape[:2]
    result = screenshot.copy()
    cv2.rectangle(result, max_loc, (max_loc[0] + w, max_loc[1] + h), (0, 255, 0), 2)
    cv2.putText(result, f"Match: {max_val:.3f}", (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)

    output_path = os.path.join(BASE_DIR, "debug_screens", "match_test.png")
    cv2.imwrite(output_path, result)
    print(f"   匹配结果已保存: {output_path}")


def main():
    parser = argparse.ArgumentParser(description="截图工具 - 用于制作特征图模板")
    parser.add_argument('-l', '--list', action='store_true', help='列出所有窗口')
    parser.add_argument('-k', '--keyword', default='疯狂赛车', help='窗口标题关键词')
    parser.add_argument('-c', '--capture', metavar='HWND', help='截取指定窗口 (输入窗口句柄或索引)')
    parser.add_argument('-o', '--output', metavar='PATH', help='输出文件路径')
    parser.add_argument('-r', '--region', nargs=4, metavar=('X', 'Y', 'W', 'H'),
                        type=int, help='裁剪区域 (x y w h)')
    parser.add_argument('-b', '--batch', metavar='COUNT', type=int,
                        help='批量截图数量')
    parser.add_argument('-t', '--test', metavar='TEMPLATE', help='测试模板匹配')
    parser.add_argument('--all', action='store_true', help='截取所有匹配窗口')
    parser.add_argument('-i', '--interactive', action='store_true', help='交互模式')

    args = parser.parse_args()

    if args.list:
        windows = list_windows(args.keyword)
        if windows:
            print(f"\n找到 {len(windows)} 个窗口:")
            for i, win in enumerate(windows):
                print(f"  [{i}] {win['title']} - {win['hwnd']} - {win['size']}")
        else:
            print("未找到匹配的窗口")

    elif args.interactive:
        interactive_capture(args.keyword)

    elif args.all:
        capture_all_windows(args.keyword)

    elif args.capture:
        try:
            # 尝试解析为索引或句柄
            if args.capture.isdigit():
                idx = int(args.capture)
                windows = list_windows(args.keyword)
                if 0 <= idx < len(windows):
                    hwnd = windows[idx]['hwnd']
                else:
                    print(f"索引超出范围: {idx}")
                    return
            else:
                hwnd = int(args.capture, 16)
        except ValueError:
            hwnd = int(args.capture)

        if args.output:
            output_path = args.output
        else:
            timestamp = "".join(str(x) for x in time.localtime()[:6])
            output_path = os.path.join(BASE_DIR, "app", "templates_1", f"capture_{timestamp}.png")

        region = None
        if args.region:
            region = args.region

        capture_window(hwnd, output_path, resize_to_base=True, region=region)

    elif args.batch:
        windows = list_windows(args.keyword)
        if not windows:
            print("未找到匹配的窗口")
            return
        hwnd = windows[0]['hwnd']
        output_dir = os.path.join(BASE_DIR, "debug_screens", "batch")
        batch_capture(hwnd, output_dir, count=args.batch)

    elif args.test:
        windows = list_windows(args.keyword)
        if windows:
            hwnd = windows[0]['hwnd']
            test_template_matching(hwnd, args.test)
        else:
            print("未找到匹配的窗口")

    else:
        parser.print_help()


if __name__ == "__main__":
    import time
    main()
