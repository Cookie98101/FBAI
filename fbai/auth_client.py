#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import requests
import json
import time
import threading
import hashlib
import platform
import uuid
import os
import tempfile
from datetime import datetime

# ==================== 全局锁文件机制（防止重复创建UI）====================
# 使用文件锁而不是类变量，确保跨模块、跨进程都能正确工作
_AUTH_LOCK_FILE = os.path.join(tempfile.gettempdir(), "facebook_auth_dialog.lock")
_AUTH_COMPLETED = False  # 全局标志：认证是否已完成

def _is_auth_dialog_showing():
    """检查是否有认证对话框正在显示（使用文件锁）"""
    # 如果认证已完成，不再显示认证对话框
    global _AUTH_COMPLETED
    if _AUTH_COMPLETED:
        print("[AuthLock] ✓ 认证已完成，不再显示认证对话框")
        return True  # 返回 True 表示"已在显示"，阻止重复显示
    
    if not os.path.exists(_AUTH_LOCK_FILE):
        return False
    
    # 检查锁文件是否过期（缩短到10秒，更快清理僵尸锁）
    try:
        file_age = time.time() - os.path.getmtime(_AUTH_LOCK_FILE)
        if file_age > 10:  # 从60秒改为10秒
            print(f"[AuthLock] ⚠ 锁文件已过期（{file_age:.0f}秒），删除旧锁文件")
            os.remove(_AUTH_LOCK_FILE)
            return False
    except Exception as e:
        print(f"[AuthLock] ⚠ 检查锁文件时出错: {e}，删除锁文件")
        try:
            os.remove(_AUTH_LOCK_FILE)
        except:
            pass
        return False
    
    # 检查锁文件中的进程ID是否还在运行
    try:
        with open(_AUTH_LOCK_FILE, 'r') as f:
            content = f.read().strip()
            if not content:
                print(f"[AuthLock] ⚠ 锁文件为空，删除无效锁文件")
                os.remove(_AUTH_LOCK_FILE)
                return False
            pid = int(content)
        
        # 检查进程是否存在
        import psutil
        if psutil.pid_exists(pid):
            # 进一步检查：是否是同一个程序？
            try:
                process = psutil.Process(pid)
                process_name = process.name().lower()
                # 如果进程名包含 facebook 或 python，认为是有效的
                if 'facebook' in process_name or 'python' in process_name:
                    print(f"[AuthLock] ✓ 检测到有效进程 {pid} ({process_name}) 正在运行")
                    return True
                else:
                    print(f"[AuthLock] ⚠ 进程 {pid} ({process_name}) 不是认证进程，删除锁文件")
                    os.remove(_AUTH_LOCK_FILE)
                    return False
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                print(f"[AuthLock] ⚠ 无法访问进程 {pid}，删除锁文件")
                os.remove(_AUTH_LOCK_FILE)
                return False
        else:
            print(f"[AuthLock] ⚠ 进程 {pid} 已不存在，删除旧锁文件")
            os.remove(_AUTH_LOCK_FILE)
            return False
    except ValueError as e:
        print(f"[AuthLock] ⚠ 锁文件内容无效: {e}，删除锁文件")
        try:
            os.remove(_AUTH_LOCK_FILE)
        except:
            pass
        return False
    except Exception as e:
        print(f"[AuthLock] ⚠ 检查进程时出错: {e}，删除锁文件")
        try:
            os.remove(_AUTH_LOCK_FILE)
        except:
            pass
        return False

def _set_auth_dialog_showing(showing=True):
    """设置认证对话框显示状态（使用文件锁）"""
    if showing:
        try:
            # 创建锁文件
            with open(_AUTH_LOCK_FILE, 'w') as f:
                f.write(str(os.getpid()))
            print(f"[AuthLock] ✓ 创建锁文件: {_AUTH_LOCK_FILE}")
            return True
        except Exception as e:
            print(f"[AuthLock] ❌ 创建锁文件失败: {e}")
            return False
    else:
        try:
            # 删除锁文件
            if os.path.exists(_AUTH_LOCK_FILE):
                os.remove(_AUTH_LOCK_FILE)
                print(f"[AuthLock] ✓ 删除锁文件: {_AUTH_LOCK_FILE}")
            return True
        except Exception as e:
            print(f"[AuthLock] ❌ 删除锁文件失败: {e}")
            return False

# ==================== 认证客户端 ====================

class AuthClient:
    """用户认证客户端"""
    
    def __init__(self, server_url="http://localhost:8805"):
        self.server_url = server_url.rstrip('/')
        self.auth_token = None
        self.user_info = None
        self.device_id = self._generate_device_id()
        self.real_name = self._load_real_name()
        
    def _generate_device_id(self):
        """生成唯一设备ID"""
        import platform
        import hashlib
        
        # 使用计算机名+MAC地址生成唯一ID
        computer_name = platform.node()
        mac = ':'.join(['{:02x}'.format((uuid.getnode() >> elements) & 0xff)
                       for elements in range(0,2*6,2)][::-1])
        
        unique_string = f"{computer_name}-{mac}"
        return hashlib.md5(unique_string.encode()).hexdigest()
    
    def _load_real_name(self):
        """从配置文件加载真实姓名"""
        try:
            import json
            import os
            config_files = ['simulator_config.json', 'monitor_config.json']
            for config_file in config_files:
                if os.path.exists(config_file):
                    with open(config_file, 'r', encoding='utf-8') as f:
                        config = json.load(f)
                        real_name = config.get('username', '未设置')
                        if real_name and real_name.strip():
                            return real_name.strip()
            return '未设置'
        except Exception as e:
            print(f"[AUTH] 加载真实姓名失败: {e}")
            return '未设置'
    
    def login(self, username, password):
        """用户登录"""
        try:
            response = requests.post(
                f"{self.server_url}/auth_backend/api/auth.php",
                data={
                    'action': 'login',
                    'username': username,
                    'password': password,
                    'device_id': self.device_id
                },
                timeout=10
            )
            
            result = response.json()
            
            if result['status'] == 'success':
                self.auth_token = result['data']['token']
                self.user_info = result['data']
                return True, result['message']
            else:
                # 处理设备绑定错误，显示详细信息
                error_code = result.get('error_code', '')
                if error_code == 'DEVICE_BOUND':
                    error_data = result.get('data', {})
                    bound_device = error_data.get('bound_device_id', '未知')
                    current_device = error_data.get('current_device_id', '未知')
                    
                    error_msg = f"{result['message']}\n\n"
                    error_msg += f"📱 绑定设备: {bound_device}\n"
                    error_msg += f"💻 当前设备: {current_device}\n\n"
                    error_msg += "如需更换设备，请联系管理员解绑。"
                    return False, error_msg
                else:
                    return False, result['message']
                
        except Exception as e:
            return False, f"登录失败: {str(e)}"
    
    def verify_auth(self):
        """验证当前认证状态"""
        if not self.auth_token:
            return False, "未登录"
        
        try:
            response = requests.post(
                f"{self.server_url}/auth_backend/api/auth.php",
                data={
                    'action': 'verify',
                    'token': self.auth_token
                },
                timeout=10
            )
            
            result = response.json()
            
            if result['status'] == 'success':
                # 更新用户信息
                self.user_info.update(result['data'])
                return True, result['message']
            else:
                self.auth_token = None
                self.user_info = None
                return False, result['message']
                
        except Exception as e:
            return False, f"验证失败: {str(e)}"
    
    def logout(self):
        """用户登出"""
        if not self.auth_token:
            return True, "已登出"
        
        try:
            response = requests.post(
                f"{self.server_url}/auth_backend/api/auth.php",
                data={
                    'action': 'logout',
                    'token': self.auth_token
                },
                timeout=10
            )
            
            result = response.json()
            
            self.auth_token = None
            self.user_info = None
            
            return True, result.get('message', '登出成功')
            
        except Exception as e:
            self.auth_token = None
            self.user_info = None
            return True, f"登出完成: {str(e)}"
    
    def is_authenticated(self):
        """检查是否已认证"""
        return self.auth_token is not None
    
    def send_heartbeat(self):
        """
        发送心跳信号（简化版）
        
        用途：
        - 更新用户在线状态
        - 不参与认证验证
        - 失败不影响程序运行
        
        Returns:
            (bool, str): (是否成功, 消息)
        """
        if not self.auth_token:
            return False, "未登录"
        
        try:
            response = requests.post(
                f"{self.server_url}/auth_backend/api/auth.php",
                data={
                    'action': 'heartbeat',
                    'token': self.auth_token,
                    'real_name': self.real_name
                },
                timeout=5  # 短超时，避免阻塞
            )
            
            result = response.json()
            
            if result['status'] == 'success':
                return True, "心跳成功"
            else:
                # 心跳失败不影响程序运行，只记录日志
                return False, result.get('message', '心跳失败')
                
        except Exception as e:
            # 网络错误等异常不影响程序运行
            return False, f"心跳异常: {str(e)}"
    
    def get_user_info(self):
        """获取用户信息"""
        return self.user_info
    
    def get_device_id(self):
        """获取设备ID"""
        return self.device_id
    
    def check_time_limit(self):
        """检查时间限制（仅检查授权到期日期，不限制每日使用时长）"""
        if not self.user_info:
            return False, "未登录"
        
        # 检查授权是否过期
        expire_date = datetime.strptime(self.user_info['expire_date'], '%Y-%m-%d %H:%M:%S')
        if datetime.now() > expire_date:
            return False, "授权已过期"
        
        # 不再检查每日使用时长，允许24小时持续运行
        # 只要授权未过期，就可以一直使用
        
        return True, "授权有效"


class AuthDialog:
    """认证对话框 - 图形化界面（防重复创建版本 - 使用文件锁）"""
    
    def __init__(self, auth_client):
        self.auth_client = auth_client
        self.username = ""
        self.password = ""
    
    def show_login_dialog(self):
        """显示登录对话框（高级图形化版本）- 使用文件锁防重复创建"""
        import traceback
        print("[AuthDialog] ========== 开始显示登录对话框 ==========")
        print(f"[AuthDialog] 调用栈:")
        for line in traceback.format_stack()[:-1]:
            print(line.strip())
        print("[AuthDialog] ==========================================")
        
        # 防止重复显示 - 使用文件锁（跨模块、跨进程有效）
        if _is_auth_dialog_showing():
            print("[AuthDialog] ⚠ 认证对话框已在显示中（文件锁检测），忽略重复调用")
            return False
        
        try:
            print("[AuthDialog] 正在导入PyQt5模块...")
            from PyQt5.QtWidgets import QApplication, QDialog
            from auth_dialog_pro import ProAuthDialog
            print("[AuthDialog] ✓ PyQt5模块导入成功")
            
            # 检查是否已有QApplication实例
            app = QApplication.instance()
            if app is None:
                print("[AuthDialog] 创建新的QApplication实例...")
                app = QApplication([])
            else:
                print("[AuthDialog] ✓ 使用已存在的QApplication实例")
            
            # 设置显示标记（创建锁文件）
            if not _set_auth_dialog_showing(True):
                print("[AuthDialog] ❌ 无法创建锁文件，取消显示")
                return False
            
            print("[AuthDialog] ✓ 开始显示认证对话框")
            
            try:
                # 创建对话框实例
                print("[AuthDialog] 正在创建ProAuthDialog实例...")
                dialog = ProAuthDialog(self.auth_client)
                print("[AuthDialog] ✓ ProAuthDialog实例创建成功")
                
                print("[AuthDialog] 正在显示对话框（exec_）...")
                result = dialog.exec_()
                print(f"[AuthDialog] 对话框已关闭，结果: {result}")
                
                # 返回结果
                success = (result == QDialog.Accepted)
                print(f"[AuthDialog] 认证结果: {'成功' if success else '失败/取消'}")
                
                # 如果认证成功，设置全局标志，防止重复认证
                if success:
                    global _AUTH_COMPLETED
                    _AUTH_COMPLETED = True
                    print("[AuthDialog] ✓ 设置认证完成标志，防止重复认证")
                
                return success
                
            finally:
                # 无论如何都要清空锁文件（使用finally确保一定执行）
                _set_auth_dialog_showing(False)
                print("[AuthDialog] ✓ 锁文件已清理")
                print("[AuthDialog] ========== 登录对话框流程结束 ==========")
                
        except ImportError as e:
            # 如果没有PyQt5，回退到控制台版本
            print(f"[AuthDialog] ❌ PyQt5导入失败: {e}")
            _set_auth_dialog_showing(False)
            return self._show_console_login()
        except Exception as e:
            print(f"[AuthDialog] ❌ 图形界面启动失败: {e}")
            import traceback
            traceback.print_exc()
            _set_auth_dialog_showing(False)
            
            # 尝试使用简单版本的GUI
            try:
                from auth_dialog_gui import AuthLoginDialog
                app = QApplication.instance()
                if app is None:
                    app = QApplication([])
                dialog = AuthLoginDialog(self.auth_client)
                result = dialog.exec_()
                return result == QDialog.Accepted
            except:
                return self._show_console_login()
        except Exception as e:
            print(f"图形界面启动失败: {e}")
            # 尝试使用简单版本的GUI
            try:
                from auth_dialog_gui import AuthLoginDialog
                app = QApplication.instance()
                if app is None:
                    app = QApplication([])
                dialog = AuthLoginDialog(self.auth_client)
                result = dialog.exec_()
                return result == QDialog.Accepted
            except:
                return self._show_console_login()
    
    def _show_console_login(self):
        """控制台版本登录（备用）"""
        print("=" * 50)
        print("Facebook数据展示程序 - 用户认证")
        print("=" * 50)
        
        while True:
            self.username = input("请输入用户名: ").strip()
            if self.username:
                break
            print("用户名不能为空！")
        
        while True:
            self.password = input("请输入密码: ").strip()
            if self.password:
                break
            print("密码不能为空！")
        
        print(f"设备ID: {self.auth_client.get_device_id()}")
        print("正在登录...")
        
        success, message = self.auth_client.login(self.username, self.password)
        
        if success:
            print(f"✓ {message}")
            user_info = self.auth_client.get_user_info()
            print(f"欢迎, {user_info['username']}!")
            print(f"授权到期时间: {user_info['expire_date']}")
            print(f"最大设备数: {user_info['max_simulators']}")
            print(f"每日最大使用时长: {user_info['max_daily_hours']}小时")
            return True
        else:
            print(f"✗ {message}")
            return False


def test_auth_system():
    """测试认证系统"""
    print("测试认证系统...")
    
    # 创建认证客户端
    auth_client = AuthClient("http://localhost:8805")
    
    # 显示登录对话框
    auth_dialog = AuthDialog(auth_client)
    
    if auth_dialog.show_login_dialog():
        print("\n认证成功！程序可以正常运行。")
        
        # 模拟程序运行
        for i in range(5):
            time.sleep(2)
            
            # 定期验证认证状态
            success, message = auth_client.verify_auth()
            if not success:
                print(f"认证验证失败: {message}")
                break
            
            # 检查时间限制
            success, message = auth_client.check_time_limit()
            if not success:
                print(f"时间限制检查失败: {message}")
                break
            
            print(f"程序运行中... ({i+1}/5)")
        
        # 登出
        auth_client.logout()
        print("已登出")
    else:
        print("认证失败，程序退出。")


if __name__ == "__main__":
    test_auth_system()
