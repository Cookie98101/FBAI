"""
操作日志记录器
用于记录所有自动化操作的详细日志
"""

from datetime import datetime
from typing import Optional
import sys
import os

# 添加父目录到路径
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from database.db import Database


class ActionLogger:
    """操作日志记录器"""
    
    def __init__(self):
        self.db = Database()
        self.current_action = {}
    
    def log_action_start(self, browser_id: str, module_name: str, action_type: str, target: str = None):
        """
        记录操作开始
        
        Args:
            browser_id: 浏览器ID
            module_name: 模块名称（阅读模块、评论模块等）
            action_type: 操作类型（点赞、评论、转发等）
            target: 操作目标（帖子ID、用户ID等）
        """
        self.current_action[browser_id] = {
            'module_name': module_name,
            'action_type': action_type,
            'target': target,
            'start_time': datetime.now()
        }
    
    def log_action_end(self, browser_id: str, result: str = 'success', content: str = None):
        """
        记录操作结束
        
        Args:
            browser_id: 浏览器ID
            result: 操作结果（success/failed）
            content: 操作内容（评论内容等）
        """
        if browser_id not in self.current_action:
            return
        
        action_info = self.current_action[browser_id]
        end_time = datetime.now()
        duration = int((end_time - action_info['start_time']).total_seconds())
        
        # 计算距离上次操作的间隔
        interval = self._get_interval_from_last(browser_id)
        
        # 保存到数据库
        try:
            conn = self.db.get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO action_logs 
                (browser_id, action_time, module_name, action_type, target, duration, interval_from_last, result, content)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                browser_id,
                end_time.isoformat(),
                action_info['module_name'],
                action_info['action_type'],
                action_info.get('target'),
                duration,
                interval,
                result,
                content
            ))
            
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"⚠️ 记录操作日志失败: {e}")
        
        # 清除当前操作记录
        del self.current_action[browser_id]
    
    def _get_interval_from_last(self, browser_id: str) -> Optional[int]:
        """获取距离上次操作的间隔（秒）"""
        try:
            conn = self.db.get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT action_time FROM action_logs
                WHERE browser_id = ?
                ORDER BY action_time DESC
                LIMIT 1
            ''', (browser_id,))
            
            row = cursor.fetchone()
            conn.close()
            
            if row:
                last_time = datetime.fromisoformat(row['action_time'])
                now = datetime.now()
                return int((now - last_time).total_seconds())
        except:
            pass
        
        return None
    
    def get_action_count(self, browser_id: str, action_type: str = None, hours: int = 24) -> int:
        """
        获取指定时间内的操作次数
        
        Args:
            browser_id: 浏览器ID
            action_type: 操作类型（可选）
            hours: 时间范围（小时）
        
        Returns:
            操作次数
        """
        try:
            conn = self.db.get_connection()
            cursor = conn.cursor()
            
            if action_type:
                cursor.execute('''
                    SELECT COUNT(*) as count FROM action_logs 
                    WHERE browser_id = ? AND action_type = ? 
                    AND action_time >= datetime('now', ? || ' hours')
                ''', (browser_id, action_type, -hours))
            else:
                cursor.execute('''
                    SELECT COUNT(*) as count FROM action_logs 
                    WHERE browser_id = ? 
                    AND action_time >= datetime('now', ? || ' hours')
                ''', (browser_id, -hours))
            
            row = cursor.fetchone()
            conn.close()
            
            return row['count'] if row else 0
        except:
            return 0
