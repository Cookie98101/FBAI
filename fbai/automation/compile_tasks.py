"""
任务脚本编译工具
将 tasks 目录下的 .py 文件编译成 .pyc 字节码文件

使用方式:
    python -m automation.compile_tasks
    
    # 编译后删除源文件
    python -m automation.compile_tasks --delete-source
    
    # 指定输出目录
    python -m automation.compile_tasks --output dist/tasks
"""

import os
import sys
import py_compile
import compileall
import shutil
import argparse
from pathlib import Path


def compile_single_file(source_path: str, output_path: str = None) -> bool:
    """
    编译单个 .py 文件为 .pyc
    """
    try:
        if output_path is None:
            output_path = source_path + 'c'  # .py -> .pyc
        
        # 使用 py_compile 编译
        py_compile.compile(source_path, cfile=output_path, doraise=True)
        print(f"  ✓ 编译成功: {os.path.basename(source_path)} -> {os.path.basename(output_path)}")
        return True
    except py_compile.PyCompileError as e:
        print(f"  ✗ 编译失败: {source_path}")
        print(f"    错误: {e}")
        return False


def compile_tasks_directory(tasks_dir: str, output_dir: str = None, delete_source: bool = False):
    """
    编译整个 tasks 目录
    """
    tasks_path = Path(tasks_dir)
    
    if not tasks_path.exists():
        print(f"错误: 目录不存在 - {tasks_dir}")
        return
    
    if output_dir:
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
    else:
        output_path = tasks_path
    
    print(f"\n编译任务脚本")
    print(f"源目录: {tasks_path}")
    print(f"输出目录: {output_path}")
    print("-" * 40)
    
    success_count = 0
    fail_count = 0
    
    for py_file in tasks_path.glob("*.py"):
        if py_file.name.startswith("_"):
            continue
        
        # 输出文件路径
        pyc_file = output_path / (py_file.stem + ".pyc")
        
        if compile_single_file(str(py_file), str(pyc_file)):
            success_count += 1
            
            # 删除源文件
            if delete_source and output_path == tasks_path:
                py_file.unlink()
                print(f"    已删除源文件: {py_file.name}")
        else:
            fail_count += 1
    
    print("-" * 40)
    print(f"编译完成: 成功 {success_count}, 失败 {fail_count}")
    
    if delete_source:
        print("\n⚠️  源文件已删除，请确保已备份！")


def main():
    parser = argparse.ArgumentParser(description="编译任务脚本为字节码")
    parser.add_argument("--tasks-dir", "-t", type=str, default=None,
                        help="任务脚本目录 (默认: automation/tasks)")
    parser.add_argument("--output", "-o", type=str, default=None,
                        help="输出目录 (默认: 同源目录)")
    parser.add_argument("--delete-source", "-d", action="store_true",
                        help="编译后删除源文件")
    
    args = parser.parse_args()
    
    # 默认任务目录
    if args.tasks_dir is None:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        args.tasks_dir = os.path.join(base_dir, "tasks")
    
    compile_tasks_directory(args.tasks_dir, args.output, args.delete_source)


if __name__ == "__main__":
    main()
