#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Facebook自动化程序 - 启动器

解决打包后的 QtWebEngine 初始化问题：
1. 在导入任何模块之前设置 Qt 属性
2. 创建 QApplication
3. 然后才导入主程序模块

这样可以确保 Qt.AA_ShareOpenGLContexts 在正确的时机设置
"""

import sys
import os

# ============ 修复工作目录问题 ============
# 确保工作目录是程序所在目录，而不是启动时的目录
if getattr(sys, 'frozen', False):
    # 打包环境：获取exe所在目录
    application_path = os.path.dirname(sys.executable)
else:
    # 开发环境：获取脚本所在目录
    application_path = os.path.dirname(os.path.abspath(__file__))

# 切换到程序目录
os.chdir(application_path)
print(f"[Launcher] 工作目录: {os.getcwd()}")

print("=" * 60)
print("Facebook Marketing Pro - Starting...")
print("=" * 60)
print()

# ============ 第1步：设置 Qt 属性 ============
print("[Launcher] Step 1: Setting Qt attributes...")

from PyQt5.QtCore import Qt, QCoreApplication

# 必须在创建任何 Qt 对象之前设置
os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--disable-gpu --no-sandbox"

# 设置 QtWebEngine 进程路径（打包环境）
if getattr(sys, 'frozen', False):
    # 打包环境
    base_path = sys._MEIPASS
    qtwebengine_path = os.path.join(base_path, 'PyQt5', 'Qt5', 'bin')
    
    # 添加到 PATH
    os.environ['PATH'] = qtwebengine_path + os.pathsep + os.environ.get('PATH', '')
    
    # 设置 Qt 插件路径
    os.environ['QT_PLUGIN_PATH'] = os.path.join(base_path, 'PyQt5', 'Qt5', 'plugins')
    os.environ['QT_QPA_PLATFORM_PLUGIN_PATH'] = os.path.join(base_path, 'PyQt5', 'Qt5', 'plugins', 'platforms')
    
    # 设置 QtWebEngine 资源路径
    os.environ['QTWEBENGINEPROCESS_PATH'] = os.path.join(qtwebengine_path, 'QtWebEngineProcess.exe')
    
    print(f"[Launcher] QtWebEngine path: {qtwebengine_path}")
    print(f"[Launcher] QtWebEngineProcess: {os.environ['QTWEBENGINEPROCESS_PATH']}")
else:
    # 开发环境
    os.environ['QT_QPA_PLATFORM_PLUGIN_PATH'] = ''

QCoreApplication.setAttribute(Qt.AA_UseSoftwareOpenGL)
QCoreApplication.setAttribute(Qt.AA_ShareOpenGLContexts)

print("[Launcher] OK: Qt attributes set")
print()

# ============ 第2步：创建 QApplication ============
print("[Launcher] Step 2: Creating QApplication...")

from PyQt5.QtWidgets import QApplication

app = QApplication(sys.argv)

print("[Launcher] OK: QApplication created")
print()

# ============ 第3步：导入并运行主程序 ============
print("[Launcher] Step 3: Importing main module...")

try:
    # 现在才安全地导入主程序
    # 注意：不要使用 from facebook_dashboard import main
    # 因为这会执行 facebook_dashboard.py 中的所有顶层代码
    import facebook_dashboard
    
    print("[Launcher] OK: Main module imported")
    print()
    
    print("[Launcher] Step 4: Starting main program...")
    print("=" * 60)
    print()
    
    # 调用主程序的 main 函数
    # 注意：main 函数内部会再次创建 QApplication，
    # 但 QApplication.instance() 会返回已存在的实例
    sys.exit(facebook_dashboard.main())
    
except ImportError as e:
    print(f"[Launcher] ERROR: Import failed: {e}")
    print()
    print("Please ensure all dependencies are installed")
    import traceback
    traceback.print_exc()
    input("\nPress Enter to exit...")
    sys.exit(1)
    
except Exception as e:
    print(f"[Launcher] ERROR: Runtime error: {e}")
    print()
    import traceback
    traceback.print_exc()
    input("\nPress Enter to exit...")
    sys.exit(1)
