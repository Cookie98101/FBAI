"""
封号追踪器
用于记录和分析账号封禁事件
"""

from datetime import datetime
from typing import Optional
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from database.db import Database


class BanTracker:
    """封号追踪器"""
    
    def __init__(self):
        self.db = Database()
    
    def record_ban(self, browser_id: str, ban_type: str = 'permanent', account_create_date: str = None):
        """
        记录封号事件
        
        Args:
            browser_id: 浏览器ID
            ban_type: 封号类型（permanent/temporary/warning）
            account_create_date: 账号创建日期
        """
        try:
            conn = self.db.get_connection()
            cursor = conn.cursor()
            
            # 计算账号年龄
            account_age_days = None
            if account_create_date:
                try:
                    create_date = datetime.fromisoformat(account_create_date)
                    account_age_days = (datetime.now() - create_date).days
                except:
                    pass
            
            # 统计封号前的操作数
            cursor.execute('''
                SELECT COUNT(*) as total FROM action_logs WHERE browser_id = ?
            ''', (browser_id,))
            row = cursor.fetchone()
            total_actions = row['total'] if row else 0
            
            # 统计最近24小时操作数
            cursor.execute('''
                SELECT COUNT(*) as count FROM action_logs 
                WHERE browser_id = ? AND action_time >= datetime('now', '-24 hours')
            ''', (browser_id,))
            row = cursor.fetchone()
            actions_24h = row['count'] if row else 0
            
            # 统计最近72小时操作数
            cursor.execute('''
                SELECT COUNT(*) as count FROM action_logs 
                WHERE browser_id = ? AND action_time >= datetime('now', '-72 hours')
            ''', (browser_id,))
            row = cursor.fetchone()
            actions_72h = row['count'] if row else 0
            
            # 获取最后操作
            cursor.execute('''
                SELECT module_name, action_type FROM action_logs
                WHERE browser_id = ?
                ORDER BY action_time DESC
                LIMIT 1
            ''', (browser_id,))
            last_action = cursor.fetchone()
            
            # 计算封号延迟（距离最后操作的时间）
            ban_delay_hours = None
            if last_action:
                cursor.execute('''
                    SELECT action_time FROM action_logs
                    WHERE browser_id = ?
                    ORDER BY action_time DESC
                    LIMIT 1
                ''', (browser_id,))
                row = cursor.fetchone()
                if row:
                    try:
                        last_time = datetime.fromisoformat(row['action_time'])
                        ban_delay_hours = int((datetime.now() - last_time).total_seconds() / 3600)
                    except:
                        pass
            
            # 插入封号记录
            cursor.execute('''
                INSERT INTO ban_analysis 
                (browser_id, ban_date, ban_type, account_age_days, ban_delay_hours,
                 total_actions_before_ban, actions_last_24h, actions_last_72h, 
                 last_module, last_action)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                browser_id,
                datetime.now().isoformat(),
                ban_type,
                account_age_days,
                ban_delay_hours,
                total_actions,
                actions_24h,
                actions_72h,
                last_action['module_name'] if last_action else None,
                last_action['action_type'] if last_action else None
            ))
            
            conn.commit()
            conn.close()
            
            print(f"✓ 已记录封号事件：{browser_id} (类型: {ban_type})")
            print(f"  - 账号年龄: {account_age_days}天" if account_age_days else "")
            print(f"  - 封号前总操作: {total_actions}次")
            print(f"  - 最近24小时: {actions_24h}次")
            print(f"  - 最近72小时: {actions_72h}次")
            if ban_delay_hours is not None:
                print(f"  - 封号延迟: {ban_delay_hours}小时")
        except Exception as e:
            print(f"⚠️ 记录封号事件失败: {e}")
    
    def get_ban_statistics(self, days: int = 7) -> dict:
        """
        获取封号统计信息
        
        Args:
            days: 统计天数
        
        Returns:
            统计信息字典
        """
        try:
            conn = self.db.get_connection()
            cursor = conn.cursor()
            
            # 总封号数
            cursor.execute('''
                SELECT COUNT(*) as count FROM ban_analysis
                WHERE ban_date >= datetime('now', ? || ' days')
            ''', (-days,))
            total_bans = cursor.fetchone()['count']
            
            # 按类型统计
            cursor.execute('''
                SELECT ban_type, COUNT(*) as count FROM ban_analysis
                WHERE ban_date >= datetime('now', ? || ' days')
                GROUP BY ban_type
            ''', (-days,))
            by_type = {row['ban_type']: row['count'] for row in cursor.fetchall()}
            
            # 平均账号年龄
            cursor.execute('''
                SELECT AVG(account_age_days) as avg_age FROM ban_analysis
                WHERE ban_date >= datetime('now', ? || ' days')
                AND account_age_days IS NOT NULL
            ''', (-days,))
            row = cursor.fetchone()
            avg_age = row['avg_age'] if row and row['avg_age'] else 0
            
            # 平均封号延迟
            cursor.execute('''
                SELECT AVG(ban_delay_hours) as avg_delay FROM ban_analysis
                WHERE ban_date >= datetime('now', ? || ' days')
                AND ban_delay_hours IS NOT NULL
            ''', (-days,))
            row = cursor.fetchone()
            avg_delay = row['avg_delay'] if row and row['avg_delay'] else 0
            
            conn.close()
            
            return {
                'total_bans': total_bans,
                'by_type': by_type,
                'avg_account_age_days': round(avg_age, 1),
                'avg_ban_delay_hours': round(avg_delay, 1)
            }
        except Exception as e:
            print(f"⚠️ 获取封号统计失败: {e}")
            return {}
