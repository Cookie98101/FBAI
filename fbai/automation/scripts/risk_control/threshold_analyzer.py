"""
阈值分析器
基于历史数据自动计算安全操作阈值
"""

from typing import Dict, List, Optional
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from database.db import Database


class ThresholdAnalyzer:
    """阈值分析器"""
    
    def __init__(self):
        self.db = Database()
        # 时间窗口配置（小时）
        self.time_windows = {
            'daily': 24,
            'three_days': 72,
            'weekly': 168
        }
        # 阈值百分位配置
        self.safe_percentile = 50  # 50%的安全账号在此以下
        self.warning_percentile = 75  # 75%的安全账号在此以下
        self.danger_percentile = 90  # 90%的安全账号在此以下
    
    def analyze_all_thresholds(self):
        """分析所有操作类型的阈值"""
        print("🔍 开始分析阈值...")
        
        # 获取所有操作类型
        action_types = self._get_all_action_types()
        
        total_analyzed = 0
        
        for action_type in action_types:
            for window_name, hours in self.time_windows.items():
                result = self.analyze_threshold(action_type, window_name, hours)
                if result:
                    total_analyzed += 1
        
        print(f"✅ 阈值分析完成！共分析 {total_analyzed} 个阈值")
    
    def analyze_threshold(self, action_type: str, time_window: str, hours: int) -> Optional[Dict]:
        """
        分析单个阈值
        
        Args:
            action_type: 操作类型
            time_window: 时间窗口名称
            hours: 时间窗口小时数
        
        Returns:
            阈值分析结果
        """
        # 获取安全账号的操作数据
        safe_data = self._get_safe_account_data(action_type, hours)
        
        # 获取被封账号的操作数据
        banned_data = self._get_banned_account_data(action_type, hours)
        
        # 检查样本量
        if len(safe_data) < 10:
            return None
        
        # 计算阈值
        safe_threshold = int(self._calculate_percentile(safe_data, self.safe_percentile))
        warning_threshold = int(self._calculate_percentile(safe_data, self.warning_percentile))
        danger_threshold = int(self._calculate_percentile(safe_data, self.danger_percentile))
        
        # 计算封号阈值
        if banned_data:
            ban_threshold = int(sum(banned_data) / len(banned_data))
        else:
            ban_threshold = danger_threshold + 10
        
        # 保存到数据库
        self._save_threshold(
            action_type, time_window, 
            safe_threshold, warning_threshold, danger_threshold, ban_threshold,
            len(safe_data)
        )
        
        print(f"✅ {action_type} - {time_window}: "
              f"安全{safe_threshold} | 警告{warning_threshold} | 危险{danger_threshold} | 封号{ban_threshold}")
        
        return {
            'action_type': action_type,
            'time_window': time_window,
            'safe_threshold': safe_threshold,
            'warning_threshold': warning_threshold,
            'danger_threshold': danger_threshold,
            'ban_threshold': ban_threshold,
            'sample_size': len(safe_data)
        }
    
    def _get_all_action_types(self) -> List[str]:
        """获取所有操作类型"""
        conn = self.db.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT DISTINCT action_type FROM action_logs 
            WHERE action_type IS NOT NULL
        ''')
        
        results = cursor.fetchall()
        conn.close()
        
        return [row['action_type'] for row in results]
    
    def _get_safe_account_data(self, action_type: str, hours: int) -> List[int]:
        """获取安全账号的操作数据"""
        conn = self.db.get_connection()
        cursor = conn.cursor()
        
        # 获取未被封的账号在指定时间窗口内的操作次数
        cursor.execute('''
            SELECT browser_id, COUNT(*) as action_count
            FROM action_logs
            WHERE action_type = ?
            AND browser_id NOT IN (SELECT browser_id FROM ban_analysis)
            AND action_time >= datetime('now', '-30 days')
            GROUP BY browser_id, date(action_time)
            HAVING COUNT(*) > 0
        ''', (action_type,))
        
        results = cursor.fetchall()
        conn.close()
        
        return [row['action_count'] for row in results]
    
    def _get_banned_account_data(self, action_type: str, hours: int) -> List[int]:
        """获取被封账号的操作数据"""
        conn = self.db.get_connection()
        cursor = conn.cursor()
        
        # 获取被封账号在封号前指定时间窗口内的操作次数
        cursor.execute('''
            SELECT b.browser_id, COUNT(a.id) as action_count
            FROM ban_analysis b
            LEFT JOIN action_logs a ON b.browser_id = a.browser_id
            WHERE a.action_type = ?
            AND a.action_time >= datetime(b.ban_date, '-' || ? || ' hours')
            AND a.action_time < b.ban_date
            GROUP BY b.browser_id
        ''', (action_type, hours))
        
        results = cursor.fetchall()
        conn.close()
        
        return [row['action_count'] for row in results if row['action_count'] > 0]
    
    def _calculate_percentile(self, data: List[int], percentile: float) -> float:
        """计算百分位数"""
        if not data:
            return 0
        
        sorted_data = sorted(data)
        index = int(len(sorted_data) * percentile / 100)
        
        if index >= len(sorted_data):
            index = len(sorted_data) - 1
        
        return sorted_data[index]
    
    def _save_threshold(self, action_type: str, time_window: str,
                       safe: int, warning: int, danger: int, ban: int, sample_size: int):
        """保存阈值到数据库"""
        conn = self.db.get_connection()
        cursor = conn.cursor()
        
        try:
            # 检查是否已存在
            cursor.execute('''
                SELECT id FROM threshold_analysis
                WHERE action_type = ? AND time_window = ?
            ''', (action_type, time_window))
            
            existing = cursor.fetchone()
            
            if existing:
                # 更新
                cursor.execute('''
                    UPDATE threshold_analysis
                    SET safe_threshold = ?,
                        warning_threshold = ?,
                        danger_threshold = ?,
                        ban_threshold = ?,
                        sample_size = ?,
                        last_updated = CURRENT_TIMESTAMP
                    WHERE id = ?
                ''', (safe, warning, danger, ban, sample_size, existing['id']))
            else:
                # 插入
                cursor.execute('''
                    INSERT INTO threshold_analysis
                    (action_type, time_window, safe_threshold, warning_threshold,
                     danger_threshold, ban_threshold, sample_size)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (action_type, time_window, safe, warning, danger, ban, sample_size))
            
            conn.commit()
        except Exception as e:
            print(f"⚠️ 保存阈值失败: {e}")
            conn.rollback()
        finally:
            conn.close()
    
    def get_threshold(self, action_type: str, time_window: str = 'daily') -> Optional[Dict]:
        """
        获取阈值
        
        Args:
            action_type: 操作类型
            time_window: 时间窗口
        
        Returns:
            阈值信息
        """
        conn = self.db.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM threshold_analysis
            WHERE action_type = ? AND time_window = ?
        ''', (action_type, time_window))
        
        result = cursor.fetchone()
        conn.close()
        
        return dict(result) if result else None
    
    def check_action_safety(self, browser_id: str, action_type: str, 
                           time_window: str = 'daily') -> tuple:
        """
        检查操作安全性
        
        Args:
            browser_id: 浏览器ID
            action_type: 操作类型
            time_window: 时间窗口
        
        Returns:
            (安全等级, 剩余次数)
        """
        # 获取阈值
        threshold = self.get_threshold(action_type, time_window)
        
        if not threshold:
            return ('unknown', -1)
        
        # 获取当前操作次数
        hours = self.time_windows.get(time_window, 24)
        current_count = self._get_action_count(browser_id, action_type, hours)
        
        # 判断安全等级
        safe = threshold['safe_threshold']
        warning = threshold['warning_threshold']
        danger = threshold['danger_threshold']
        
        if current_count < safe:
            return ('safe', safe - current_count)
        elif current_count < warning:
            return ('warning', warning - current_count)
        elif current_count < danger:
            return ('danger', danger - current_count)
        else:
            return ('critical', 0)
    
    def _get_action_count(self, browser_id: str, action_type: str, hours: int) -> int:
        """获取指定时间内的操作次数"""
        conn = self.db.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT COUNT(*) as count FROM action_logs
            WHERE browser_id = ? AND action_type = ?
            AND action_time >= datetime('now', '-' || ? || ' hours')
        ''', (browser_id, action_type, hours))
        
        result = cursor.fetchone()
        conn.close()
        
        return result['count'] if result else 0


if __name__ == "__main__":
    # 测试阈值分析器
    analyzer = ThresholdAnalyzer()
    
    print("测试1：分析所有阈值")
    analyzer.analyze_all_thresholds()
    
    print("\n测试2：获取特定阈值")
    threshold = analyzer.get_threshold('点赞', 'daily')
    if threshold:
        print(f"点赞阈值（每日）:")
        print(f"  安全: {threshold['safe_threshold']}")
        print(f"  警告: {threshold['warning_threshold']}")
        print(f"  危险: {threshold['danger_threshold']}")
        print(f"  封号: {threshold['ban_threshold']}")
