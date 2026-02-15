"""
热更新守护进程

功能：
1. 在后台独立运行，不影响主脚本
2. 定期检查服务器更新
3. 下载并替换文件
4. 通知主脚本重载模块

使用方法：
    在 main.py 启动时自动启动守护进程
"""

import os
import sys
import json
import time
import hashlib
import requests
import threading
import importlib
import py_compile
import shutil
from typing import Dict, List, Optional, Callable
from pathlib import Path


# ==================== 配置 ====================

# 更新服务器地址
UPDATE_SERVER = "http://43.142.176.53:8805/update_server"  # PHP 服务器地址

# 检查更新间隔（秒）
CHECK_INTERVAL = 300  # 5 分钟检查一次

# 本地脚本目录
SCRIPTS_DIR = Path(__file__).parent

# 版本文件
VERSION_FILE = SCRIPTS_DIR / "version.json"

# 更新配置 URL
UPDATE_CONFIG_URL = f"{UPDATE_SERVER}/api/version.php"


# ==================== 工具函数 ====================

def 计算文件哈希(file_path: Path) -> str:
    """计算文件的 MD5 哈希值"""
    if not file_path.exists():
        return ""
    
    md5 = hashlib.md5()
    with open(file_path, 'rb') as f:
        for chunk in iter(lambda: f.read(4096), b""):
            md5.update(chunk)
    return md5.hexdigest()


def 读取本地版本() -> Dict:
    """读取本地版本信息"""
    if not VERSION_FILE.exists():
        return {"version": "0.0.0", "files": {}}
    
    try:
        with open(VERSION_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return {"version": "0.0.0", "files": {}}


def 保存本地版本(version_data: Dict):
    """保存本地版本信息"""
    try:
        with open(VERSION_FILE, 'w', encoding='utf-8') as f:
            json.dump(version_data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[热更新] 保存版本信息失败: {e}")


def 获取服务器版本() -> Optional[Dict]:
    """从服务器获取最新版本信息"""
    try:
        response = requests.get(UPDATE_CONFIG_URL, timeout=10)
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        print(f"[热更新] 获取服务器版本失败: {e}")
    return None


def 下载文件(url: str, save_path: Path) -> bool:
    """下载文件"""
    try:
        response = requests.get(url, timeout=30)
        if response.status_code == 200:
            save_path.parent.mkdir(parents=True, exist_ok=True)
            with open(save_path, 'wb') as f:
                f.write(response.content)
            return True
    except Exception as e:
        print(f"[热更新] 下载失败 {url}: {e}")
    return False


def 下载并编译文件(url: str, save_path: Path) -> bool:
    """
    下载 .pyc 文件（不下载 .py 源文件，避免覆盖本地开发代码）
    
    Args:
        url: 下载地址（.py 文件的 URL，会自动转换为 .pyc）
        save_path: 保存路径（.py 文件路径，会自动转换为 .pyc）
    
    Returns:
        是否成功
    """
    try:
        save_path.parent.mkdir(parents=True, exist_ok=True)
        
        # 策略：只下载 .pyc 文件，不覆盖本地 .py 源文件
        if str(save_path).endswith('.py'):
            # 只下载 .pyc 文件
            pyc_url = url.replace('.py', '.pyc')
            pyc_path = Path(str(save_path).replace('.py', '.pyc'))
            
            print(f"[热更新] 下载 .pyc: {pyc_url}")
            try:
                response = requests.get(pyc_url, timeout=30)
                if response.status_code == 200:
                    # 成功下载 .pyc
                    with open(pyc_path, 'wb') as f:
                        f.write(response.content)
                    print(f"[热更新] ✓ 下载成功: {pyc_path}")
                    return True
                else:
                    print(f"[热更新] ✗ 下载失败: HTTP {response.status_code}")
                    return False
            except Exception as e:
                print(f"[热更新] ✗ 下载失败: {e}")
                return False
        
        # 非 .py 文件，直接下载
        print(f"[热更新] 下载: {url}")
        response = requests.get(url, timeout=30)
        if response.status_code != 200:
            print(f"[热更新] 下载失败 {url}: HTTP {response.status_code}")
            return False
        
        with open(save_path, 'wb') as f:
            f.write(response.content)
        
        print(f"[热更新] ✓ 下载成功: {save_path}")
        return True
        
    except Exception as e:
        print(f"[热更新] 下载失败 {url}: {e}")
        return False


# ==================== 热更新守护进程 ====================

class 热更新守护进程:
    """
    热更新守护进程
    
    在后台运行，定期检查更新并自动应用
    """
    
    def __init__(self, 
                 检查间隔: int = CHECK_INTERVAL,
                 日志回调: Optional[Callable] = None,
                 更新回调: Optional[Callable] = None):
        """
        Args:
            检查间隔: 检查更新的间隔（秒）
            日志回调: 日志输出回调函数
            更新回调: 更新完成后的回调函数（用于通知主脚本重载模块）
        """
        self.检查间隔 = 检查间隔
        self.日志回调 = 日志回调
        self.更新回调 = 更新回调
        self.运行中 = False
        self.线程 = None
        self.已更新文件: List[str] = []
    
    def log(self, msg: str):
        """输出日志"""
        timestamp = time.strftime("%H:%M:%S")
        log_msg = f"[{timestamp}] [热更新] {msg}"
        print(log_msg)
        
        if self.日志回调:
            try:
                self.日志回调(log_msg)
            except:
                pass
    
    def 检查更新(self) -> tuple[bool, List[Dict]]:
        """
        检查是否有更新
        
        Returns:
            (是否有更新, 需要更新的文件列表)
        """
        server_version = 获取服务器版本()
        if not server_version:
            return False, []
        
        local_version = 读取本地版本()
        
        server_ver = server_version.get("version", "0.0.0")
        local_ver = local_version.get("version", "0.0.0")
        
        # 比较文件哈希（即使版本号相同也要检查）
        # 这样可以检测到文件被修改或损坏的情况
        server_files = server_version.get("files", {})
        local_files = local_version.get("files", {})
        
        需要更新 = []
        
        for file_path, file_info in server_files.items():
            server_hash = file_info.get("hash", "")
            full_path = SCRIPTS_DIR / file_path
            actual_hash = 计算文件哈希(full_path)
            
            if server_hash != actual_hash:
                需要更新.append({
                    "path": file_path,
                    "url": file_info.get("url", f"{UPDATE_SERVER}/files/{file_path}"),
                    "hash": server_hash,
                    "size": file_info.get("size", 0)
                })
        
        return len(需要更新) > 0, 需要更新
    
    def 执行更新(self, files: List[Dict]) -> bool:
        """
        执行更新
        
        Args:
            files: 需要更新的文件列表
        
        Returns:
            是否全部更新成功
        """
        self.log(f"开始更新 {len(files)} 个文件...")
        
        成功数 = 0
        self.已更新文件 = []
        
        for file_info in files:
            file_path = file_info["path"]
            url = file_info["url"]
            expected_hash = file_info["hash"]
            
            full_path = SCRIPTS_DIR / file_path
            
            # 备份旧文件
            backup_path = Path(str(full_path) + ".backup")
            if full_path.exists():
                try:
                    shutil.copy2(full_path, backup_path)
                except:
                    pass
            
            # 下载并编译新文件
            if 下载并编译文件(url, full_path):
                # 验证哈希
                actual_hash = 计算文件哈希(full_path)
                if actual_hash == expected_hash:
                    self.log(f"✓ 更新成功: {file_path}")
                    成功数 += 1
                    self.已更新文件.append(file_path)
                    
                    # 删除备份
                    if backup_path.exists():
                        try:
                            backup_path.unlink()
                        except:
                            pass
                else:
                    self.log(f"✗ 哈希校验失败: {file_path}")
                    # 恢复备份
                    if backup_path.exists():
                        try:
                            shutil.copy2(backup_path, full_path)
                        except:
                            pass
            else:
                self.log(f"✗ 下载失败: {file_path}")
        
        # 更新本地版本信息
        if 成功数 > 0:
            server_version = 获取服务器版本()
            if server_version:
                保存本地版本(server_version)
        
        self.log(f"更新完成: 成功 {成功数}/{len(files)}")
        
        return 成功数 == len(files)
    
    def 运行循环(self):
        """守护进程主循环"""
        self.log("守护进程已启动")
        
        while self.运行中:
            try:
                # 检查更新
                has_update, files = self.检查更新()
                
                if has_update:
                    self.log(f"发现 {len(files)} 个文件需要更新")
                    
                    # 执行更新
                    if self.执行更新(files):
                        self.log("✓ 更新成功，通知主脚本重载模块")
                        
                        # 调用更新回调
                        if self.更新回调:
                            try:
                                self.更新回调(self.已更新文件)
                            except Exception as e:
                                self.log(f"更新回调失败: {e}")
                
            except Exception as e:
                self.log(f"检查更新异常: {e}")
            
            # 等待下次检查
            time.sleep(self.检查间隔)
        
        self.log("守护进程已停止")
    
    def 启动(self):
        """启动守护进程"""
        if self.运行中:
            self.log("守护进程已在运行中")
            return
        
        self.运行中 = True
        self.线程 = threading.Thread(target=self.运行循环, daemon=True)
        self.线程.start()
        self.log(f"守护进程已启动（每 {self.检查间隔} 秒检查一次）")
    
    def 停止(self):
        """停止守护进程"""
        self.运行中 = False
        self.log("正在停止守护进程...")


# ==================== 模块热重载管理器 ====================

class 模块热重载管理器:
    """
    模块热重载管理器
    
    负责重载已更新的 Python 模块
    """
    
    def __init__(self, 日志回调: Optional[Callable] = None):
        self.日志回调 = 日志回调
        self.已加载模块: Dict[str, object] = {}
    
    def log(self, msg: str):
        """输出日志"""
        print(f"[模块重载] {msg}")
        if self.日志回调:
            try:
                self.日志回调(f"[模块重载] {msg}")
            except:
                pass
    
    def 重载模块(self, 文件路径: str):
        """
        重载指定的 Python 模块
        
        Args:
            文件路径: 相对于 scripts 目录的文件路径（如 "tasks/阅读.py"）
        """
        try:
            # 转换文件路径为模块名
            # tasks/阅读.py -> tasks.阅读
            模块名 = 文件路径.replace("/", ".").replace("\\", ".").replace(".py", "")
            
            # 特殊处理 main.py
            if 文件路径 == "main.py":
                self.log("⚠️ main.py 已更新，需要重启脚本才能生效")
                return
            
            # 检查模块是否已加载
            if 模块名 in sys.modules:
                self.log(f"重载模块: {模块名}")
                importlib.reload(sys.modules[模块名])
                self.log(f"✓ 模块已重载: {模块名}")
            else:
                self.log(f"模块未加载，跳过: {模块名}")
                
        except Exception as e:
            self.log(f"✗ 重载失败 {文件路径}: {e}")
    
    def 批量重载(self, 文件列表: List[str]):
        """批量重载模块"""
        self.log(f"开始重载 {len(文件列表)} 个模块...")
        
        for 文件路径 in 文件列表:
            if 文件路径.endswith(".py"):
                self.重载模块(文件路径)
        
        self.log("模块重载完成")


# ==================== 全局实例 ====================

_守护进程实例: Optional[热更新守护进程] = None
_重载管理器实例: Optional[模块热重载管理器] = None


def 启动热更新守护进程(
    检查间隔: int = CHECK_INTERVAL,
    日志回调: Optional[Callable] = None,
    启动时检查: bool = True,
    main_py_更新回调: Optional[Callable] = None
) -> 热更新守护进程:
    """
    启动热更新守护进程（全局单例）
    
    Args:
        检查间隔: 检查更新的间隔（秒）
        日志回调: 日志输出回调函数
        启动时检查: 是否在启动时立即检查更新
        main_py_更新回调: main.py 更新后的回调函数（用于重启程序）
    
    Returns:
        守护进程实例
    """
    global _守护进程实例, _重载管理器实例
    
    if _守护进程实例 is not None:
        return _守护进程实例
    
    # 创建重载管理器
    _重载管理器实例 = 模块热重载管理器(日志回调)
    
    # 创建守护进程
    def 更新回调(文件列表: List[str]):
        """更新完成后重载模块或重启程序"""
        # 检查是否包含 main.py
        main_py_更新 = any("main.py" in f for f in 文件列表)
        
        if main_py_更新:
            # main.py 被更新，需要重启
            if main_py_更新回调:
                try:
                    main_py_更新回调()
                except Exception as e:
                    if _守护进程实例:
                        _守护进程实例.log(f"重启程序失败: {e}")
            else:
                if _守护进程实例:
                    _守护进程实例.log("⚠️ main.py 已更新，建议重启程序以应用更新")
        else:
            # 其他文件更新，热重载
            if _重载管理器实例:
                _重载管理器实例.批量重载(文件列表)
    
    _守护进程实例 = 热更新守护进程(
        检查间隔=检查间隔,
        日志回调=日志回调,
        更新回调=更新回调
    )
    
    # 启动时立即检查更新
    if 启动时检查:
        def 启动时检查更新():
            """在后台线程中检查更新，不阻塞主程序启动"""
            try:
                _守护进程实例.log("🔍 启动时检查更新...")
                has_update, files = _守护进程实例.检查更新()
                
                if has_update:
                    _守护进程实例.log(f"发现 {len(files)} 个文件需要更新")
                    
                    # 检查是否包含 main.py
                    main_py_更新 = any("main.py" in f.get("path", "") for f in files)
                    
                    if main_py_更新:
                        _守护进程实例.log("⚠️ 检测到 main.py 更新，将在更新后重启程序")
                    
                    if _守护进程实例.执行更新(files):
                        _守护进程实例.log("✓ 启动时更新成功")
                        # 调用更新回调
                        if _守护进程实例.更新回调:
                            try:
                                _守护进程实例.更新回调(_守护进程实例.已更新文件)
                            except Exception as e:
                                _守护进程实例.log(f"更新回调失败: {e}")
                else:
                    _守护进程实例.log("✓ 已是最新版本")
            except Exception as e:
                _守护进程实例.log(f"启动时检查更新失败: {e}")
        
        # 在后台线程中执行，不阻塞主程序
        threading.Thread(target=启动时检查更新, daemon=True).start()
    
    # 启动定期检查
    _守护进程实例.启动()
    
    return _守护进程实例


def 停止热更新守护进程():
    """停止热更新守护进程"""
    global _守护进程实例
    
    if _守护进程实例:
        _守护进程实例.停止()
        _守护进程实例 = None


# ==================== 测试 ====================

def main():
    """测试守护进程"""
    print("启动热更新守护进程测试...")
    
    守护进程 = 启动热更新守护进程(检查间隔=10)  # 10 秒检查一次
    
    try:
        # 保持运行
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n停止守护进程...")
        停止热更新守护进程()


if __name__ == "__main__":
    main()
