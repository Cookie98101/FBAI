"""
数据库操作类
使用 SQLite 存储和管理数据
"""

import sqlite3
import os
import sys
import json
from datetime import datetime
from typing import List, Dict, Optional, Tuple


class Database:
    """数据库操作类"""
    
    def __init__(self, db_path: Optional[str] = None):
        """
        初始化数据库
        
        Args:
            db_path: 数据库文件路径，如果为 None 则自动选择
        """
        if db_path is None:
            db_path = self._get_default_db_path()
        
        self.db_path = db_path
        
        # 确保数据库目录存在
        db_dir = os.path.dirname(db_path)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir, exist_ok=True)
        
        # 初始化数据库表
        self.init_db()
    
    def _get_default_db_path(self) -> str:
        """获取默认数据库路径"""
        if getattr(sys, 'frozen', False):
            # 打包后的环境，放在用户目录
            user_dir = os.path.expanduser('~')
            app_dir = os.path.join(user_dir, '.facebook_automation')
            os.makedirs(app_dir, exist_ok=True)
            return os.path.join(app_dir, 'automation.db')
        else:
            # 开发环境，放在项目根目录
            current_dir = os.path.dirname(os.path.abspath(__file__))
            project_root = os.path.dirname(os.path.dirname(current_dir))
            return os.path.join(project_root, 'automation.db')
    
    def get_connection(self) -> sqlite3.Connection:
        """获取数据库连接"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # 返回字典格式
        return conn
    
    def init_db(self):
        """初始化数据库表"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # 1. 账号表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS accounts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                browser_id TEXT UNIQUE NOT NULL,
                username TEXT,
                password TEXT,
                cookie TEXT,
                status TEXT DEFAULT 'active',
                last_login_at TIMESTAMP,
                total_tasks INTEGER DEFAULT 0,
                total_likes INTEGER DEFAULT 0,
                total_comments INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # 2. 任务表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                account_id INTEGER NOT NULL,
                task_type TEXT NOT NULL,
                status TEXT DEFAULT 'pending',
                start_time TIMESTAMP,
                end_time TIMESTAMP,
                duration INTEGER,
                error_message TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (account_id) REFERENCES accounts(id)
            )
        ''')
        
        # 3. 互动记录表（包含去重字段）
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS interactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                account_id INTEGER NOT NULL,
                browser_id TEXT NOT NULL,
                post_id INTEGER,
                post_url TEXT NOT NULL,
                action_type TEXT NOT NULL,
                content TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (account_id) REFERENCES accounts(id),
                FOREIGN KEY (post_id) REFERENCES posts(id),
                UNIQUE(browser_id, post_url, action_type)
            )
        ''')
        
        # 4. 账号-小组关系表（简化版，直接存储浏览器ID）
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS account_groups (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                browser_id TEXT NOT NULL,
                group_id TEXT NOT NULL,
                group_name TEXT,
                member_count INTEGER,
                joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                joined_date DATE,
                status TEXT DEFAULT 'active',
                released_at TIMESTAMP,
                UNIQUE(browser_id, group_id)
            )
        ''')
        
        # 5. 不精准小组表（AI 判断为不符合的小组）
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS rejected_groups (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                group_id TEXT UNIQUE NOT NULL,
                group_name TEXT,
                group_description TEXT,
                reject_reason TEXT,
                rejected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # 6. 黑名单帖子表（用户主动添加的帖子）
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS blacklist_posts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                post_url TEXT UNIQUE NOT NULL,
                post_id TEXT,
                reason TEXT,
                added_by TEXT,
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # 7. 公共主页表（营销目标主页）
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS target_pages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                page_url TEXT UNIQUE NOT NULL,
                page_id TEXT,
                page_name TEXT,
                category TEXT,
                notes TEXT,
                status TEXT DEFAULT 'active',
                added_by TEXT,
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # 8. 好友管理表（账号-好友关系）
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS account_friends (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                browser_id TEXT NOT NULL,
                friend_id TEXT NOT NULL,
                friend_name TEXT,
                friend_profile_url TEXT,
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                status TEXT DEFAULT 'active',
                notes TEXT,
                UNIQUE(browser_id, friend_id)
            )
        ''')
        
        # 9. 封号表（记录被封禁的账号）
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS banned_accounts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                browser_id TEXT NOT NULL,
                username TEXT,
                password TEXT,
                ban_reason TEXT,
                banned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                notes TEXT
            )
        ''')
        
        # ==================== 风控系统表 ====================
        
        # 10. 详细操作日志表（风控）
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS action_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                browser_id TEXT NOT NULL,
                action_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                module_name TEXT NOT NULL,
                action_type TEXT NOT NULL,
                target TEXT,
                duration INTEGER,
                interval_from_last INTEGER,
                result TEXT,
                content TEXT,
                ip_address TEXT,
                device_fingerprint TEXT
            )
        ''')
        
        # 11. 封号分析表（风控）
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS ban_analysis (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                browser_id TEXT NOT NULL,
                ban_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                ban_type TEXT,
                account_age_days INTEGER,
                ban_delay_hours INTEGER,
                total_actions_before_ban INTEGER,
                actions_last_24h INTEGER,
                actions_last_72h INTEGER,
                last_module TEXT,
                last_action TEXT,
                ip_address TEXT,
                related_accounts TEXT
            )
        ''')
        
        # 12. 风险评分表（风控）
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS risk_scores (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                browser_id TEXT NOT NULL,
                score_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                total_score INTEGER,
                age_score INTEGER,
                frequency_score INTEGER,
                pattern_score INTEGER,
                content_score INTEGER,
                ip_score INTEGER,
                risk_level TEXT
            )
        ''')
        
        # 13. 阈值分析表（风控）
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS threshold_analysis (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                action_type TEXT NOT NULL,
                time_window TEXT NOT NULL,
                safe_threshold INTEGER,
                warning_threshold INTEGER,
                danger_threshold INTEGER,
                ban_threshold INTEGER,
                sample_size INTEGER,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(action_type, time_window)
            )
        ''')
        
        # 14. 账号群检测表（风控）
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS account_clusters (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cluster_type TEXT NOT NULL,
                cluster_key TEXT NOT NULL,
                account_list TEXT NOT NULL,
                account_count INTEGER,
                ban_count INTEGER DEFAULT 0,
                ban_rate REAL DEFAULT 0,
                risk_level TEXT,
                detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(cluster_type, cluster_key)
            )
        ''')
        
        conn.commit()
        
        # 执行数据库迁移（处理旧版本数据库）
        self._migrate_database(conn)
        
        # 创建索引（迁移后）
        cursor = conn.cursor()
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_accounts_browser_id ON accounts(browser_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_tasks_account_id ON tasks(account_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_interactions_account_id ON interactions(account_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_interactions_browser_id ON interactions(browser_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_interactions_post_url ON interactions(post_url)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_interactions_action_type ON interactions(action_type)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_account_groups_browser_id ON account_groups(browser_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_account_groups_group_id ON account_groups(group_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_account_groups_status ON account_groups(status)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_rejected_groups_group_id ON rejected_groups(group_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_blacklist_posts_post_url ON blacklist_posts(post_url)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_blacklist_posts_post_id ON blacklist_posts(post_id)')
        
        # 风控系统索引
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_action_logs_browser_id ON action_logs(browser_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_action_logs_action_time ON action_logs(action_time)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_action_logs_action_type ON action_logs(action_type)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_ban_analysis_browser_id ON ban_analysis(browser_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_ban_analysis_ban_date ON ban_analysis(ban_date)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_risk_scores_browser_id ON risk_scores(browser_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_risk_scores_score_date ON risk_scores(score_date)')
        
        conn.commit()
        conn.close()
    
    def _migrate_database(self, conn: sqlite3.Connection):
        """
        数据库迁移：处理旧版本数据库的表结构更新
        
        这个方法会检查表结构，如果缺少列则自动添加
        """
        cursor = conn.cursor()
        
        # 迁移 account_groups 表：添加 browser_id 列
        try:
            # 检查 account_groups 表是否存在
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='account_groups'")
            if cursor.fetchone():
                # 获取当前列
                cursor.execute('PRAGMA table_info(account_groups)')
                columns = {row['name'] for row in cursor.fetchall()}
                
                # 添加 browser_id 列（如果缺失）
                if 'browser_id' not in columns:
                    print("[数据库迁移] 开始迁移 account_groups 表...")
                    
                    # 方案：重建表（因为需要添加 NOT NULL 列）
                    # 1. 创建新表
                    cursor.execute('''
                        CREATE TABLE account_groups_new (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            browser_id TEXT NOT NULL,
                            group_id TEXT NOT NULL,
                            group_name TEXT,
                            joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            status TEXT DEFAULT 'active',
                            released_at TIMESTAMP,
                            UNIQUE(browser_id, group_id)
                        )
                    ''')
                    
                    # 2. 迁移数据（从 account_id 获取 browser_id）
                    cursor.execute('''
                        INSERT INTO account_groups_new (id, browser_id, group_id, group_name, joined_at, status, released_at)
                        SELECT ag.id, a.browser_id, ag.group_id, ag.group_name, ag.joined_at, ag.status, ag.released_at
                        FROM account_groups ag
                        JOIN accounts a ON ag.account_id = a.id
                    ''')
                    
                    # 3. 删除旧表
                    cursor.execute('DROP TABLE account_groups')
                    
                    # 4. 重命名新表
                    cursor.execute('ALTER TABLE account_groups_new RENAME TO account_groups')
                    
                    # 5. 重建索引
                    cursor.execute('CREATE INDEX IF NOT EXISTS idx_account_groups_browser_id ON account_groups(browser_id)')
                    cursor.execute('CREATE INDEX IF NOT EXISTS idx_account_groups_group_id ON account_groups(group_id)')
                    cursor.execute('CREATE INDEX IF NOT EXISTS idx_account_groups_status ON account_groups(status)')
                    
                    print("[数据库迁移] ✓ account_groups 表已迁移到新结构")
                    conn.commit()
                
        except Exception as e:
            print(f"[数据库迁移] 警告: account_groups 表迁移失败: {e}")
            conn.rollback()
        
        # 迁移 account_groups 表：添加 member_count 列
        try:
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='account_groups'")
            if cursor.fetchone():
                cursor.execute('PRAGMA table_info(account_groups)')
                columns = {row['name'] for row in cursor.fetchall()}
                
                if 'member_count' not in columns:
                    print("[数据库迁移] 添加 member_count 字段到 account_groups 表...")
                    cursor.execute('ALTER TABLE account_groups ADD COLUMN member_count INTEGER')
                    conn.commit()
                    print("[数据库迁移] ✓ member_count 字段已添加")
        except Exception as e:
            print(f"[数据库迁移] 警告: 添加 member_count 字段失败: {e}")
            conn.rollback()
        
        # 迁移 accounts 表：添加 backup_created_at 列（用于账号阶段管理）
        try:
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='accounts'")
            if cursor.fetchone():
                cursor.execute('PRAGMA table_info(accounts)')
                columns = {row['name'] for row in cursor.fetchall()}
                
                if 'backup_created_at' not in columns:
                    print("[数据库迁移] 添加 backup_created_at 字段到 accounts 表...")
                    cursor.execute('ALTER TABLE accounts ADD COLUMN backup_created_at TIMESTAMP')
                    conn.commit()
                    print("[数据库迁移] ✓ backup_created_at 字段已添加")
        except Exception as e:
            print(f"[数据库迁移] 警告: 添加 backup_created_at 字段失败: {e}")
            conn.rollback()
        
        # 迁移 interactions 表：添加 browser_id 列和唯一约束
        try:
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='interactions'")
            if cursor.fetchone():
                cursor.execute('PRAGMA table_info(interactions)')
                columns = {row['name'] for row in cursor.fetchall()}
                
                if 'browser_id' not in columns:
                    print("[数据库迁移] 开始迁移 interactions 表...")
                    
                    # 1. 创建新表
                    cursor.execute('''
                        CREATE TABLE interactions_new (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            account_id INTEGER NOT NULL,
                            browser_id TEXT NOT NULL,
                            post_id INTEGER,
                            post_url TEXT NOT NULL,
                            action_type TEXT NOT NULL,
                            content TEXT,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            FOREIGN KEY (account_id) REFERENCES accounts(id),
                            FOREIGN KEY (post_id) REFERENCES posts(id),
                            UNIQUE(browser_id, post_url, action_type)
                        )
                    ''')
                    
                    # 2. 迁移数据（从 account_id 获取 browser_id）
                    cursor.execute('''
                        INSERT INTO interactions_new (id, account_id, browser_id, post_id, post_url, action_type, content, created_at)
                        SELECT i.id, i.account_id, a.browser_id, i.post_id, i.post_url, i.action_type, i.content, i.created_at
                        FROM interactions i
                        JOIN accounts a ON i.account_id = a.id
                    ''')
                    
                    # 3. 删除旧表
                    cursor.execute('DROP TABLE interactions')
                    
                    # 4. 重命名新表
                    cursor.execute('ALTER TABLE interactions_new RENAME TO interactions')
                    
                    # 5. 重建索引
                    cursor.execute('CREATE INDEX IF NOT EXISTS idx_interactions_account_id ON interactions(account_id)')
                    cursor.execute('CREATE INDEX IF NOT EXISTS idx_interactions_browser_id ON interactions(browser_id)')
                    cursor.execute('CREATE INDEX IF NOT EXISTS idx_interactions_post_url ON interactions(post_url)')
                    cursor.execute('CREATE INDEX IF NOT EXISTS idx_interactions_action_type ON interactions(action_type)')
                    
                    print("[数据库迁移] ✓ interactions 表已迁移到新结构")
                    conn.commit()
                    
        except Exception as e:
            print(f"[数据库迁移] 警告: interactions 表迁移失败: {e}")
            conn.rollback()
        
        # 删除旧的 groups 表（不再需要）
        try:
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='groups'")
            if cursor.fetchone():
                cursor.execute('DROP TABLE groups')
                print("[数据库迁移] ✓ 已删除旧的 groups 表")
                conn.commit()
        except Exception as e:
            print(f"[数据库迁移] 警告: 删除 groups 表失败: {e}")
        
        conn.commit()
    
    # ==================== 账号相关 ====================
    
    def add_account(self, browser_id: str, username: str = None, password: str = None, cookie: str = None) -> int:
        """
        添加账号（如果已存在则更新，保持 created_at 不变）
        
        Args:
            browser_id: 浏览器ID
            username: 用户名
            password: 密码
            cookie: Cookie
        
        Returns:
            账号ID
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # 方法：先尝试插入，如果已存在则更新
        # 这样可以保持 created_at 不变
        
        # 1. 尝试插入（如果不存在）
        cursor.execute('''
            INSERT OR IGNORE INTO accounts (browser_id, username, password, cookie, created_at, updated_at)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        ''', (browser_id, username, password, cookie))
        
        # 2. 如果已存在，更新（不更新 created_at）
        cursor.execute('''
            UPDATE accounts 
            SET username = ?, password = ?, cookie = ?, updated_at = CURRENT_TIMESTAMP
            WHERE browser_id = ?
        ''', (username, password, cookie, browser_id))
        
        # 3. 获取账号ID
        cursor.execute('SELECT id FROM accounts WHERE browser_id = ?', (browser_id,))
        account_id = cursor.fetchone()['id']
        
        conn.commit()
        conn.close()
        
        return account_id
    
    def get_account_by_browser_id(self, browser_id: str) -> Optional[Dict]:
        """根据浏览器ID获取账号"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM accounts WHERE browser_id = ?', (browser_id,))
        row = cursor.fetchone()
        conn.close()
        
        return dict(row) if row else None
    
    def get_all_accounts(self, status: str = None) -> List[Dict]:
        """
        获取所有账号
        
        Args:
            status: 账号状态过滤（active/banned/restricted）
        
        Returns:
            账号列表
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        if status:
            cursor.execute('SELECT * FROM accounts WHERE status = ? ORDER BY created_at', (status,))
        else:
            cursor.execute('SELECT * FROM accounts ORDER BY created_at')
        
        rows = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in rows]
    
    def update_account_status(self, browser_id: str, status: str):
        """更新账号状态"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE accounts 
            SET status = ?, updated_at = CURRENT_TIMESTAMP
            WHERE browser_id = ?
        ''', (status, browser_id))
        
        conn.commit()
        conn.close()
    
    def update_account_login_time(self, browser_id: str):
        """更新账号最后登录时间"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE accounts 
            SET last_login_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
            WHERE browser_id = ?
        ''', (browser_id,))
        
        conn.commit()
        conn.close()
    
    def increment_account_stats(self, browser_id: str, likes: int = 0, comments: int = 0, tasks: int = 0):
        """增加账号统计数据"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE accounts 
            SET total_likes = total_likes + ?,
                total_comments = total_comments + ?,
                total_tasks = total_tasks + ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE browser_id = ?
        ''', (likes, comments, tasks, browser_id))
        
        conn.commit()
        conn.close()
    
    # ==================== 任务相关 ====================
    
    def create_task(self, account_id: int, task_type: str) -> int:
        """
        创建任务记录
        
        Args:
            account_id: 账号ID
            task_type: 任务类型（login/interaction/browse等）
        
        Returns:
            任务ID
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO tasks (account_id, task_type, status, start_time)
            VALUES (?, ?, 'running', CURRENT_TIMESTAMP)
        ''', (account_id, task_type))
        
        task_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return task_id
    
    def complete_task(self, task_id: int, status: str = 'completed', error_message: str = None):
        """
        完成任务
        
        Args:
            task_id: 任务ID
            status: 任务状态（completed/failed）
            error_message: 错误信息
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE tasks 
            SET status = ?,
                end_time = CURRENT_TIMESTAMP,
                duration = (julianday(CURRENT_TIMESTAMP) - julianday(start_time)) * 86400,
                error_message = ?
            WHERE id = ?
        ''', (status, error_message, task_id))
        
        conn.commit()
        conn.close()
    
    def get_account_tasks(self, account_id: int, limit: int = 100) -> List[Dict]:
        """获取账号的任务历史"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM tasks 
            WHERE account_id = ? 
            ORDER BY created_at DESC 
            LIMIT ?
        ''', (account_id, limit))
        
        rows = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in rows]
    
    # ==================== 互动相关 ====================
    
    def can_interact(self, browser_id: str, post_url: str, action_type: str) -> bool:
        """
        检查浏览器是否可以对帖子进行互动（去重检查）
        每个帖子的每种操作只允许1个浏览器执行
        
        Args:
            browser_id: 浏览器ID
            post_url: 帖子URL
            action_type: 互动类型（like/comment/add_friend等）
        
        Returns:
            True: 可以互动（帖子未被占用，或已被当前浏览器占用）
            False: 已被其他浏览器占用，不能互动
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # 检查是否有活跃的浏览器对这个帖子执行过这个操作
        cursor.execute('''
            SELECT browser_id FROM interactions
            WHERE post_url = ? AND action_type = ?
        ''', (post_url, action_type))
        
        result = cursor.fetchone()
        conn.close()
        
        if not result:
            # 没有浏览器操作过，可以互动
            return True
        
        # 如果是当前浏览器操作过，也可以互动（幂等性）
        return result['browser_id'] == browser_id
    
    def record_interaction(self, browser_id: str, post_url: str, action_type: str, content: str = None) -> bool:
        """
        记录互动（带去重：每个帖子的每种操作只允许1个浏览器）
        
        Args:
            browser_id: 浏览器ID
            post_url: 帖子URL
            action_type: 互动类型（like/comment/add_friend等）
            content: 评论内容或其他内容
        
        Returns:
            True: 记录成功
            False: 帖子已被其他浏览器操作，记录失败
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            # 1. 获取或创建账号
            account = self.get_account_by_browser_id(browser_id)
            if not account:
                # 自动创建账号
                account_id = self.add_account(browser_id)
            else:
                account_id = account['id']
            
            # 2. 检查是否已经互动过
            cursor.execute('''
                SELECT * FROM interactions 
                WHERE browser_id = ? AND post_url = ? AND action_type = ?
            ''', (browser_id, post_url, action_type))
            
            if cursor.fetchone():
                conn.close()
                return True  # 已经互动过了，幂等性
            
            # 3. 检查是否被其他浏览器占用
            cursor.execute('''
                SELECT browser_id FROM interactions
                WHERE post_url = ? AND action_type = ?
            ''', (post_url, action_type))
            
            existing = cursor.fetchone()
            if existing and existing['browser_id'] != browser_id:
                conn.close()
                return False  # 已被其他浏览器占用
            
            # 4. 记录互动
            cursor.execute('''
                INSERT INTO interactions (account_id, browser_id, post_url, action_type, content)
                VALUES (?, ?, ?, ?, ?)
            ''', (account_id, browser_id, post_url, action_type, content))
            
            conn.commit()
            conn.close()
            return True
            
        except Exception as e:
            conn.rollback()
            conn.close()
            print(f"记录互动失败: {e}")
            return False
    
    def has_interacted(self, browser_id: str, post_url: str, action_type: str = None) -> bool:
        """
        检查浏览器是否已经互动过
        
        Args:
            browser_id: 浏览器ID
            post_url: 帖子URL
            action_type: 互动类型（可选，不指定则检查所有类型）
        
        Returns:
            是否已互动
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        if action_type:
            cursor.execute('''
                SELECT COUNT(*) as count FROM interactions
                WHERE browser_id = ? AND post_url = ? AND action_type = ?
            ''', (browser_id, post_url, action_type))
        else:
            cursor.execute('''
                SELECT COUNT(*) as count FROM interactions
                WHERE browser_id = ? AND post_url = ?
            ''', (browser_id, post_url))
        
        count = cursor.fetchone()['count']
        conn.close()
        
        return count > 0
    
    def get_browser_interactions(self, browser_id: str, action_type: str = None, limit: int = 100) -> List[Dict]:
        """
        获取浏览器的互动历史
        
        Args:
            browser_id: 浏览器ID
            action_type: 互动类型过滤（可选）
            limit: 返回数量限制
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        if action_type:
            cursor.execute('''
                SELECT * FROM interactions 
                WHERE browser_id = ? AND action_type = ?
                ORDER BY created_at DESC 
                LIMIT ?
            ''', (browser_id, action_type, limit))
        else:
            cursor.execute('''
                SELECT * FROM interactions 
                WHERE browser_id = ?
                ORDER BY created_at DESC 
                LIMIT ?
            ''', (browser_id, limit))
        
        rows = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in rows]
    
    def get_interaction_status(self, post_url: str, action_type: str) -> Optional[Dict]:
        """
        获取帖子的互动状态（用于调试和监控）
        
        Returns:
            {
                'post_url': '...',
                'action_type': '...',
                'is_occupied': True/False,
                'occupied_by': {...}  # 占用的浏览器信息（如果有）
            }
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT browser_id, content, created_at
            FROM interactions
            WHERE post_url = ? AND action_type = ?
            LIMIT 1
        ''', (post_url, action_type))
        
        result = cursor.fetchone()
        conn.close()
        
        if result:
            return {
                'post_url': post_url,
                'action_type': action_type,
                'is_occupied': True,
                'occupied_by': {
                    'browser_id': result['browser_id'],
                    'content': result['content'],
                    'created_at': result['created_at']
                }
            }
        else:
            return {
                'post_url': post_url,
                'action_type': action_type,
                'is_occupied': False,
                'occupied_by': None
            }
    
    # ==================== 小组相关 ====================
    
    def can_join_group(self, browser_id: str, group_id: str) -> bool:
        """
        检查浏览器是否可以加入小组（全局去重检查）
        每个小组只允许1个浏览器加入
        
        Args:
            browser_id: 浏览器ID
            group_id: 小组ID
        
        Returns:
            True: 可以加入（小组未被占用，或已被当前浏览器占用）
            False: 已被其他浏览器占用，不能加入
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # 检查是否有活跃的浏览器占用这个小组
        cursor.execute('''
            SELECT browser_id FROM account_groups
            WHERE group_id = ? AND status = 'active'
        ''', (group_id,))
        
        result = cursor.fetchone()
        conn.close()
        
        if not result:
            # 没有浏览器占用，可以加入
            return True
        
        # 如果是当前浏览器占用，也可以加入（幂等性）
        return result['browser_id'] == browser_id
    
    def join_group(self, browser_id: str, group_id: str, group_name: str = None, member_count: int = None) -> bool:
        """
        浏览器加入小组（全局去重：每个小组只允许1个浏览器）
        
        Args:
            browser_id: 浏览器ID
            group_id: 小组ID
            group_name: 小组名称
            member_count: 小组成员数量
        
        Returns:
            True: 加入成功
            False: 小组已被其他浏览器占用，加入失败
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            # 1. 检查这个浏览器是否已经加入过这个小组
            cursor.execute('''
                SELECT * FROM account_groups 
                WHERE browser_id = ? AND group_id = ? AND status = 'active'
            ''', (browser_id, group_id))
            
            if cursor.fetchone():
                conn.close()
                return True  # 已经加入过了，幂等性
            
            # 2. 检查小组是否已被其他浏览器占用
            cursor.execute('''
                SELECT browser_id FROM account_groups
                WHERE group_id = ? AND status = 'active'
            ''', (group_id,))
            
            existing = cursor.fetchone()
            if existing and existing['browser_id'] != browser_id:
                conn.close()
                return False  # 小组已被其他浏览器占用
            
            # 3. 创建关系记录
            cursor.execute('''
                INSERT INTO account_groups (browser_id, group_id, group_name, member_count, status)
                VALUES (?, ?, ?, ?, 'active')
            ''', (browser_id, group_id, group_name, member_count))
            
            conn.commit()
            conn.close()
            return True
            
        except Exception as e:
            conn.rollback()
            conn.close()
            print(f"加入小组失败: {e}")
            return False
    
    def release_account_groups(self, browser_id: str) -> int:
        """
        释放浏览器占用的所有小组（账号封号时调用）
        
        Args:
            browser_id: 浏览器ID
        
        Returns:
            释放的小组数量
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            # 1. 获取浏览器占用的所有小组
            cursor.execute('''
                SELECT group_id FROM account_groups
                WHERE browser_id = ? AND status = 'active'
            ''', (browser_id,))
            
            groups = cursor.fetchall()
            
            # 2. 标记为已释放
            cursor.execute('''
                UPDATE account_groups
                SET status = 'released',
                    released_at = CURRENT_TIMESTAMP
                WHERE browser_id = ? AND status = 'active'
            ''', (browser_id,))
            
            conn.commit()
            released_count = len(groups)
            conn.close()
            
            return released_count
            
        except Exception as e:
            conn.rollback()
            conn.close()
            print(f"释放小组失败: {e}")
            return 0
    
    def get_group_status(self, group_id: str) -> Optional[Dict]:
        """
        获取小组状态（用于调试和监控）
        
        Returns:
            {
                'group_id': '...',
                'group_name': '...',
                'is_occupied': True/False,  # 是否被占用
                'occupied_by': {...}  # 占用的浏览器信息（如果有）
            }
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # 获取占用的浏览器
        cursor.execute('''
            SELECT browser_id, group_name, joined_at
            FROM account_groups
            WHERE group_id = ? AND status = 'active'
            LIMIT 1
        ''', (group_id,))
        
        result = cursor.fetchone()
        conn.close()
        
        if result:
            return {
                'group_id': group_id,
                'group_name': result['group_name'],
                'is_occupied': True,
                'occupied_by': {
                    'browser_id': result['browser_id'],
                    'joined_at': result['joined_at']
                }
            }
        else:
            return {
                'group_id': group_id,
                'group_name': None,
                'is_occupied': False,
                'occupied_by': None
            }
    
    def get_browser_groups(self, browser_id: str, status: str = 'active') -> List[Dict]:
        """
        获取浏览器加入的所有小组
        
        Args:
            browser_id: 浏览器ID
            status: 'active' 或 'released'
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM account_groups
            WHERE browser_id = ? AND status = ?
            ORDER BY joined_at DESC
        ''', (browser_id, status))
        
        rows = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in rows]
    
    # ==================== 不精准小组相关 ====================
    
    def is_group_rejected(self, group_id: str) -> bool:
        """
        检查小组是否在不精准小组表中
        
        Args:
            group_id: 小组ID
        
        Returns:
            True: 小组已被 AI 判断为不精准，应该跳过
            False: 小组不在表中，需要 AI 判断
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT COUNT(*) as count FROM rejected_groups
            WHERE group_id = ?
        ''', (group_id,))
        
        count = cursor.fetchone()['count']
        conn.close()
        
        return count > 0
    
    def reject_group(self, group_id: str, group_name: str = None, 
                    group_description: str = None, reject_reason: str = None) -> bool:
        """
        将小组标记为不精准（AI 判断后）
        
        Args:
            group_id: 小组ID
            group_name: 小组名称
            group_description: 小组简介
            reject_reason: AI 判断的原因
        
        Returns:
            True: 记录成功
            False: 记录失败
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                INSERT OR IGNORE INTO rejected_groups (group_id, group_name, group_description, reject_reason)
                VALUES (?, ?, ?, ?)
            ''', (group_id, group_name, group_description, reject_reason))
            
            conn.commit()
            conn.close()
            return True
            
        except Exception as e:
            conn.rollback()
            conn.close()
            print(f"记录不精准小组失败: {e}")
            return False
    
    def get_rejected_group(self, group_id: str) -> Optional[Dict]:
        """
        获取不精准小组的详细信息
        
        Args:
            group_id: 小组ID
        
        Returns:
            小组信息字典，如果不存在返回 None
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM rejected_groups
            WHERE group_id = ?
        ''', (group_id,))
        
        row = cursor.fetchone()
        conn.close()
        
        return dict(row) if row else None
    
    def get_all_rejected_groups(self, limit: int = 100) -> List[Dict]:
        """
        获取所有不精准小组
        
        Args:
            limit: 返回数量限制
        
        Returns:
            不精准小组列表
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM rejected_groups
            ORDER BY rejected_at DESC
            LIMIT ?
        ''', (limit,))
        
        rows = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in rows]
    
    def remove_rejected_group(self, group_id: str) -> bool:
        """
        从不精准小组表中移除（如果误判）
        
        Args:
            group_id: 小组ID
        
        Returns:
            True: 移除成功
            False: 移除失败
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                DELETE FROM rejected_groups
                WHERE group_id = ?
            ''', (group_id,))
            
            conn.commit()
            conn.close()
            return True
            
        except Exception as e:
            conn.rollback()
            conn.close()
            print(f"移除不精准小组失败: {e}")
            return False
    
    def get_rejected_groups_stats(self) -> Dict:
        """
        获取不精准小组统计信息
        
        Returns:
            统计信息字典
        """
        conn = self.get_connection()
        cursor = conn.cursor()
    
    # ==================== 加入小组配额相关 ====================
    
    def get_today_joined_count(self, browser_id: str) -> int:
        """
        获取今日已加入小组数量
        
        Args:
            browser_id: 浏览器ID
        
        Returns:
            今日加入数量
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT COUNT(*) as count FROM account_groups
            WHERE browser_id = ? 
            AND DATE(joined_at) = DATE('now')
            AND status = 'active'
        ''', (browser_id,))
        
        count = cursor.fetchone()['count']
        conn.close()
        
        return count
    
    def get_account_age_days(self, browser_id: str) -> int:
        """
        获取账号运行天数（从创建到现在）
        
        Args:
            browser_id: 浏览器ID
        
        Returns:
            运行天数
        """
        account = self.get_account_by_browser_id(browser_id)
        
        if not account:
            return 0
        
        import datetime
        try:
            created_at = datetime.datetime.strptime(
                account['created_at'], 
                "%Y-%m-%d %H:%M:%S"
            )
            
            now = datetime.datetime.now()
            days = (now - created_at).days
            
            return days
        except:
            return 0
    
    def get_group_statistics(self, browser_id: str = None) -> Dict:
        """
        获取小组统计信息
        
        Args:
            browser_id: 浏览器ID（None=全局统计）
        
        Returns:
            {
                'total_joined': 总加入数,
                'today_joined': 今日加入数,
                'total_rejected': 总拒绝数,
                'active_groups': 活跃小组数
            }
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        if browser_id:
            # 单个账号统计
            cursor.execute('''
                SELECT 
                    COUNT(*) as total_joined,
                    SUM(CASE WHEN DATE(joined_at) = DATE('now') THEN 1 ELSE 0 END) as today_joined
                FROM account_groups
                WHERE browser_id = ? AND status = 'active'
            ''', (browser_id,))
        else:
            # 全局统计
            cursor.execute('''
                SELECT 
                    COUNT(*) as total_joined,
                    SUM(CASE WHEN DATE(joined_at) = DATE('now') THEN 1 ELSE 0 END) as today_joined
                FROM account_groups
                WHERE status = 'active'
            ''')
        
        result = cursor.fetchone()
        
        # 拒绝数统计
        cursor.execute('SELECT COUNT(*) as total_rejected FROM rejected_groups')
        rejected = cursor.fetchone()
        
        conn.close()
        
        return {
            'total_joined': result['total_joined'] or 0,
            'today_joined': result['today_joined'] or 0,
            'total_rejected': rejected['total_rejected'] or 0,
            'active_groups': result['total_joined'] or 0
        }
        
        # 总数
        cursor.execute('SELECT COUNT(*) as count FROM rejected_groups')
        total = cursor.fetchone()['count']
        
        # 今日新增
        cursor.execute('''
            SELECT COUNT(*) as count FROM rejected_groups
            WHERE DATE(rejected_at) = DATE('now')
        ''')
        today = cursor.fetchone()['count']
        
        conn.close()
        
        return {
            'total': total,
            'today': today
        }
    
    # ==================== 黑名单帖子相关 ====================
    
    def is_post_blacklisted(self, post_url: str) -> bool:
        """
        检查帖子是否在黑名单中
        
        Args:
            post_url: 帖子URL
        
        Returns:
            True: 帖子在黑名单中，应该跳过
            False: 帖子不在黑名单中，可以操作
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT COUNT(*) as count FROM blacklist_posts
            WHERE post_url = ?
        ''', (post_url,))
        
        count = cursor.fetchone()['count']
        conn.close()
        
        return count > 0
    
    def add_to_blacklist(self, post_url: str, post_id: str = None, 
                        reason: str = None, added_by: str = None) -> bool:
        """
        将帖子添加到黑名单（用户主动添加）
        
        Args:
            post_url: 帖子URL
            post_id: 帖子ID（可选）
            reason: 添加原因
            added_by: 添加者（用户名或浏览器ID）
        
        Returns:
            True: 添加成功
            False: 添加失败
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                INSERT OR IGNORE INTO blacklist_posts (post_url, post_id, reason, added_by)
                VALUES (?, ?, ?, ?)
            ''', (post_url, post_id, reason, added_by))
            
            conn.commit()
            conn.close()
            return True
            
        except Exception as e:
            conn.rollback()
            conn.close()
            print(f"添加到黑名单失败: {e}")
            return False
    
    def remove_from_blacklist(self, post_url: str) -> bool:
        """
        从黑名单中移除帖子
        
        Args:
            post_url: 帖子URL
        
        Returns:
            True: 移除成功
            False: 移除失败
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                DELETE FROM blacklist_posts
                WHERE post_url = ?
            ''', (post_url,))
            
            conn.commit()
            conn.close()
            return True
            
        except Exception as e:
            conn.rollback()
            conn.close()
            print(f"从黑名单移除失败: {e}")
            return False
    
    def get_blacklist_post(self, post_url: str) -> Optional[Dict]:
        """
        获取黑名单帖子的详细信息
        
        Args:
            post_url: 帖子URL
        
        Returns:
            帖子信息字典，如果不存在返回 None
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM blacklist_posts
            WHERE post_url = ?
        ''', (post_url,))
        
        row = cursor.fetchone()
        conn.close()
        
        return dict(row) if row else None
    
    def get_all_blacklist_posts(self, limit: int = 100) -> List[Dict]:
        """
        获取所有黑名单帖子
        
        Args:
            limit: 返回数量限制
        
        Returns:
            黑名单帖子列表
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM blacklist_posts
            ORDER BY added_at DESC
            LIMIT ?
        ''', (limit,))
        
        rows = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in rows]
    
    def get_blacklist_stats(self) -> Dict:
        """
        获取黑名单统计信息
        
        Returns:
            统计信息字典
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # 总数
        cursor.execute('SELECT COUNT(*) as count FROM blacklist_posts')
        total = cursor.fetchone()['count']
        
        # 今日新增
        cursor.execute('''
            SELECT COUNT(*) as count FROM blacklist_posts
            WHERE DATE(added_at) = DATE('now')
        ''')
        today = cursor.fetchone()['count']
        
        conn.close()
        
        return {
            'total': total,
            'today': today
        }
    
    def batch_add_to_blacklist(self, post_urls: List[str], reason: str = None, 
                               added_by: str = None) -> int:
        """
        批量添加帖子到黑名单
        
        Args:
            post_urls: 帖子URL列表
            reason: 添加原因
            added_by: 添加者
        
        Returns:
            成功添加的数量
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        success_count = 0
        
        try:
            for post_url in post_urls:
                try:
                    cursor.execute('''
                        INSERT OR IGNORE INTO blacklist_posts (post_url, reason, added_by)
                        VALUES (?, ?, ?)
                    ''', (post_url, reason, added_by))
                    
                    if cursor.rowcount > 0:
                        success_count += 1
                        
                except:
                    continue
            
            conn.commit()
            conn.close()
            return success_count
            
        except Exception as e:
            conn.rollback()
            conn.close()
            print(f"批量添加到黑名单失败: {e}")
            return success_count
    
    def clear_blacklist(self) -> bool:
        """
        清空黑名单（慎用）
        
        Returns:
            True: 清空成功
            False: 清空失败
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute('DELETE FROM blacklist_posts')
            conn.commit()
            conn.close()
            return True
            
        except Exception as e:
            conn.rollback()
            conn.close()
            print(f"清空黑名单失败: {e}")
            return False
    
    # ==================== 公共主页相关 ====================
    
    def is_page_in_targets(self, page_url: str) -> bool:
        """
        检查主页是否在目标列表中
        
        Args:
            page_url: 主页URL
        
        Returns:
            True: 主页在目标列表中
            False: 主页不在目标列表中
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT COUNT(*) as count FROM target_pages
            WHERE page_url = ? AND status = 'active'
        ''', (page_url,))
        
        count = cursor.fetchone()['count']
        conn.close()
        
        return count > 0
    
    def add_target_page(self, page_url: str, page_id: str = None, 
                       page_name: str = None, category: str = None,
                       notes: str = None, added_by: str = None) -> bool:
        """
        添加目标主页
        
        Args:
            page_url: 主页URL
            page_id: 主页ID（可选）
            page_name: 主页名称（可选）
            category: 分类（可选）
            notes: 备注（可选）
            added_by: 添加者（用户名或浏览器ID）
        
        Returns:
            True: 添加成功
            False: 添加失败
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                INSERT OR IGNORE INTO target_pages 
                (page_url, page_id, page_name, category, notes, added_by)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (page_url, page_id, page_name, category, notes, added_by))
            
            conn.commit()
            conn.close()
            return True
            
        except Exception as e:
            conn.rollback()
            conn.close()
            print(f"添加目标主页失败: {e}")
            return False
    
    def remove_target_page(self, page_url: str) -> bool:
        """
        移除目标主页
        
        Args:
            page_url: 主页URL
        
        Returns:
            True: 移除成功
            False: 移除失败
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                DELETE FROM target_pages
                WHERE page_url = ?
            ''', (page_url,))
            
            conn.commit()
            conn.close()
            return True
            
        except Exception as e:
            conn.rollback()
            conn.close()
            print(f"移除目标主页失败: {e}")
            return False
    
    def update_target_page_status(self, page_url: str, status: str) -> bool:
        """
        更新目标主页状态
        
        Args:
            page_url: 主页URL
            status: 状态（active/inactive）
        
        Returns:
            True: 更新成功
            False: 更新失败
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                UPDATE target_pages
                SET status = ?, updated_at = CURRENT_TIMESTAMP
                WHERE page_url = ?
            ''', (status, page_url))
            
            conn.commit()
            conn.close()
            return True
            
        except Exception as e:
            conn.rollback()
            conn.close()
            print(f"更新目标主页状态失败: {e}")
            return False
    
    def get_target_page(self, page_url: str) -> Optional[Dict]:
        """
        获取目标主页的详细信息
        
        Args:
            page_url: 主页URL
        
        Returns:
            主页信息字典，如果不存在返回 None
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM target_pages
            WHERE page_url = ?
        ''', (page_url,))
        
        row = cursor.fetchone()
        conn.close()
        
        return dict(row) if row else None
    
    def get_all_target_pages(self, status: str = None, limit: int = 100) -> List[Dict]:
        """
        获取所有目标主页
        
        Args:
            status: 状态过滤（可选，active/inactive）
            limit: 返回数量限制
        
        Returns:
            目标主页列表
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        if status:
            cursor.execute('''
                SELECT * FROM target_pages
                WHERE status = ?
                ORDER BY added_at DESC
                LIMIT ?
            ''', (status, limit))
        else:
            cursor.execute('''
                SELECT * FROM target_pages
                ORDER BY added_at DESC
                LIMIT ?
            ''', (limit,))
        
        rows = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in rows]
    
    def get_target_pages_stats(self) -> Dict:
        """
        获取目标主页统计信息
        
        Returns:
            统计信息字典
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # 总数
        cursor.execute('SELECT COUNT(*) as count FROM target_pages')
        total = cursor.fetchone()['count']
        
        # 活跃数
        cursor.execute('''
            SELECT COUNT(*) as count FROM target_pages
            WHERE status = 'active'
        ''')
        active = cursor.fetchone()['count']
        
        # 今日新增
        cursor.execute('''
            SELECT COUNT(*) as count FROM target_pages
            WHERE DATE(added_at) = DATE('now')
        ''')
        today = cursor.fetchone()['count']
        
        conn.close()
        
        return {
            'total': total,
            'active': active,
            'inactive': total - active,
            'today': today
        }
    
    def batch_add_target_pages(self, page_urls: List[str], category: str = None, 
                               added_by: str = None) -> int:
        """
        批量添加目标主页
        
        Args:
            page_urls: 主页URL列表
            category: 分类
            added_by: 添加者
        
        Returns:
            成功添加的数量
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        success_count = 0
        
        try:
            for page_url in page_urls:
                try:
                    cursor.execute('''
                        INSERT OR IGNORE INTO target_pages (page_url, category, added_by)
                        VALUES (?, ?, ?)
                    ''', (page_url, category, added_by))
                    
                    if cursor.rowcount > 0:
                        success_count += 1
                        
                except:
                    continue
            
            conn.commit()
            conn.close()
            return success_count
            
        except Exception as e:
            conn.rollback()
            conn.close()
            print(f"批量添加目标主页失败: {e}")
            return success_count
    
    def clear_target_pages(self) -> bool:
        """
        清空目标主页列表（慎用）
        
        Returns:
            True: 清空成功
            False: 清空失败
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute('DELETE FROM target_pages')
            conn.commit()
            conn.close()
            return True
            
        except Exception as e:
            conn.rollback()
            conn.close()
            print(f"清空目标主页失败: {e}")
            return False
    
    # ==================== 好友管理相关 ====================
    
    def add_friend(self, browser_id: str, friend_id: str, 
                   friend_name: str = None, friend_profile_url: str = None,
                   notes: str = None) -> bool:
        """
        添加好友记录
        
        Args:
            browser_id: 浏览器ID
            friend_id: 好友ID
            friend_name: 好友名称（可选）
            friend_profile_url: 好友主页URL（可选）
            notes: 备注（可选）
        
        Returns:
            True: 添加成功
            False: 添加失败（可能已存在）
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                INSERT OR IGNORE INTO account_friends 
                (browser_id, friend_id, friend_name, friend_profile_url, notes)
                VALUES (?, ?, ?, ?, ?)
            ''', (browser_id, friend_id, friend_name, friend_profile_url, notes))
            
            success = cursor.rowcount > 0
            conn.commit()
            conn.close()
            return success
            
        except Exception as e:
            conn.rollback()
            conn.close()
            print(f"添加好友记录失败: {e}")
            return False
    
    def is_friend_added(self, browser_id: str, friend_id: str) -> bool:
        """
        检查是否已添加好友
        
        Args:
            browser_id: 浏览器ID
            friend_id: 好友ID
        
        Returns:
            True: 已添加
            False: 未添加
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT COUNT(*) as count FROM account_friends
            WHERE browser_id = ? AND friend_id = ?
        ''', (browser_id, friend_id))
        
        count = cursor.fetchone()['count']
        conn.close()
        
        return count > 0
    
    def get_friend(self, browser_id: str, friend_id: str) -> Optional[Dict]:
        """
        获取好友信息
        
        Args:
            browser_id: 浏览器ID
            friend_id: 好友ID
        
        Returns:
            好友信息字典，如果不存在返回 None
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM account_friends
            WHERE browser_id = ? AND friend_id = ?
        ''', (browser_id, friend_id))
        
        row = cursor.fetchone()
        conn.close()
        
        return dict(row) if row else None
    
    def get_friends_by_browser(self, browser_id: str, limit: int = 100) -> List[Dict]:
        """
        获取指定浏览器的所有好友
        
        Args:
            browser_id: 浏览器ID
            limit: 返回数量限制
        
        Returns:
            好友列表
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM account_friends
            WHERE browser_id = ?
            ORDER BY added_at DESC
            LIMIT ?
        ''', (browser_id, limit))
        
        rows = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in rows]
    
    def get_all_friends(self, limit: int = 1000) -> List[Dict]:
        """
        获取所有好友记录
        
        Args:
            limit: 返回数量限制
        
        Returns:
            好友列表
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM account_friends
            ORDER BY added_at DESC
            LIMIT ?
        ''', (limit,))
        
        rows = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in rows]
    
    def get_friends_stats(self, browser_id: str = None) -> Dict:
        """
        获取好友统计信息
        
        Args:
            browser_id: 浏览器ID（可选，如果提供则只统计该浏览器）
        
        Returns:
            统计信息字典
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        if browser_id:
            # 指定浏览器的统计
            cursor.execute('''
                SELECT COUNT(*) as count FROM account_friends
                WHERE browser_id = ?
            ''', (browser_id,))
            total = cursor.fetchone()['count']
            
            cursor.execute('''
                SELECT COUNT(*) as count FROM account_friends
                WHERE browser_id = ? AND DATE(added_at) = DATE('now')
            ''', (browser_id,))
            today = cursor.fetchone()['count']
        else:
            # 全局统计
            cursor.execute('SELECT COUNT(*) as count FROM account_friends')
            total = cursor.fetchone()['count']
            
            cursor.execute('''
                SELECT COUNT(*) as count FROM account_friends
                WHERE DATE(added_at) = DATE('now')
            ''')
            today = cursor.fetchone()['count']
        
        conn.close()
        
        return {
            'total': total,
            'today': today
        }
    
    def remove_friend(self, browser_id: str, friend_id: str) -> bool:
        """
        移除好友记录
        
        Args:
            browser_id: 浏览器ID
            friend_id: 好友ID
        
        Returns:
            True: 移除成功
            False: 移除失败
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                DELETE FROM account_friends
                WHERE browser_id = ? AND friend_id = ?
            ''', (browser_id, friend_id))
            
            conn.commit()
            conn.close()
            return True
            
        except Exception as e:
            conn.rollback()
            conn.close()
            print(f"移除好友记录失败: {e}")
            return False
    
    # ==================== 统计相关 ====================
    
    def get_account_stats(self, account_id: int) -> Dict:
        """获取账号统计信息"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # 基本信息
        cursor.execute('SELECT * FROM accounts WHERE id = ?', (account_id,))
        account = dict(cursor.fetchone())
        
        # 今日互动数
        cursor.execute('''
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN action_type = 'like' THEN 1 ELSE 0 END) as likes,
                SUM(CASE WHEN action_type = 'comment' THEN 1 ELSE 0 END) as comments
            FROM interactions
            WHERE account_id = ? AND DATE(created_at) = DATE('now')
        ''', (account_id,))
        today_stats = dict(cursor.fetchone())
        
        # 今日任务数
        cursor.execute('''
            SELECT COUNT(*) as count FROM tasks
            WHERE account_id = ? AND DATE(created_at) = DATE('now')
        ''', (account_id,))
        today_tasks = cursor.fetchone()['count']
        
        conn.close()
        
        return {
            'account': account,
            'today': {
                'interactions': today_stats['total'],
                'likes': today_stats['likes'],
                'comments': today_stats['comments'],
                'tasks': today_tasks
            }
        }
    
    def get_account_days_since_creation(self, browser_id: str) -> int:
        """
        获取账号创建以来的天数
        
        Args:
            browser_id: 浏览器ID
        
        Returns:
            天数（从 created_at 到现在）
        """
        account = self.get_account_by_browser_id(browser_id)
        if not account:
            return 0
        
        import datetime
        created_at_str = account['created_at']
        
        try:
            # SQLite 格式: "YYYY-MM-DD HH:MM:SS"
            created_at = datetime.datetime.strptime(created_at_str, "%Y-%m-%d %H:%M:%S")
            now = datetime.datetime.now()
            delta = now - created_at
            return delta.days
        except:
            return 0
    
    # ==================== 数据迁移 ====================
    
    def migrate_from_json(self, json_file_path: str):
        """
        从JSON文件迁移数据
        
        Args:
            json_file_path: JSON文件路径
        """
        if not os.path.exists(json_file_path):
            print(f"JSON文件不存在: {json_file_path}")
            return
        
        with open(json_file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # 迁移账号数据
        for account in data:
            browser_id = account.get('browser_id')
            if browser_id:
                self.add_account(
                    browser_id=browser_id,
                    username=account.get('name'),
                    password=account.get('password'),
                    cookie=account.get('cookie')
                )
        
        print(f"✓ 已从 {json_file_path} 迁移 {len(data)} 个账号")

    # ==================== 封号管理相关 ====================
    
    def add_banned_account(self, browser_id: str, username: str = None, 
                          password: str = None, ban_reason: str = None,
                          notes: str = None) -> bool:
        """
        添加封号记录
        
        Args:
            browser_id: 浏览器ID
            username: 用户名（可选）
            password: 密码（可选）
            ban_reason: 封号原因（可选）
            notes: 备注（可选）
        
        Returns:
            True: 添加成功
            False: 添加失败
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                INSERT INTO banned_accounts 
                (browser_id, username, password, ban_reason, notes)
                VALUES (?, ?, ?, ?, ?)
            ''', (browser_id, username, password, ban_reason, notes))
            
            conn.commit()
            conn.close()
            return True
            
        except Exception as e:
            conn.rollback()
            conn.close()
            print(f"添加封号记录失败: {e}")
            return False
    
    def is_account_banned(self, browser_id: str) -> bool:
        """
        检查账号是否已被封禁
        
        Args:
            browser_id: 浏览器ID
        
        Returns:
            True: 账号已被封禁
            False: 账号未被封禁
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT COUNT(*) as count FROM banned_accounts
            WHERE browser_id = ?
        ''', (browser_id,))
        
        count = cursor.fetchone()['count']
        conn.close()
        
        return count > 0
    
    def get_banned_account(self, browser_id: str) -> Optional[Dict]:
        """
        获取封号记录
        
        Args:
            browser_id: 浏览器ID
        
        Returns:
            封号记录字典，如果不存在返回 None
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM banned_accounts
            WHERE browser_id = ?
            ORDER BY banned_at DESC
            LIMIT 1
        ''', (browser_id,))
        
        row = cursor.fetchone()
        conn.close()
        
        return dict(row) if row else None
    
    def get_all_banned_accounts(self, limit: int = 1000) -> List[Dict]:
        """
        获取所有封号记录
        
        Args:
            limit: 返回数量限制
        
        Returns:
            封号记录列表
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM banned_accounts
            ORDER BY banned_at DESC
            LIMIT ?
        ''', (limit,))
        
        rows = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in rows]
    
    def get_banned_accounts_stats(self) -> Dict:
        """
        获取封号统计信息
        
        Returns:
            统计信息字典
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # 总数
        cursor.execute('SELECT COUNT(*) as count FROM banned_accounts')
        total = cursor.fetchone()['count']
        
        # 今日新增
        cursor.execute('''
            SELECT COUNT(*) as count FROM banned_accounts
            WHERE DATE(banned_at) = DATE('now')
        ''')
        today = cursor.fetchone()['count']
        
        # 本周新增
        cursor.execute('''
            SELECT COUNT(*) as count FROM banned_accounts
            WHERE DATE(banned_at) >= DATE('now', '-7 days')
        ''')
        this_week = cursor.fetchone()['count']
        
        conn.close()
        
        return {
            'total': total,
            'today': today,
            'this_week': this_week
        }
    
    def remove_banned_account(self, browser_id: str) -> bool:
        """
        移除封号记录（如果误判或解封）
        
        Args:
            browser_id: 浏览器ID
        
        Returns:
            True: 移除成功
            False: 移除失败
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                DELETE FROM banned_accounts
                WHERE browser_id = ?
            ''', (browser_id,))
            
            conn.commit()
            conn.close()
            return True
            
        except Exception as e:
            conn.rollback()
            conn.close()
            print(f"移除封号记录失败: {e}")
            return False
    
    def update_banned_account_notes(self, browser_id: str, notes: str) -> bool:
        """
        更新封号记录备注
        
        Args:
            browser_id: 浏览器ID
            notes: 备注内容
        
        Returns:
            True: 更新成功
            False: 更新失败
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                UPDATE banned_accounts
                SET notes = ?
                WHERE browser_id = ?
            ''', (notes, browser_id))
            
            conn.commit()
            conn.close()
            return True
            
        except Exception as e:
            conn.rollback()
            conn.close()
            print(f"更新封号记录备注失败: {e}")
            return False

    # ==================== 异常记录相关方法 ====================
    
    def record_exception(
        self,
        browser_id: str,
        exception_type: str,
        details: str = "",
        pause_minutes: int = 0
    ) -> bool:
        """
        记录异常到数据库
        
        Args:
            browser_id: 浏览器ID
            exception_type: 异常类型 ('load_fail', 'captcha', 'restricted', 'timeout')
            details: 详细信息
            pause_minutes: 建议暂停时长（分钟）
        
        Returns:
            是否记录成功
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            # 确保 exceptions 表存在
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS exceptions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    browser_id TEXT NOT NULL,
                    exception_type TEXT NOT NULL,
                    details TEXT,
                    pause_minutes INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # 插入异常记录
            cursor.execute('''
                INSERT INTO exceptions (browser_id, exception_type, details, pause_minutes)
                VALUES (?, ?, ?, ?)
            ''', (browser_id, exception_type, details, pause_minutes))
            
            conn.commit()
            conn.close()
            return True
            
        except Exception as e:
            print(f"[数据库] 记录异常失败: {e}")
            conn.rollback()
            conn.close()
            return False
    
    def get_recent_exceptions(
        self,
        browser_id: str,
        hours: int = 24
    ) -> List[Dict]:
        """
        获取最近的异常记录
        
        Args:
            browser_id: 浏览器ID
            hours: 查询最近多少小时的记录
        
        Returns:
            异常记录列表
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            # 确保表存在
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS exceptions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    browser_id TEXT NOT NULL,
                    exception_type TEXT NOT NULL,
                    details TEXT,
                    pause_minutes INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # 查询最近的异常
            cursor.execute('''
                SELECT * FROM exceptions
                WHERE browser_id = ?
                AND datetime(created_at) >= datetime('now', '-' || ? || ' hours')
                ORDER BY created_at DESC
            ''', (browser_id, hours))
            
            rows = cursor.fetchall()
            conn.close()
            
            return [dict(row) for row in rows]
            
        except Exception as e:
            print(f"[数据库] 获取异常记录失败: {e}")
            conn.close()
            return []
    
    def should_pause_browser(
        self,
        browser_id: str
    ) -> Tuple[bool, str, int]:
        """
        检查浏览器是否应该暂停
        
        Args:
            browser_id: 浏览器ID
        
        Returns:
            (是否应该暂停, 原因, 暂停时长分钟)
        """
        # 获取最近24小时的异常
        exceptions = self.get_recent_exceptions(browser_id, hours=24)
        
        if not exceptions:
            return (False, "", 0)
        
        # 检查最近的异常
        最近异常 = exceptions[0]
        异常类型 = 最近异常['exception_type']
        暂停时长 = 最近异常['pause_minutes']
        创建时间 = datetime.fromisoformat(最近异常['created_at'])
        
        # 计算是否还在暂停期内
        from datetime import timedelta
        暂停结束时间 = 创建时间 + timedelta(minutes=暂停时长)
        当前时间 = datetime.now()
        
        if 当前时间 < 暂停结束时间:
            剩余分钟 = int((暂停结束时间 - 当前时间).total_seconds() / 60)
            原因 = f"{异常类型} - 还需暂停{剩余分钟}分钟"
            return (True, 原因, 剩余分钟)
        
        return (False, "", 0)

    # ==================== 潜在用户池相关 ====================
    
    def add_potential_user(
        self,
        user_id: str,
        user_name: str,
        profile_url: str,
        intent_score: int,
        comment_text: str = None,
        source_post_id: str = None,
        source_comment_id: str = None,
        discovered_by: str = None,
        next_action_date: str = None
    ) -> bool:
        """
        添加潜在用户到用户池
        
        Args:
            user_id: 用户ID
            user_name: 用户名
            profile_url: 用户主页URL
            intent_score: 意向评分（0-10）
            comment_text: 评论内容
            source_post_id: 来源帖子ID
            source_comment_id: 来源评论ID
            discovered_by: 发现者（浏览器ID）
            next_action_date: 下次动作日期（YYYY-MM-DD）
        
        Returns:
            是否成功添加
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            # 确保表存在
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS potential_users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    user_name TEXT,
                    profile_url TEXT,
                    intent_score INTEGER DEFAULT 0,
                    comment_text TEXT,
                    source_post_id TEXT,
                    source_comment_id TEXT,
                    discovered_by TEXT,
                    discovered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    next_action_date DATE,
                    status TEXT DEFAULT 'pending',
                    last_action_at TIMESTAMP,
                    notes TEXT,
                    UNIQUE(user_id, discovered_by)
                )
            ''')
            
            # 检查是否已存在
            cursor.execute('''
                SELECT id FROM potential_users
                WHERE user_id = ? AND discovered_by = ?
            ''', (user_id, discovered_by))
            
            existing = cursor.fetchone()
            
            if existing:
                # 更新现有记录（如果新的意向评分更高）
                cursor.execute('''
                    UPDATE potential_users
                    SET intent_score = MAX(intent_score, ?),
                        comment_text = COALESCE(?, comment_text),
                        next_action_date = COALESCE(?, next_action_date),
                        discovered_at = CURRENT_TIMESTAMP
                    WHERE user_id = ? AND discovered_by = ?
                ''', (intent_score, comment_text, next_action_date, user_id, discovered_by))
            else:
                # 插入新记录
                cursor.execute('''
                    INSERT INTO potential_users (
                        user_id, user_name, profile_url, intent_score,
                        comment_text, source_post_id, source_comment_id,
                        discovered_by, next_action_date
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    user_id, user_name, profile_url, intent_score,
                    comment_text, source_post_id, source_comment_id,
                    discovered_by, next_action_date
                ))
            
            conn.commit()
            conn.close()
            return True
            
        except Exception as e:
            print(f"[数据库] 添加潜在用户失败: {e}")
            conn.rollback()
            conn.close()
            return False
    
    def get_potential_users_for_action(
        self,
        discovered_by: str = None,
        min_intent_score: int = 6,
        limit: int = 10
    ) -> List[Dict]:
        """
        获取需要执行动作的潜在用户
        
        Args:
            discovered_by: 发现者（浏览器ID）
            min_intent_score: 最低意向评分
            limit: 返回数量限制
        
        Returns:
            潜在用户列表
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            # 确保表存在
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS potential_users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    user_name TEXT,
                    profile_url TEXT,
                    intent_score INTEGER DEFAULT 0,
                    comment_text TEXT,
                    source_post_id TEXT,
                    source_comment_id TEXT,
                    discovered_by TEXT,
                    discovered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    next_action_date DATE,
                    status TEXT DEFAULT 'pending',
                    last_action_at TIMESTAMP,
                    notes TEXT,
                    UNIQUE(user_id, discovered_by)
                )
            ''')
            
            # 查询符合条件的用户
            if discovered_by:
                cursor.execute('''
                    SELECT * FROM potential_users
                    WHERE discovered_by = ?
                    AND intent_score >= ?
                    AND status = 'pending'
                    AND (next_action_date IS NULL OR date(next_action_date) <= date('now'))
                    ORDER BY intent_score DESC, discovered_at ASC
                    LIMIT ?
                ''', (discovered_by, min_intent_score, limit))
            else:
                cursor.execute('''
                    SELECT * FROM potential_users
                    WHERE intent_score >= ?
                    AND status = 'pending'
                    AND (next_action_date IS NULL OR date(next_action_date) <= date('now'))
                    ORDER BY intent_score DESC, discovered_at ASC
                    LIMIT ?
                ''', (min_intent_score, limit))
            
            rows = cursor.fetchall()
            conn.close()
            
            return [dict(row) for row in rows]
            
        except Exception as e:
            print(f"[数据库] 获取潜在用户失败: {e}")
            conn.close()
            return []
    
    def update_potential_user_status(
        self,
        user_id: str,
        discovered_by: str,
        status: str,
        notes: str = None
    ) -> bool:
        """
        更新潜在用户状态
        
        Args:
            user_id: 用户ID
            discovered_by: 发现者（浏览器ID）
            status: 状态（pending/contacted/converted/failed）
            notes: 备注
        
        Returns:
            是否成功更新
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                UPDATE potential_users
                SET status = ?,
                    last_action_at = CURRENT_TIMESTAMP,
                    notes = COALESCE(?, notes)
                WHERE user_id = ? AND discovered_by = ?
            ''', (status, notes, user_id, discovered_by))
            
            conn.commit()
            conn.close()
            return True
            
        except Exception as e:
            print(f"[数据库] 更新潜在用户状态失败: {e}")
            conn.rollback()
            conn.close()
            return False
    
    def get_potential_users_stats(
        self,
        discovered_by: str = None
    ) -> Dict:
        """
        获取潜在用户池统计信息
        
        Args:
            discovered_by: 发现者（浏览器ID）
        
        Returns:
            统计信息字典
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            # 确保表存在
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS potential_users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    user_name TEXT,
                    profile_url TEXT,
                    intent_score INTEGER DEFAULT 0,
                    comment_text TEXT,
                    source_post_id TEXT,
                    source_comment_id TEXT,
                    discovered_by TEXT,
                    discovered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    next_action_date DATE,
                    status TEXT DEFAULT 'pending',
                    last_action_at TIMESTAMP,
                    notes TEXT,
                    UNIQUE(user_id, discovered_by)
                )
            ''')
            
            # 总数
            if discovered_by:
                cursor.execute('''
                    SELECT COUNT(*) as total FROM potential_users
                    WHERE discovered_by = ?
                ''', (discovered_by,))
            else:
                cursor.execute('SELECT COUNT(*) as total FROM potential_users')
            
            total = cursor.fetchone()['total']
            
            # 按状态统计
            if discovered_by:
                cursor.execute('''
                    SELECT status, COUNT(*) as count
                    FROM potential_users
                    WHERE discovered_by = ?
                    GROUP BY status
                ''', (discovered_by,))
            else:
                cursor.execute('''
                    SELECT status, COUNT(*) as count
                    FROM potential_users
                    GROUP BY status
                ''')
            
            status_counts = {row['status']: row['count'] for row in cursor.fetchall()}
            
            # 按意向评分统计
            if discovered_by:
                cursor.execute('''
                    SELECT 
                        SUM(CASE WHEN intent_score >= 9 THEN 1 ELSE 0 END) as high_intent,
                        SUM(CASE WHEN intent_score >= 6 AND intent_score < 9 THEN 1 ELSE 0 END) as medium_intent,
                        SUM(CASE WHEN intent_score >= 3 AND intent_score < 6 THEN 1 ELSE 0 END) as low_intent
                    FROM potential_users
                    WHERE discovered_by = ?
                ''', (discovered_by,))
            else:
                cursor.execute('''
                    SELECT 
                        SUM(CASE WHEN intent_score >= 9 THEN 1 ELSE 0 END) as high_intent,
                        SUM(CASE WHEN intent_score >= 6 AND intent_score < 9 THEN 1 ELSE 0 END) as medium_intent,
                        SUM(CASE WHEN intent_score >= 3 AND intent_score < 6 THEN 1 ELSE 0 END) as low_intent
                    FROM potential_users
                ''')
            
            intent_counts = cursor.fetchone()
            
            conn.close()
            
            return {
                'total': total,
                'pending': status_counts.get('pending', 0),
                'contacted': status_counts.get('contacted', 0),
                'converted': status_counts.get('converted', 0),
                'failed': status_counts.get('failed', 0),
                'high_intent': intent_counts['high_intent'] or 0,
                'medium_intent': intent_counts['medium_intent'] or 0,
                'low_intent': intent_counts['low_intent'] or 0,
            }
            
        except Exception as e:
            print(f"[数据库] 获取潜在用户统计失败: {e}")
            conn.close()
            return {
                'total': 0,
                'pending': 0,
                'contacted': 0,
                'converted': 0,
                'failed': 0,
                'high_intent': 0,
                'medium_intent': 0,
                'low_intent': 0,
            }
