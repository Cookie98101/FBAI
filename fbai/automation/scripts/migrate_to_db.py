"""
数据迁移脚本
将 JSON 文件中的数据迁移到 SQLite 数据库
"""

import os
import sys

# 添加项目根目录到路径
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

from database.db import Database


def migrate():
    """执行数据迁移"""
    print("=" * 60)
    print("数据迁移工具 - JSON 到 SQLite")
    print("=" * 60)
    
    # 初始化数据库
    db = Database()
    print(f"✓ 数据库已初始化: {db.db_path}")
    
    # 迁移账号数据
    json_file = os.path.join(current_dir, '脚本配置', '账号.txt')
    if os.path.exists(json_file):
        print(f"\n正在迁移账号数据: {json_file}")
        db.migrate_from_json(json_file)
    else:
        print(f"\n⚠️ 账号文件不存在: {json_file}")
    
    # 显示迁移结果
    print("\n" + "=" * 60)
    print("迁移完成！数据库统计：")
    print("=" * 60)
    
    accounts = db.get_all_accounts()
    print(f"总账号数: {len(accounts)}")
    print(f"活跃账号: {len([a for a in accounts if a['status'] == 'active'])}")
    
    if accounts:
        print("\n账号列表：")
        for acc in accounts[:10]:  # 只显示前10个
            print(f"  - {acc['browser_id']}: {acc['username'] or '未设置用户名'} ({acc['status']})")
        
        if len(accounts) > 10:
            print(f"  ... 还有 {len(accounts) - 10} 个账号")
    
    print("\n" + "=" * 60)
    print("✓ 迁移完成！")
    print(f"数据库文件: {db.db_path}")
    print("=" * 60)


if __name__ == "__main__":
    migrate()
