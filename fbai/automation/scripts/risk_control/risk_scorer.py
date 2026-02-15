"""
风险评分器
多维度评估账号风险等级
"""

from typing import Dict, Optional
from datetime import datetime
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from database.db import Database


class RiskScorer:
    """风险评分器"""
    
    def __init__(self):
        self.db = Database()
        # 权重配置
        self.weights = {
            'age': 0.15,      # 账号年龄 15%
            'frequency': 0.30,  # 操作频率 30%
            'pattern': 0.25,    # 行为模式 25%
            'content': 0.20,    # 内容质量 20%
            'ip': 0.10         # IP风险 10%
        }
    
    def calculate_all_scores(self):
        """计算所有活跃账号的风险分数"""
        print("🔍 开始计算风险分数...")
        
        accounts = self._get_active_accounts()
        calculated_count = 0
        
        for browser_id in accounts:
            result = self.calculate_risk_score(browser_id)
            if result:
                calculated_count += 1
        
        print(f"✅ 风险分数计算完成！共计算 {calculated_count} 个账号")
    
    def calculate_risk_score(self, browser_id: str) -> Optional[Dict]:
        """
        计算单个账号的风险分数
        
        Args:
            browser_id: 浏览器ID
        
        Returns:
            风险评分结果
        """
        # 1. 账号年龄分数
        age_score = self._calculate_age_score(browser_id)
        
        # 2. 操作频率分数
        frequency_score = self._calculate_frequency_score(browser_id)
        
        # 3. 行为模式分数
        pattern_score = self._calculate_pattern_score(browser_id)
        
        # 4. 内容质量分数
        content_score = self._calculate_content_score(browser_id)
        
        # 5. IP风险分数
        ip_score = self._calculate_ip_score(browser_id)
        
        # 计算总分
        total_score = int(
            age_score * self.weights['age'] +
            frequency_score * self.weights['frequency'] +
            pattern_score * self.weights['pattern'] +
            content_score * self.weights['content'] +
            ip_score * self.weights['ip']
        )
        
        # 判断风险等级
        risk_level = self._get_risk_level(total_score)
        
        # 保存到数据库
        self._save_score(browser_id, total_score, age_score, frequency_score,
                        pattern_score, content_score, ip_score, risk_level)
        
        result = {
            'browser_id': browser_id,
            'total_score': total_score,
            'age_score': age_score,
            'frequency_score': frequency_score,
            'pattern_score': pattern_score,
            'content_score': content_score,
            'ip_score': ip_score,
            'risk_level': risk_level
        }
        
        print(f"✅ {browser_id}: 总分 {total_score} ({risk_level}) - "
              f"年龄{age_score} | 频率{frequency_score} | 模式{pattern_score} | "
              f"内容{content_score} | IP{ip_score}")
        
        return result
    
    def _get_active_accounts(self) -> list:
        """获取活跃账号列表"""
        conn = self.db.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT DISTINCT browser_id FROM action_logs
            WHERE action_time >= datetime('now', '-7 days')
        ''')
        
        results = cursor.fetchall()
        conn.close()
        
        return [row['browser_id'] for row in results]
    
    def _calculate_age_score(self, browser_id: str) -> int:
        """
        计算账号年龄分数（0-100，越高风险越高）
        新号风险高，老号风险低
        """
        account = self.db.get_account_by_browser_id(browser_id)
        
        if not account or not account.get('created_at'):
            return 50  # 默认中等风险
        
        try:
            created_at = datetime.strptime(account['created_at'], "%Y-%m-%d %H:%M:%S")
            age_days = (datetime.now() - created_at).days
            
            # 年龄越小，风险越高
            if age_days <= 7:
                return 90  # 新号期：高风险
            elif age_days <= 30:
                return 70  # 成长期：较高风险
            elif age_days <= 90:
                return 50  # 稳定期：中等风险
            elif age_days <= 180:
                return 30  # 成熟期：较低风险
            else:
                return 10  # 老号：低风险
        except:
            return 50
    
    def _calculate_frequency_score(self, browser_id: str) -> int:
        """
        计算操作频率分数（0-100，越高风险越高）
        频率过高风险高
        """
        conn = self.db.get_connection()
        cursor = conn.cursor()
        
        # 获取24小时内的操作次数
        cursor.execute('''
            SELECT COUNT(*) as count FROM action_logs
            WHERE browser_id = ?
            AND action_time >= datetime('now', '-24 hours')
        ''', (browser_id,))
        
        result = cursor.fetchone()
        conn.close()
        
        action_count = result['count'] if result else 0
        
        # 根据操作次数判断风险
        if action_count == 0:
            return 0
        elif action_count <= 20:
            return 20  # 低频：低风险
        elif action_count <= 50:
            return 40  # 中频：中等风险
        elif action_count <= 100:
            return 60  # 高频：较高风险
        elif action_count <= 200:
            return 80  # 超高频：高风险
        else:
            return 100  # 极高频：极高风险
    
    def _calculate_pattern_score(self, browser_id: str) -> int:
        """
        计算行为模式分数（0-100，越高风险越高）
        过于规律风险高
        """
        conn = self.db.get_connection()
        cursor = conn.cursor()
        
        # 获取最近的操作间隔
        cursor.execute('''
            SELECT interval_from_last FROM action_logs
            WHERE browser_id = ?
            AND interval_from_last IS NOT NULL
            ORDER BY action_time DESC
            LIMIT 20
        ''', (browser_id,))
        
        results = cursor.fetchall()
        conn.close()
        
        if not results or len(results) < 5:
            return 50  # 数据不足，默认中等风险
        
        intervals = [row['interval_from_last'] for row in results]
        
        # 计算间隔的标准差（规律性指标）
        avg = sum(intervals) / len(intervals)
        variance = sum((x - avg) ** 2 for x in intervals) / len(intervals)
        std_dev = variance ** 0.5
        
        # 变异系数（CV）= 标准差 / 平均值
        if avg > 0:
            cv = std_dev / avg
        else:
            cv = 0
        
        # CV越小，规律性越高，风险越高
        if cv < 0.2:
            return 90  # 过于规律：高风险
        elif cv < 0.4:
            return 70  # 较规律：较高风险
        elif cv < 0.6:
            return 40  # 适度随机：较低风险
        else:
            return 20  # 随机性好：低风险
    
    def _calculate_content_score(self, browser_id: str) -> int:
        """
        计算内容质量分数（0-100，越高风险越高）
        内容重复、营销性强风险高
        """
        conn = self.db.get_connection()
        cursor = conn.cursor()
        
        # 获取最近的评论内容
        cursor.execute('''
            SELECT content FROM action_logs
            WHERE browser_id = ?
            AND action_type = '评论'
            AND content IS NOT NULL
            ORDER BY action_time DESC
            LIMIT 10
        ''', (browser_id,))
        
        results = cursor.fetchall()
        conn.close()
        
        if not results:
            return 30  # 无评论，默认较低风险
        
        contents = [row['content'] for row in results]
        
        # 简单的相似度检测（检查重复内容）
        unique_contents = set(contents)
        similarity_ratio = 1 - (len(unique_contents) / len(contents))
        
        # 相似度越高，风险越高
        return int(similarity_ratio * 100)
    
    def _calculate_ip_score(self, browser_id: str) -> int:
        """
        计算IP风险分数（0-100，越高风险越高）
        IP关联账号多、封号率高风险高
        """
        conn = self.db.get_connection()
        cursor = conn.cursor()
        
        # 获取账号使用的IP
        cursor.execute('''
            SELECT ip_address FROM action_logs
            WHERE browser_id = ?
            AND ip_address IS NOT NULL
            ORDER BY action_time DESC
            LIMIT 1
        ''', (browser_id,))
        
        result = cursor.fetchone()
        
        if not result or not result['ip_address']:
            return 50  # 无IP信息，默认中等风险
        
        ip_address = result['ip_address']
        
        # 查找使用相同IP的其他账号
        cursor.execute('''
            SELECT DISTINCT browser_id FROM action_logs
            WHERE ip_address = ?
        ''', (ip_address,))
        
        accounts = cursor.fetchall()
        account_count = len(accounts)
        
        # 查找这些账号中被封的数量
        if account_count > 0:
            browser_ids = [acc['browser_id'] for acc in accounts]
            placeholders = ','.join(['?' for _ in browser_ids])
            
            cursor.execute(f'''
                SELECT COUNT(*) as count FROM ban_analysis
                WHERE browser_id IN ({placeholders})
            ''', browser_ids)
            
            banned_count = cursor.fetchone()['count']
            ban_rate = banned_count / account_count if account_count > 0 else 0
        else:
            ban_rate = 0
        
        conn.close()
        
        # 根据封号率和账号数量判断风险
        ban_risk = ban_rate * 100
        
        # 账号数量越多，风险越高
        if account_count >= 10:
            count_risk = 80
        elif account_count >= 5:
            count_risk = 60
        elif account_count >= 3:
            count_risk = 40
        else:
            count_risk = 20
        
        return int(ban_risk * 0.7 + count_risk * 0.3)
    
    def _get_risk_level(self, total_score: int) -> str:
        """根据总分判断风险等级"""
        if total_score < 30:
            return 'low'
        elif total_score < 50:
            return 'medium'
        elif total_score < 70:
            return 'high'
        else:
            return 'critical'
    
    def _save_score(self, browser_id: str, total_score: int, age_score: int,
                   frequency_score: int, pattern_score: int, content_score: int,
                   ip_score: int, risk_level: str):
        """保存风险分数到数据库"""
        conn = self.db.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                INSERT INTO risk_scores
                (browser_id, score_date, total_score, age_score, frequency_score,
                 pattern_score, content_score, ip_score, risk_level)
                VALUES (?, CURRENT_TIMESTAMP, ?, ?, ?, ?, ?, ?, ?)
            ''', (browser_id, total_score, age_score, frequency_score,
                  pattern_score, content_score, ip_score, risk_level))
            
            conn.commit()
        except Exception as e:
            print(f"⚠️ 保存风险分数失败: {e}")
            conn.rollback()
        finally:
            conn.close()
    
    def get_risk_score(self, browser_id: str) -> Optional[Dict]:
        """
        获取账号的最新风险分数
        
        Args:
            browser_id: 浏览器ID
        
        Returns:
            风险分数信息
        """
        conn = self.db.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM risk_scores
            WHERE browser_id = ?
            ORDER BY score_date DESC
            LIMIT 1
        ''', (browser_id,))
        
        result = cursor.fetchone()
        conn.close()
        
        return dict(result) if result else None
    
    def get_high_risk_accounts(self, risk_level: str = 'high') -> list:
        """
        获取高风险账号
        
        Args:
            risk_level: 风险等级（high/critical）
        
        Returns:
            高风险账号列表
        """
        conn = self.db.get_connection()
        cursor = conn.cursor()
        
        if risk_level == 'high':
            cursor.execute('''
                SELECT * FROM risk_scores
                WHERE risk_level IN ('high', 'critical')
                AND score_date >= datetime('now', '-1 day')
                ORDER BY total_score DESC
            ''')
        else:
            cursor.execute('''
                SELECT * FROM risk_scores
                WHERE risk_level = ?
                AND score_date >= datetime('now', '-1 day')
                ORDER BY total_score DESC
            ''', (risk_level,))
        
        results = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in results]


if __name__ == "__main__":
    # 测试风险评分器
    scorer = RiskScorer()
    
    print("测试1：计算所有账号的风险分数")
    scorer.calculate_all_scores()
    
    print("\n测试2：获取高风险账号")
    high_risk = scorer.get_high_risk_accounts('high')
    print(f"高风险账号数量: {len(high_risk)}")
    for account in high_risk[:5]:
        print(f"  - {account['browser_id']}: {account['total_score']} ({account['risk_level']})")
