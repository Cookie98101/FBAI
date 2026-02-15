"""
远程账号管理模块

功能：
1. 从远程服务器获取分配的账号
2. 与本地账号.txt配合使用
3. 优先使用本地账号，本地没有时使用远程账号

使用方法：
    from 远程账号管理 import 获取远程账号
    
    accounts = 获取远程账号()
    if accounts:
        print(f"获取到 {len(accounts)} 个远程账号")
"""

import os
import json
import requests
from typing import List, Optional
from pathlib import Path


# ==================== 配置 ====================

# 远程服务器地址
REMOTE_SERVER = "http://43.142.176.53:8805"  # 修改为你的服务器地址

# API端点
API_ENDPOINT = f"{REMOTE_SERVER}/auth_backend/api/admin.php"

# 本地配置文件
current_dir = Path(__file__).parent
脚本配置目录 = current_dir / "脚本配置"
远程配置文件 = 脚本配置目录 / "远程账号配置.json"


# ==================== 配置管理 ====================

def 读取远程配置() -> dict:
    """读取远程账号配置"""
    if not 远程配置文件.exists():
        return {
            "enabled": False,
            "server_url": REMOTE_SERVER,
            "username": "",
            "last_sync": None
        }
    
    try:
        with open(远程配置文件, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return {
            "enabled": False,
            "server_url": REMOTE_SERVER,
            "username": "",
            "last_sync": None
        }


def 保存远程配置(config: dict):
    """保存远程账号配置"""
    try:
        脚本配置目录.mkdir(parents=True, exist_ok=True)
        with open(远程配置文件, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"保存远程配置失败: {e}")


# ==================== 远程账号获取 ====================

def 获取远程账号(username: str = None) -> List[str]:
    """
    从远程服务器获取分配的账号
    
    Args:
        username: 用户名，如果不提供则从配置文件读取
    
    Returns:
        账号列表，格式：["c_user|密码|2FA|邮箱|cookie|token", ...]
    """
    config = 读取远程配置()
    
    # 检查是否启用远程账号
    if not config.get("enabled", False):
        print("[远程账号] 远程账号功能未启用")
        return []
    
    # 获取用户名
    if username is None:
        username = config.get("username", "")
    
    if not username:
        print("[远程账号] 未配置用户名")
        return []
    
    # 获取服务器地址
    server_url = config.get("server_url", REMOTE_SERVER)
    api_url = f"{server_url}/auth_backend/api/admin.php"
    
    try:
        print(f"[远程账号] 正在从服务器获取账号...")
        print(f"[远程账号] 服务器: {server_url}")
        print(f"[远程账号] 用户名: {username}")
        
        # 调用API
        response = requests.post(
            api_url,
            data={
                'action': 'get_user_accounts',
                'username': username
            },
            timeout=10
        )
        
        if response.status_code != 200:
            print(f"[远程账号] 服务器响应错误: HTTP {response.status_code}")
            return []
        
        result = response.json()
        
        if result.get('status') == 'success':
            accounts_data = result.get('data', [])
            accounts = [acc['account_line'] for acc in accounts_data]
            
            print(f"[远程账号] ✓ 成功获取 {len(accounts)} 个账号")
            
            # 更新最后同步时间
            from datetime import datetime
            config['last_sync'] = datetime.now().isoformat()
            保存远程配置(config)
            
            return accounts
        else:
            print(f"[远程账号] 获取失败: {result.get('message', '未知错误')}")
            return []
            
    except requests.exceptions.Timeout:
        print(f"[远程账号] 连接超时")
        return []
    except requests.exceptions.ConnectionError:
        print(f"[远程账号] 无法连接到服务器")
        return []
    except Exception as e:
        print(f"[远程账号] 获取账号异常: {e}")
        return []


def 测试远程连接(server_url: str = None, username: str = None) -> bool:
    """
    测试远程服务器连接
    
    Args:
        server_url: 服务器地址
        username: 用户名
    
    Returns:
        是否连接成功
    """
    if server_url is None:
        config = 读取远程配置()
        server_url = config.get("server_url", REMOTE_SERVER)
    
    if username is None:
        config = 读取远程配置()
        username = config.get("username", "")
    
    if not username:
        print("[测试] 未提供用户名")
        return False
    
    api_url = f"{server_url}/auth_backend/api/admin.php"
    
    try:
        print(f"[测试] 正在测试连接...")
        print(f"[测试] 服务器: {server_url}")
        print(f"[测试] 用户名: {username}")
        
        response = requests.post(
            api_url,
            data={
                'action': 'get_user_accounts',
                'username': username
            },
            timeout=5
        )
        
        if response.status_code == 200:
            result = response.json()
            if result.get('status') == 'success':
                print(f"[测试] ✓ 连接成功")
                return True
            else:
                print(f"[测试] ✗ API返回错误: {result.get('message')}")
                return False
        else:
            print(f"[测试] ✗ HTTP错误: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"[测试] ✗ 连接失败: {e}")
        return False


def 配置远程账号(server_url: str, username: str, enabled: bool = True):
    """
    配置远程账号功能
    
    Args:
        server_url: 服务器地址
        username: 用户名
        enabled: 是否启用
    """
    config = {
        "enabled": enabled,
        "server_url": server_url,
        "username": username,
        "last_sync": None
    }
    
    保存远程配置(config)
    print(f"[配置] 远程账号配置已保存")
    print(f"[配置] 服务器: {server_url}")
    print(f"[配置] 用户名: {username}")
    print(f"[配置] 状态: {'启用' if enabled else '禁用'}")


# ==================== 测试 ====================

def main():
    """测试远程账号功能"""
    print("=" * 60)
    print("远程账号管理测试")
    print("=" * 60)
    print()
    
    # 读取配置
    config = 读取远程配置()
    print("当前配置:")
    print(f"  启用状态: {config.get('enabled', False)}")
    print(f"  服务器: {config.get('server_url', 'N/A')}")
    print(f"  用户名: {config.get('username', 'N/A')}")
    print(f"  最后同步: {config.get('last_sync', 'N/A')}")
    print()
    
    if not config.get('enabled', False):
        print("远程账号功能未启用")
        print()
        print("要启用远程账号功能，请运行:")
        print("  from 远程账号管理 import 配置远程账号")
        print("  配置远程账号('http://your-server.com', 'your_username')")
        return
    
    # 测试连接
    print("测试服务器连接...")
    if 测试远程连接():
        print()
        print("获取远程账号...")
        accounts = 获取远程账号()
        
        if accounts:
            print()
            print(f"成功获取 {len(accounts)} 个账号:")
            for i, account in enumerate(accounts, 1):
                # 只显示c_user部分
                c_user = account.split('|')[0]
                print(f"  {i}. {c_user}")
        else:
            print("未获取到账号")
    
    print()
    print("=" * 60)


if __name__ == "__main__":
    main()
