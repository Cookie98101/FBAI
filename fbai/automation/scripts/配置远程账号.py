"""
远程账号配置工具

用于配置远程账号功能
"""

import sys
import os

# 添加路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from 远程账号管理 import 配置远程账号, 测试远程连接, 读取远程配置


def main():
    print("=" * 60)
    print("远程账号配置工具")
    print("=" * 60)
    print()
    
    # 显示当前配置
    config = 读取远程配置()
    print("当前配置:")
    print(f"  启用状态: {config.get('enabled', False)}")
    print(f"  服务器: {config.get('server_url', 'N/A')}")
    print(f"  用户名: {config.get('username', 'N/A')}")
    print(f"  最后同步: {config.get('last_sync', 'N/A')}")
    print()
    
    # 询问是否要修改配置
    choice = input("是否要修改配置？(y/n): ").strip().lower()
    
    if choice != 'y':
        print("退出配置")
        return
    
    print()
    print("请输入配置信息:")
    print()
    
    # 输入服务器地址
    server_url = input(f"服务器地址 [{config.get('server_url', 'http://43.142.176.53:8805')}]: ").strip()
    if not server_url:
        server_url = config.get('server_url', 'http://43.142.176.53:8805')
    
    # 输入用户名
    username = input(f"用户名 [{config.get('username', '')}]: ").strip()
    if not username:
        username = config.get('username', '')
    
    if not username:
        print()
        print("❌ 用户名不能为空")
        return
    
    # 询问是否启用
    enabled_input = input("是否启用远程账号功能？(y/n) [y]: ").strip().lower()
    enabled = enabled_input != 'n'
    
    print()
    print("正在保存配置...")
    
    # 保存配置
    配置远程账号(server_url, username, enabled)
    
    print()
    print("✓ 配置已保存")
    print()
    
    # 测试连接
    test_choice = input("是否测试连接？(y/n) [y]: ").strip().lower()
    
    if test_choice != 'n':
        print()
        print("正在测试连接...")
        print()
        
        if 测试远程连接(server_url, username):
            print()
            print("✓ 连接测试成功！")
            print()
            print("现在可以使用远程账号功能了。")
            print("当本地 账号.txt 为空时，系统会自动从远程获取账号。")
        else:
            print()
            print("✗ 连接测试失败")
            print()
            print("请检查:")
            print("  1. 服务器地址是否正确")
            print("  2. 用户名是否正确")
            print("  3. 网络连接是否正常")
            print("  4. 服务器是否已部署")
    
    print()
    print("=" * 60)


if __name__ == "__main__":
    main()
