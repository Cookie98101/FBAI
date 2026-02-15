#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据库迁移：添加小组互动记录表

用途：
- 记录每次小组互动的详细信息
- 支持互动数据统计和分析
- 配合小组互动加权模块使用
"""

import sqlite3
import os
import sys

# 添加项目根目录到路径
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(current_dir))))
sys.path.insert(0, project_root)

from automation.scripts.database.db import Database


def migrate():
    """执行迁移"""
    print("=" * 60)
    print("数据库迁移：添加小组互动记录表")
    print("=" * 60)
    
    try:
        db = Database()
        conn = db.get_connection()
        cursor = conn.cursor()
        
        # 1. 创建 groups 表（用于小组互动加权模块）
        print("\n1. 创建 groups 表...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS groups (
                group_url TEXT PRIMARY KEY,
                group_name TEXT,
                joined_date TEXT,
                last_interaction_date TEXT,
                member_count INTEGER,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        print("   ✓ 表创建成功")
        
        # 2. 创建 group_interactions 表
        print("\n2. 创建 group_interactions 表...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS group_interactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                group_url TEXT NOT NULL,
                interaction_date TEXT NOT NULL,
                interaction_type TEXT NOT NULL,
                
                -- 阅读相关
                posts_read INTEGER DEFAULT 0,
                read_duration INTEGER DEFAULT 0,
                comments_expanded INTEGER DEFAULT 0,
                
                -- 互动相关
                likes INTEGER DEFAULT 0,
                comments INTEGER DEFAULT 0,
                replies INTEGER DEFAULT 0,
                posts INTEGER DEFAULT 0,
                
                -- 详细信息
                content TEXT,
                group_stage INTEGER,
                
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                
                FOREIGN KEY (group_url) REFERENCES groups(group_url)
            )
        """)
        print("   ✓ 表创建成功")
        
        # 3. 创建索引
        print("\n3. 创建索引...")
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_groups_joined_date 
            ON groups(joined_date)
        """)
        print("   ✓ 索引 idx_groups_joined_date 创建成功")
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_groups_last_interaction 
            ON groups(last_interaction_date)
        """)
        print("   ✓ 索引 idx_groups_last_interaction 创建成功")
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_group_interactions_url 
            ON group_interactions(group_url)
        """)
        print("   ✓ 索引 idx_group_interactions_url 创建成功")
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_group_interactions_date 
            ON group_interactions(interaction_date)
        """)
        print("   ✓ 索引 idx_group_interactions_date 创建成功")
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_group_interactions_type 
            ON group_interactions(interaction_type)
        """)
        print("   ✓ 索引 idx_group_interactions_type 创建成功")
        
        # 4. 从 account_groups 迁移数据到 groups（如果有数据）
        print("\n4. 迁移现有小组数据...")
        cursor.execute("""
            INSERT OR IGNORE INTO groups (group_url, group_name, joined_date, member_count)
            SELECT 
                'https://www.facebook.com/groups/' || group_id || '/' as group_url,
                group_name,
                DATE(joined_at) as joined_date,
                member_count
            FROM account_groups
            WHERE status = 'active'
        """)
        migrated_count = cursor.rowcount
        print(f"   ✓ 迁移了 {migrated_count} 个小组")
        
        # 5. 提交更改
        conn.commit()
        conn.close()
        
        print("\n" + "=" * 60)
        print("✓ 迁移完成！")
        print("=" * 60)
        print("\n新增表：")
        print("  - groups: 小组基础信息表")
        print("  - group_interactions: 小组互动记录表")
        print("\n新增索引：")
        print("  - idx_groups_joined_date")
        print("  - idx_groups_last_interaction")
        print("  - idx_group_interactions_url")
        print("  - idx_group_interactions_date")
        print("  - idx_group_interactions_type")
        
        return True
        
    except Exception as e:
        print(f"\n✗ 迁移失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def rollback():
    """回滚迁移"""
    print("=" * 60)
    print("回滚迁移：删除小组互动记录表")
    print("=" * 60)
    
    try:
        db = Database()
        conn = db.get_connection()
        cursor = conn.cursor()
        
        # 删除表
        cursor.execute("DROP TABLE IF EXISTS group_interactions")
        print("✓ 表 group_interactions 已删除")
        
        cursor.execute("DROP TABLE IF EXISTS groups")
        print("✓ 表 groups 已删除")
        
        conn.commit()
        conn.close()
        
        print("\n✓ 回滚完成！")
        return True
        
    except Exception as e:
        print(f"\n✗ 回滚失败: {e}")
        return False


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "rollback":
        rollback()
    else:
        migrate()
