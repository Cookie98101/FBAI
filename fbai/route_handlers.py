"""
路由处理模块
实现各种路由的处理逻辑
"""

import subprocess
import sys
import os
import json
import platform
from datetime import datetime
from flask import request, jsonify
from route_manager import route_manager

def execute_desktop_program():
    """
    执行桌面端程序
    
    Returns:
        dict: 执行结果
    """
    try:
        # 获取请求数据
        data = request.get_json()
        program_path = data.get('program_path')
        arguments = data.get('arguments', [])
        
        if not program_path:
            return {
                "status": "error",
                "message": "未提供程序路径"
            }
        
        # 检查程序文件是否存在
        if not os.path.exists(program_path):
            return {
                "status": "error",
                "message": f"程序文件不存在: {program_path}"
            }
        
        # 构建命令
        cmd = [program_path] + arguments
        
        # 执行程序（非阻塞）
        subprocess.Popen(cmd, shell=True, 
                        creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0)
        
        return {
            "status": "success",
            "message": f"已启动程序: {program_path}",
            "program": program_path,
            "arguments": arguments,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"执行程序时出错: {str(e)}"
        }

def execute_backend_program():
    """
    通过后台服务执行程序
    
    Returns:
        dict: 执行结果
    """
    try:
        # 获取请求数据
        data = request.get_json()
        command = data.get('command')
        working_dir = data.get('working_dir', '.')
        
        if not command:
            return {
                "status": "error",
                "message": "未提供执行命令"
            }
        
        # 在后台执行命令
        result = subprocess.run(
            command,
            cwd=working_dir,
            shell=True,
            capture_output=True,
            text=True,
            timeout=30,  # 设置超时时间
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        )
        
        return {
            "status": "success",
            "message": "命令执行完成",
            "command": command,
            "return_code": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "timestamp": datetime.now().isoformat()
        }
    except subprocess.TimeoutExpired:
        return {
            "status": "error",
            "message": "命令执行超时"
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"执行命令时出错: {str(e)}"
        }

def get_available_routes():
    """
    获取所有可用路由
    
    Returns:
        dict: 路由列表
    """
    routes = route_manager.list_routes()
    return {
        "status": "success",
        "routes": routes,
        "count": len(routes),
        "timestamp": datetime.now().isoformat()
    }

def get_system_details():
    """
    获取详细的系统信息
    
    Returns:
        dict: 系统信息
    """
    try:
        return {
            "status": "success",
            "system_info": {
                "platform": platform.platform(),
                "system": platform.system(),
                "release": platform.release(),
                "version": platform.version(),
                "machine": platform.machine(),
                "processor": platform.processor(),
                "python_version": sys.version,
                "python_executable": sys.executable,
                "current_directory": os.getcwd(),
                "timestamp": datetime.now().isoformat()
            }
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"获取系统信息时出错: {str(e)}"
        }

# 路由注册装饰器
def register_routes(app):
    """
    注册所有路由处理函数
    
    Args:
        app (Flask): Flask应用实例
    """
    # 注册新增的路由处理函数
    app.add_url_rule(
        route_manager.get_endpoint('execute_desktop_program'),
        'execute_desktop_program',
        execute_desktop_program,
        methods=[route_manager.get_method('execute_desktop_program')]
    )
    
    app.add_url_rule(
        route_manager.get_endpoint('execute_backend_program'),
        'execute_backend_program',
        execute_backend_program,
        methods=[route_manager.get_method('execute_backend_program')]
    )
    
    app.add_url_rule(
        route_manager.get_endpoint('get_available_routes'),
        'get_available_routes',
        get_available_routes,
        methods=[route_manager.get_method('get_available_routes')]
    )
    
    # 注册系统信息路由（扩展版本）
    app.add_url_rule(
        '/get_system_details',
        'get_system_details',
        get_system_details,
        methods=['GET']
    )