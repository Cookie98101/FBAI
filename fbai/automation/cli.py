"""
自动化命令行入口
通过 ScriptRunner 调用可热更新的 main.py

使用方式:
    # 列出所有可用任务
    python -m automation.cli --list
    
    # 列出所有浏览器
    python -m automation.cli --browsers
    
    # 执行单个任务
    python -m automation.cli --browser <ID> --task <任务名> [--params '{}']
    
    # 批量执行
    python -m automation.cli --browser <ID1> --browser <ID2> --task <任务名> --batch
    
    # 自动模式
    python -m automation.cli --auto
"""

import sys
import os
import json
import argparse

# 确保可以导入项目模块
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from automation.script_runner import ScriptRunner


def main():
    parser = argparse.ArgumentParser(description="自动化任务执行器")
    parser.add_argument("--list", "-l", action="store_true", help="列出所有可用任务")
    parser.add_argument("--browsers", "-b", action="store_true", help="列出所有浏览器")
    parser.add_argument("--browser", type=str, action="append", help="浏览器ID (可多次指定)")
    parser.add_argument("--task", "-t", type=str, help="任务名称")
    parser.add_argument("--params", "-p", type=str, default="{}", help="任务参数 (JSON格式)")
    parser.add_argument("--batch", action="store_true", help="批量执行模式")
    parser.add_argument("--auto", action="store_true", help="自动模式")
    
    args = parser.parse_args()
    
    # 创建脚本运行器
    runner = ScriptRunner()
    
    # 列出任务
    if args.list:
        print("\n可用任务列表:")
        print("-" * 40)
        tasks = runner.get_available_tasks()
        if tasks:
            for task in tasks:
                module = runner.scheduler.task_loader.load_task(task)
                if module and hasattr(module, 'TASK_INFO'):
                    info = module.TASK_INFO
                    print(f"  {task}")
                    print(f"    名称: {info.get('name', task)}")
                    print(f"    描述: {info.get('description', '无')}")
                    print()
                else:
                    print(f"  {task}")
        else:
            print("  没有找到任务脚本")
        return
    
    # 列出浏览器
    if args.browsers:
        print("\n检查比特浏览器连接...")
        if not runner.check_connection():
            print("无法连接到比特浏览器，请确保比特浏览器已启动")
            return
        
        print("\n浏览器列表:")
        print("-" * 60)
        browsers = runner.get_browser_list()
        if browsers:
            for b in browsers:
                status = "运行中" if b.get("pid") else "已关闭"
                print(f"  ID: {b.get('id')}")
                print(f"  名称: {b.get('name', '未命名')}")
                print(f"  状态: {status}")
                print()
        else:
            print("  没有找到浏览器窗口")
        return
    
    # 自动模式
    if args.auto:
        print("\n启动自动模式...")
        result = runner.run_auto()
        print_result(result)
        return
    
    # 执行任务
    if args.task:
        browser_ids = args.browser or []
        
        if not browser_ids:
            print("错误: 请指定浏览器ID (--browser)")
            return
        
        # 解析参数
        try:
            params = json.loads(args.params)
        except json.JSONDecodeError as e:
            print(f"错误: 参数JSON格式错误 - {e}")
            return
        
        if args.batch or len(browser_ids) > 1:
            # 批量模式
            print(f"\n批量执行任务: {args.task}")
            print(f"浏览器数量: {len(browser_ids)}")
            result = runner.run_batch(browser_ids, args.task, params)
        else:
            # 单个任务
            print(f"\n执行任务: {args.task}")
            print(f"浏览器: {browser_ids[0]}")
            result = runner.run_single(browser_ids[0], args.task, params)
        
        print_result(result)
        return
    
    # 没有指定操作
    parser.print_help()


def print_result(result):
    """打印执行结果"""
    print("\n" + "=" * 40)
    if result.get("success"):
        print(f"✓ 执行成功")
        if result.get("message"):
            print(f"  消息: {result['message']}")
    else:
        print(f"✗ 执行失败")
        if result.get("error"):
            print(f"  错误: {result['error']}")
    
    if result.get("data"):
        print(f"  数据: {result['data']}")
    
    if result.get("duration"):
        print(f"  耗时: {result['duration']:.1f}秒")


if __name__ == "__main__":
    main()
