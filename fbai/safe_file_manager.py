#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
安全文件管理器 - 解决并发访问和JSON损坏问题
"""

import json
import os
import time
import tempfile
import shutil
import threading
from datetime import datetime
from contextlib import contextmanager

class SafeFileManager:
    """安全文件管理器"""
    
    def __init__(self):
        self.locks = {}  # 文件锁字典
        self.lock_timeout = 30  # 锁超时时间（秒）
        
    def get_file_lock(self, file_path):
        """获取文件锁"""
        if file_path not in self.locks:
            self.locks[file_path] = threading.RLock()
        return self.locks[file_path]
    
    @contextmanager
    def safe_file_operation(self, file_path, operation='read'):
        """安全文件操作上下文管理器"""
        file_lock = self.get_file_lock(file_path)
        acquired = False
        
        try:
            # 尝试获取锁
            acquired = file_lock.acquire(timeout=self.lock_timeout)
            if not acquired:
                raise TimeoutError(f"无法获取文件锁: {file_path}")
            
            print(f"[文件锁] 获取锁成功: {file_path} ({operation})")
            yield
            
        except Exception as e:
            print(f"[文件锁] 操作异常: {file_path} - {e}")
            raise
        finally:
            if acquired:
                file_lock.release()
                print(f"[文件锁] 释放锁: {file_path}")
    
    def safe_read_json(self, file_path, default_data=None):
        """安全读取JSON文件"""
        if default_data is None:
            default_data = {}
            
        with self.safe_file_operation(file_path, 'read'):
            if not os.path.exists(file_path):
                print(f"[安全读取] 文件不存在，返回默认数据: {file_path}")
                return default_data
            
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                print(f"[安全读取] 成功读取: {file_path}")
                return data
            except json.JSONDecodeError as e:
                print(f"[安全读取] JSON格式错误: {file_path} - {e}")
                # 尝试从备份恢复
                backup_data = self.try_restore_from_backup(file_path)
                if backup_data is not None:
                    return backup_data
                return default_data
            except Exception as e:
                print(f"[安全读取] 读取失败: {file_path} - {e}")
                return default_data
    
    def safe_write_json(self, file_path, data):
        """安全写入JSON文件（原子操作）"""
        with self.safe_file_operation(file_path, 'write'):
            # 确保目录存在
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            
            # 创建备份
            self.create_backup(file_path)
            
            # 原子写入：先写临时文件，再重命名
            temp_file = None
            try:
                # 创建临时文件
                temp_dir = os.path.dirname(file_path)
                temp_file = tempfile.NamedTemporaryFile(
                    mode='w', 
                    encoding='utf-8', 
                    dir=temp_dir, 
                    delete=False,
                    suffix='.tmp'
                )
                
                # 写入数据到临时文件
                json.dump(data, temp_file, ensure_ascii=False, indent=2)
                temp_file.flush()
                os.fsync(temp_file.fileno())  # 强制写入磁盘
                temp_file.close()
                
                # 原子重命名（Windows上需要先删除目标文件）
                if os.path.exists(file_path):
                    os.remove(file_path)
                shutil.move(temp_file.name, file_path)
                
                print(f"[安全写入] 成功写入: {file_path}")
                return True
                
            except Exception as e:
                print(f"[安全写入] 写入失败: {file_path} - {e}")
                # 清理临时文件
                if temp_file and os.path.exists(temp_file.name):
                    try:
                        os.remove(temp_file.name)
                    except:
                        pass
                raise
    
    def create_backup(self, file_path):
        """创建文件备份"""
        if not os.path.exists(file_path):
            return
        
        try:
            backup_dir = os.path.join(os.path.dirname(file_path), 'backup')
            os.makedirs(backup_dir, exist_ok=True)
            
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = os.path.basename(file_path)
            backup_path = os.path.join(backup_dir, f"{timestamp}_{filename}")
            
            shutil.copy2(file_path, backup_path)
            print(f"[备份] 创建备份: {backup_path}")
            
            # 清理旧备份（保留最近10个）
            self.cleanup_old_backups(backup_dir, filename)
            
        except Exception as e:
            print(f"[备份] 备份失败: {file_path} - {e}")
    
    def cleanup_old_backups(self, backup_dir, filename):
        """清理旧备份文件"""
        try:
            # 获取相关备份文件
            backup_files = []
            for f in os.listdir(backup_dir):
                if f.endswith(filename):
                    backup_path = os.path.join(backup_dir, f)
                    backup_files.append((backup_path, os.path.getmtime(backup_path)))
            
            # 按时间排序，保留最新的10个
            backup_files.sort(key=lambda x: x[1], reverse=True)
            
            for backup_path, _ in backup_files[10:]:
                os.remove(backup_path)
                print(f"[清理] 删除旧备份: {backup_path}")
                
        except Exception as e:
            print(f"[清理] 清理备份失败: {e}")
    
    def try_restore_from_backup(self, file_path):
        """尝试从备份恢复数据"""
        try:
            backup_dir = os.path.join(os.path.dirname(file_path), 'backup')
            filename = os.path.basename(file_path)
            
            if not os.path.exists(backup_dir):
                return None
            
            # 找到最新的备份文件
            backup_files = []
            for f in os.listdir(backup_dir):
                if f.endswith(filename):
                    backup_path = os.path.join(backup_dir, f)
                    backup_files.append((backup_path, os.path.getmtime(backup_path)))
            
            if not backup_files:
                return None
            
            # 使用最新的备份
            backup_files.sort(key=lambda x: x[1], reverse=True)
            latest_backup = backup_files[0][0]
            
            with open(latest_backup, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            print(f"[恢复] 从备份恢复数据: {latest_backup}")
            return data
            
        except Exception as e:
            print(f"[恢复] 备份恢复失败: {e}")
            return None

# 全局文件管理器实例
file_manager = SafeFileManager()

def safe_read_json(file_path, default_data=None):
    """全局安全读取函数"""
    return file_manager.safe_read_json(file_path, default_data)

def safe_write_json(file_path, data):
    """全局安全写入函数"""
    return file_manager.safe_write_json(file_path, data)

# 测试函数
def test_concurrent_access():
    """测试并发访问"""
    import threading
    import random
    
    test_file = "test_concurrent.json"
    
    def worker(worker_id):
        """工作线程"""
        for i in range(10):
            try:
                # 读取数据
                data = safe_read_json(test_file, {})
                
                # 模拟处理时间
                time.sleep(random.uniform(0.01, 0.1))
                
                # 修改数据
                key = f"worker_{worker_id}"
                if key not in data:
                    data[key] = []
                data[key].append(f"operation_{i}")
                
                # 写入数据
                safe_write_json(test_file, data)
                
                print(f"Worker {worker_id} - Operation {i} completed")
                
            except Exception as e:
                print(f"Worker {worker_id} - Error: {e}")
    
    # 启动10个并发线程（模拟10台模拟器）
    threads = []
    for i in range(10):
        t = threading.Thread(target=worker, args=(i,))
        threads.append(t)
        t.start()
    
    # 等待所有线程完成
    for t in threads:
        t.join()
    
    # 验证结果
    final_data = safe_read_json(test_file, {})
    print(f"Final data keys: {list(final_data.keys())}")
    
    # 清理测试文件
    if os.path.exists(test_file):
        os.remove(test_file)

if __name__ == "__main__":
    print("测试并发文件访问...")
    test_concurrent_access()
    print("测试完成！")
