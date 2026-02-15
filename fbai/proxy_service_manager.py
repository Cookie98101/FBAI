#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
IP代理管理服务管理器
负责启动、停止和管理IP代理管理服务（Flask应用）
修复：在打包环境下使用线程而不是子进程启动，避免无限重启循环
"""

import subprocess
import os
import sys
import time
import requests
import threading
from typing import Optional

class ProxyServiceManager:
    """IP代理管理服务管理器"""
    
    def __init__(self, host='127.0.0.1', port=5000):
        self.host = host
        self.port = port
        self.process: Optional[subprocess.Popen] = None
        self.thread: Optional[threading.Thread] = None
        self.service_url = f"http://{host}:{port}"
        self._monitor_thread = None
        self._should_monitor = False
        self._server_running = False
        
    def is_running(self) -> bool:
        """检查服务是否正在运行（快速检查，避免阻塞）"""
        # 如果是线程模式，先检查标志位
        if getattr(sys, 'frozen', False) and self.thread and not self._server_running:
             return False

        try:
            response = requests.get(
                f"{self.service_url}/api/proxies",
                timeout=1  # 减少超时时间到1秒
            )
            return response.status_code == 200
        except:
            return False
    
    def start(self) -> bool:
        """启动IP代理管理服务"""
        if self.is_running():
            print(f"✓ IP代理管理服务已在运行: {self.service_url}")
            return True
        
        print(f"正在启动IP代理管理服务...")
        
        # 检查是否在打包环境中
        if getattr(sys, 'frozen', False):
            return self._start_in_thread()
        else:
            return self._start_subprocess()

    def _start_in_thread(self) -> bool:
        """在线程中启动服务（打包环境）"""
        try:
            # 1. 确定服务目录路径
            base_dir = os.path.dirname(sys.executable)
            
            # 尝试多个可能的路径
            possible_paths = [
                os.path.join(base_dir, 'ip_proxy_manager_v3_fixed', 'ip_proxy_manager_v3_fixed'),
                os.path.join(base_dir, '_internal', 'ip_proxy_manager_v3_fixed', 'ip_proxy_manager_v3_fixed'),
                # 开发环境下的路径（作为后备）
                os.path.join(os.path.dirname(os.path.abspath(__file__)), 'ip_proxy_manager_v3_fixed', 'ip_proxy_manager_v3_fixed')
            ]
            
            app_dir = None
            for path in possible_paths:
                if os.path.exists(path) and os.path.exists(os.path.join(path, 'app.py')):
                    app_dir = path
                    break
            
            if not app_dir:
                print(f"✗ 找不到服务目录，尝试路径: {possible_paths}")
                return False

            print(f"[ProxyService] 服务目录: {app_dir}")
            
            # 2. 添加到 sys.path
            if app_dir not in sys.path:
                sys.path.insert(0, app_dir)
            
            # 3. 导入 app
            try:
                # 尝试导入 waitress
                from waitress import serve
                has_waitress = True
            except ImportError:
                has_waitress = False
                print("[ProxyService] Waitress未安装，将使用Flask内置服务器")
            
            # 动态导入 app 模块
            import importlib
            if 'app' in sys.modules:
                # 如果之前导入过，需要 reload
                app_module = importlib.reload(sys.modules['app'])
            else:
                import app as app_module
                
            self.flask_app = app_module.app
            
            # 4. 启动线程
            def run_server():
                print(f"[ProxyService] 线程启动，监听 {self.host}:{self.port}")
                self._server_running = True
                try:
                    # 确保在服务目录中运行，以便找到数据库等文件
                    # 注意：os.chdir 可能会影响主程序，但 models.py 使用 __file__ 定位，应该没问题
                    # 这里为了安全起见，暂时不切换目录，依赖 __file__ 定位
                    
                    if has_waitress:
                         serve(self.flask_app, host=self.host, port=self.port, threads=4, _quiet=True)
                    else:
                         self.flask_app.run(host=self.host, port=self.port, debug=False, use_reloader=False)
                except Exception as e:
                    print(f"[ProxyService] 服务线程异常: {e}")
                finally:
                    self._server_running = False
                    print("[ProxyService] 服务线程结束")

            self.thread = threading.Thread(target=run_server, daemon=True)
            self.thread.start()
            
            # 5. 等待启动
            for i in range(10):
                time.sleep(1)
                if self.is_running():
                    print(f"✓ IP代理管理服务启动成功 (Thread): {self.service_url}")
                    return True
            
            print(f"✗ 服务启动超时 (Thread)")
            # 即使检测超时，线程可能还在尝试启动，暂时返回 False
            return False
            
        except Exception as e:
            print(f"✗ 启动服务失败 (Thread): {e}")
            import traceback
            traceback.print_exc()
            return False

    def _start_subprocess(self) -> bool:
        """在子进程中启动服务（开发环境）"""
        try:
            # 获取app.py的路径
            app_dir = os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                'ip_proxy_manager_v3_fixed',
                'ip_proxy_manager_v3_fixed'
            )
            app_file = os.path.join(app_dir, 'app.py')
            
            if not os.path.exists(app_file):
                print(f"✗ 找不到服务文件: {app_file}")
                return False
            
            # 启动Flask应用
            startupinfo = None
            if sys.platform == 'win32':
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = subprocess.SW_HIDE
            
            self.process = subprocess.Popen(
                [sys.executable, app_file],
                cwd=app_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                startupinfo=startupinfo,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
            )
            
            # 等待服务启动
            for i in range(10):
                time.sleep(1)
                if self.is_running():
                    print(f"✓ IP代理管理服务启动成功: {self.service_url}")
                    self._should_monitor = True
                    self._monitor_thread = threading.Thread(target=self._monitor_service, daemon=True)
                    self._monitor_thread.start()
                    return True
                
                if self.process.poll() is not None:
                    stdout, stderr = self.process.communicate()
                    error_msg = stderr.decode('utf-8', errors='ignore')
                    print(f"✗ 服务启动失败: {error_msg[:200]}")
                    return False
            
            print(f"✗ 服务启动超时")
            return False
            
        except Exception as e:
            print(f"✗ 启动服务失败: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def _monitor_service(self):
        """监控服务状态，如果崩溃则自动重启"""
        while self._should_monitor:
            time.sleep(5)
            if not self.is_running():
                print("⚠ IP代理管理服务已停止，尝试重启...")
                if self.start():
                    print("✓ 服务重启成功")
                else:
                    print("✗ 服务重启失败")
                    break
    
    def stop(self):
        """停止IP代理管理服务"""
        self._should_monitor = False
        
        # 停止线程模式
        if self.thread and self.thread.is_alive():
            # 线程模式下无法强制停止，只能不再引用
            self.thread = None
            
        # 停止子进程模式
        if self.process:
            try:
                print("[ProxyService] 正在停止服务进程...")
                self.process.terminate()
                try:
                    self.process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    self.process.kill()
                self.process = None
                print("[ProxyService] ✓ 服务已停止")
            except Exception as e:
                print(f"[ProxyService] 停止服务时出错: {e}")

    def restart(self) -> bool:
        """重启服务"""
        self.stop()
        time.sleep(1)
        return self.start()

    def get_status(self) -> dict:
        """获取服务状态"""
        running = self.is_running()
        status = {
            'running': running,
            'url': self.service_url,
            'host': self.host,
            'port': self.port
        }
        if running:
            try:
                response = requests.get(f"{self.service_url}/api/proxies", timeout=1)
                if response.status_code == 200:
                    data = response.json()
                    if data.get('success'):
                        proxies = data.get('data', [])
                        status['proxy_count'] = len(proxies)
                        status['active_count'] = sum(1 for p in proxies if p.get('status') == 'active')
            except:
                pass
        return status

# 全局单例
_service_manager = None

def get_service_manager() -> ProxyServiceManager:
    global _service_manager
    if _service_manager is None:
        _service_manager = ProxyServiceManager()
    return _service_manager
