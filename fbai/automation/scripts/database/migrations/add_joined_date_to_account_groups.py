"""
数据库迁移：为 account_groups 表添加 joined_date 字段

用途：
- 统计每日加入小组数量
- 支持每日配额限制
"""

import sqlite3
import os

def migrate():
    """执行迁移"""
    # 数据库路径
    db_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
        "data",
        "facebook_automation.db"
    )
    
    if not os.path.exists(db_path):
        print(f"数据库文件不存在: {db_path}")
        return False
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # 检查字段是否已存在
        cursor.execute("PRAGMA table_info(account_groups)")
        columns = [row[1] for row in cursor.fetchall()]
        
        if 'joined_date' in columns:
            print("✓ joined_date 字段已存在，跳过迁移")
            conn.close()
            return True
        
        print("开始迁移：添加 joined_date 字段...")
        
        # 1. 添加 joined_date 字段
        cursor.execute('''
            ALTER TABLE account_groups 
            ADD COLUMN joined_date DATE
        ''')
        
        print("✓ 已添加 joined_date 字段")
        
        # 2. 更新现有数据（从 joined_at 提取日期）
        cursor.execute('''
            UPDATE account_groups 
            SET joined_date = DATE(joined_at)
            WHERE joined_date IS NULL
        ''')
        
        updated_count = cursor.rowcount
        print(f"✓ 已更新 {updated_count} 条现有记录")
        
        conn.commit()
        print("✓ 迁移完成")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"✗ 迁移失败: {e}")
        conn.rollback()
        conn.close()
        return False

if __name__ == "__main__":
    print("=" * 60)
    print("数据库迁移：添加 joined_date 字段")
    print("=" * 60)
    migrate()
