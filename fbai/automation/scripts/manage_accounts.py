"""
账号管理工具
用于添加、查看、更新账号信息
"""

import os
import sys

# 添加项目根目录到路径
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

from database.db import Database


def show_menu():
    """显示菜单"""
    print("\n" + "=" * 60)
    print("账号管理工具")
    print("=" * 60)
    print("1. 查看所有账号")
    print("2. 添加账号")
    print("3. 更新账号状态")
    print("4. 查看账号统计")
    print("5. 删除测试数据")
    print("0. 退出")
    print("=" * 60)


def list_accounts(db: Database):
    """查看所有账号"""
    accounts = db.get_all_accounts()
    
    if not accounts:
        print("\n暂无账号数据")
        return
    
    print(f"\n共有 {len(accounts)} 个账号：")
    print("-" * 100)
    print(f"{'ID':<5} {'浏览器ID':<25} {'用户名':<15} {'状态':<10} {'任务数':<8} {'点赞数':<8} {'评论数':<8}")
    print("-" * 100)
    
    for acc in accounts:
        print(f"{acc['id']:<5} {acc['browser_id']:<25} {acc['username'] or '未设置':<15} "
              f"{acc['status']:<10} {acc['total_tasks']:<8} {acc['total_likes']:<8} {acc['total_comments']:<8}")
    
    print("-" * 100)


def add_account(db: Database):
    """添加账号"""
    print("\n添加新账号")
    print("-" * 60)
    
    browser_id = input("浏览器ID (必填): ").strip()
    if not browser_id:
        print("❌ 浏览器ID不能为空")
        return
    
    # 检查是否已存在
    existing = db.get_account_by_browser_id(browser_id)
    if existing:
        print(f"⚠️ 账号已存在: {existing['username'] or browser_id}")
        update = input("是否更新？(y/n): ").strip().lower()
        if update != 'y':
            return
    
    username = input("用户名 (可选): ").strip() or None
    password = input("密码 (可选): ").strip() or None
    cookie = input("Cookie (可选): ").strip() or None
    
    try:
        account_id = db.add_account(browser_id, username, password, cookie)
        print(f"✓ 账号已添加，ID: {account_id}")
    except Exception as e:
        print(f"❌ 添加失败: {e}")


def update_account_status(db: Database):
    """更新账号状态"""
    print("\n更新账号状态")
    print("-" * 60)
    
    browser_id = input("浏览器ID: ").strip()
    if not browser_id:
        print("❌ 浏览器ID不能为空")
        return
    
    account = db.get_account_by_browser_id(browser_id)
    if not account:
        print(f"❌ 账号不存在: {browser_id}")
        return
    
    print(f"\n当前状态: {account['status']}")
    print("可选状态: active (活跃), banned (封号), restricted (受限)")
    
    new_status = input("新状态: ").strip()
    if new_status not in ['active', 'banned', 'restricted']:
        print("❌ 无效的状态")
        return
    
    try:
        db.update_account_status(browser_id, new_status)
        print(f"✓ 状态已更新: {new_status}")
    except Exception as e:
        print(f"❌ 更新失败: {e}")


def show_account_stats(db: Database):
    """查看账号统计"""
    print("\n账号统计")
    print("-" * 60)
    
    browser_id = input("浏览器ID: ").strip()
    if not browser_id:
        print("❌ 浏览器ID不能为空")
        return
    
    account = db.get_account_by_browser_id(browser_id)
    if not account:
        print(f"❌ 账号不存在: {browser_id}")
        return
    
    stats = db.get_account_stats(account['id'])
    
    print(f"\n账号信息:")
    print(f"  浏览器ID: {account['browser_id']}")
    print(f"  用户名: {account['username'] or '未设置'}")
    print(f"  状态: {account['status']}")
    print(f"  创建时间: {account['created_at']}")
    print(f"  最后登录: {account['last_login_at'] or '从未登录'}")
    
    print(f"\n总计统计:")
    print(f"  总任务数: {account['total_tasks']}")
    print(f"  总点赞数: {account['total_likes']}")
    print(f"  总评论数: {account['total_comments']}")
    
    print(f"\n今日统计:")
    print(f"  今日互动: {stats['today']['interactions']}")
    print(f"  今日点赞: {stats['today']['likes']}")
    print(f"  今日评论: {stats['today']['comments']}")
    print(f"  今日任务: {stats['today']['tasks']}")


def delete_test_data(db: Database):
    """删除测试数据"""
    print("\n删除测试数据")
    print("-" * 60)
    print("⚠️ 警告: 这将删除所有测试账号数据")
    
    confirm = input("确认删除？(输入 'yes' 确认): ").strip()
    if confirm != 'yes':
        print("已取消")
        return
    
    try:
        conn = db.get_connection()
        cursor = conn.cursor()
        
        # 删除测试账号
        cursor.execute("DELETE FROM accounts WHERE browser_id LIKE 'test_%'")
        deleted_accounts = cursor.rowcount
        
        # 删除相关的任务和互动记录会自动级联删除（如果设置了外键）
        
        conn.commit()
        conn.close()
        
        print(f"✓ 已删除 {deleted_accounts} 个测试账号")
    except Exception as e:
        print(f"❌ 删除失败: {e}")


def main():
    """主函数"""
    db = Database()
    
    while True:
        show_menu()
        choice = input("\n请选择操作 (0-5): ").strip()
        
        if choice == '0':
            print("\n再见！")
            break
        elif choice == '1':
            list_accounts(db)
        elif choice == '2':
            add_account(db)
        elif choice == '3':
            update_account_status(db)
        elif choice == '4':
            show_account_stats(db)
        elif choice == '5':
            delete_test_data(db)
        else:
            print("\n❌ 无效的选择")
        
        input("\n按回车继续...")


if __name__ == "__main__":
    main()
