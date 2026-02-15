"""
黑名单小组管理工具
用于管理不精准小组黑名单（rejected_groups表）

功能：
1. 添加小组到黑名单（通过链接或ID）
2. 从黑名单移除小组
3. 查看黑名单列表
4. 批量导入黑名单
5. 清空黑名单
"""

import os
import sys
import re
from typing import List, Dict

# ==================== 路径设置 ====================
current_dir = os.path.dirname(os.path.abspath(__file__))
scripts_dir = os.path.dirname(current_dir)
database_dir = os.path.join(scripts_dir, "database")

for path in [current_dir, scripts_dir, database_dir]:
    if path not in sys.path:
        sys.path.insert(0, path)

# 导入数据库
from db import Database

# 初始化数据库
db = Database()

# ==================== 工具函数 ====================

def 提取小组ID(小组链接: str) -> str:
    """
    从小组链接中提取小组ID
    
    Args:
        小组链接: Facebook小组链接
    
    Returns:
        小组ID
    """
    # 格式1: https://www.facebook.com/groups/123456789
    # 格式2: https://www.facebook.com/groups/group_name
    match = re.search(r'/groups/([^/?]+)', 小组链接)
    if match:
        return match.group(1)
    
    # 如果不是链接，直接返回（可能已经是ID）
    return 小组链接

def 添加到黑名单(小组标识: str, 小组名称: str = None, 原因: str = None) -> bool:
    """
    添加小组到黑名单
    
    Args:
        小组标识: 小组链接或ID
        小组名称: 小组名称（可选）
        原因: 添加原因（可选）
    
    Returns:
        是否成功
    """
    小组ID = 提取小组ID(小组标识)
    
    # 检查是否已在黑名单中
    if db.is_group_rejected(小组ID):
        print(f"⚠ 小组已在黑名单中: {小组ID}")
        return False
    
    # 添加到黑名单
    成功 = db.reject_group(
        group_id=小组ID,
        group_name=小组名称,
        reject_reason=原因 or "手动添加"
    )
    
    if 成功:
        print(f"✓ 已添加到黑名单: {小组ID}")
        if 小组名称:
            print(f"  名称: {小组名称}")
        if 原因:
            print(f"  原因: {原因}")
    else:
        print(f"✗ 添加失败: {小组ID}")
    
    return 成功

def 从黑名单移除(小组标识: str) -> bool:
    """
    从黑名单移除小组
    
    Args:
        小组标识: 小组链接或ID
    
    Returns:
        是否成功
    """
    小组ID = 提取小组ID(小组标识)
    
    # 检查是否在黑名单中
    if not db.is_group_rejected(小组ID):
        print(f"⚠ 小组不在黑名单中: {小组ID}")
        return False
    
    # 从黑名单移除
    成功 = db.remove_rejected_group(小组ID)
    
    if 成功:
        print(f"✓ 已从黑名单移除: {小组ID}")
    else:
        print(f"✗ 移除失败: {小组ID}")
    
    return 成功

def 查看黑名单(限制数量: int = 50, 显示详情: bool = True) -> List[Dict]:
    """
    查看黑名单列表
    
    Args:
        限制数量: 返回数量限制
        显示详情: 是否显示详细信息
    
    Returns:
        黑名单列表
    """
    黑名单列表 = db.get_all_rejected_groups(limit=限制数量)
    
    if not 黑名单列表:
        print("黑名单为空")
        return []
    
    print(f"\n黑名单小组列表（共 {len(黑名单列表)} 个）")
    print("=" * 80)
    
    for i, 小组 in enumerate(黑名单列表, 1):
        print(f"\n{i}. 小组ID: {小组['group_id']}")
        
        if 显示详情:
            if 小组['group_name']:
                print(f"   名称: {小组['group_name']}")
            if 小组['reject_reason']:
                print(f"   原因: {小组['reject_reason']}")
            print(f"   添加时间: {小组['rejected_at']}")
    
    print("\n" + "=" * 80)
    
    return 黑名单列表

def 批量添加到黑名单(小组列表: List[str], 原因: str = None) -> int:
    """
    批量添加小组到黑名单
    
    Args:
        小组列表: 小组链接或ID列表
        原因: 添加原因
    
    Returns:
        成功添加的数量
    """
    成功数量 = 0
    失败数量 = 0
    
    print(f"\n开始批量添加 {len(小组列表)} 个小组到黑名单...")
    print("-" * 80)
    
    for i, 小组标识 in enumerate(小组列表, 1):
        print(f"\n[{i}/{len(小组列表)}] 处理: {小组标识}")
        
        if 添加到黑名单(小组标识, 原因=原因):
            成功数量 += 1
        else:
            失败数量 += 1
    
    print("\n" + "-" * 80)
    print(f"批量添加完成:")
    print(f"  成功: {成功数量} 个")
    print(f"  失败: {失败数量} 个")
    
    return 成功数量

def 从文件导入黑名单(文件路径: str, 原因: str = None) -> int:
    """
    从文件导入黑名单（每行一个小组链接或ID）
    
    Args:
        文件路径: 文件路径
        原因: 添加原因
    
    Returns:
        成功添加的数量
    """
    if not os.path.exists(文件路径):
        print(f"✗ 文件不存在: {文件路径}")
        return 0
    
    try:
        with open(文件路径, 'r', encoding='utf-8') as f:
            小组列表 = [line.strip() for line in f if line.strip()]
        
        print(f"从文件读取到 {len(小组列表)} 个小组")
        
        return 批量添加到黑名单(小组列表, 原因=原因)
    
    except Exception as e:
        print(f"✗ 读取文件失败: {e}")
        return 0

def 导出黑名单到文件(文件路径: str) -> bool:
    """
    导出黑名单到文件
    
    Args:
        文件路径: 文件路径
    
    Returns:
        是否成功
    """
    try:
        黑名单列表 = db.get_all_rejected_groups(limit=10000)
        
        if not 黑名单列表:
            print("黑名单为空，无需导出")
            return False
        
        with open(文件路径, 'w', encoding='utf-8') as f:
            for 小组 in 黑名单列表:
                # 格式: 小组ID | 小组名称 | 原因 | 时间
                f.write(f"{小组['group_id']}")
                if 小组['group_name']:
                    f.write(f" | {小组['group_name']}")
                if 小组['reject_reason']:
                    f.write(f" | {小组['reject_reason']}")
                f.write(f" | {小组['rejected_at']}")
                f.write("\n")
        
        print(f"✓ 已导出 {len(黑名单列表)} 个小组到: {文件路径}")
        return True
    
    except Exception as e:
        print(f"✗ 导出失败: {e}")
        return False

def 清空黑名单() -> bool:
    """
    清空黑名单（危险操作，需要确认）
    
    Returns:
        是否成功
    """
    黑名单列表 = db.get_all_rejected_groups(limit=10000)
    
    if not 黑名单列表:
        print("黑名单已经为空")
        return True
    
    print(f"\n⚠ 警告：即将清空黑名单（共 {len(黑名单列表)} 个小组）")
    确认 = input("请输入 'YES' 确认清空: ").strip()
    
    if 确认 != 'YES':
        print("已取消")
        return False
    
    try:
        conn = db.get_connection()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM rejected_groups')
        conn.commit()
        conn.close()
        
        print(f"✓ 已清空黑名单（删除了 {len(黑名单列表)} 个小组）")
        return True
    
    except Exception as e:
        print(f"✗ 清空失败: {e}")
        return False

def 搜索黑名单(关键词: str) -> List[Dict]:
    """
    搜索黑名单（按名称或ID）
    
    Args:
        关键词: 搜索关键词
    
    Returns:
        匹配的小组列表
    """
    黑名单列表 = db.get_all_rejected_groups(limit=10000)
    
    匹配列表 = [
        小组 for 小组 in 黑名单列表
        if 关键词.lower() in 小组['group_id'].lower()
        or (小组['group_name'] and 关键词.lower() in 小组['group_name'].lower())
    ]
    
    if not 匹配列表:
        print(f"未找到匹配的小组: {关键词}")
        return []
    
    print(f"\n搜索结果（共 {len(匹配列表)} 个）")
    print("=" * 80)
    
    for i, 小组 in enumerate(匹配列表, 1):
        print(f"\n{i}. 小组ID: {小组['group_id']}")
        if 小组['group_name']:
            print(f"   名称: {小组['group_name']}")
        if 小组['reject_reason']:
            print(f"   原因: {小组['reject_reason']}")
        print(f"   添加时间: {小组['rejected_at']}")
    
    print("\n" + "=" * 80)
    
    return 匹配列表

def 显示统计信息():
    """显示黑名单统计信息"""
    统计 = db.get_rejected_groups_stats()
    
    print("\n黑名单统计信息")
    print("=" * 80)
    print(f"总数: {统计['total']} 个")
    print(f"今日新增: {统计['today']} 个")
    print("=" * 80)

# ==================== 交互式菜单 ====================

def 显示菜单():
    """显示主菜单"""
    print("\n" + "=" * 80)
    print("黑名单小组管理工具")
    print("=" * 80)
    print("1. 添加小组到黑名单")
    print("2. 从黑名单移除小组")
    print("3. 查看黑名单列表")
    print("4. 搜索黑名单")
    print("5. 批量添加到黑名单")
    print("6. 从文件导入黑名单")
    print("7. 导出黑名单到文件")
    print("8. 显示统计信息")
    print("9. 清空黑名单（危险）")
    print("0. 退出")
    print("=" * 80)

def 主循环():
    """主循环"""
    while True:
        显示菜单()
        
        选择 = input("\n请选择操作 (0-9): ").strip()
        
        if 选择 == "0":
            print("再见！")
            break
        
        elif 选择 == "1":
            # 添加小组到黑名单
            print("\n添加小组到黑名单")
            print("-" * 80)
            小组标识 = input("请输入小组链接或ID: ").strip()
            if 小组标识:
                小组名称 = input("请输入小组名称（可选，直接回车跳过）: ").strip() or None
                原因 = input("请输入添加原因（可选，直接回车跳过）: ").strip() or None
                添加到黑名单(小组标识, 小组名称, 原因)
        
        elif 选择 == "2":
            # 从黑名单移除小组
            print("\n从黑名单移除小组")
            print("-" * 80)
            小组标识 = input("请输入小组链接或ID: ").strip()
            if 小组标识:
                从黑名单移除(小组标识)
        
        elif 选择 == "3":
            # 查看黑名单列表
            print("\n查看黑名单列表")
            print("-" * 80)
            限制数量 = input("请输入显示数量（默认50）: ").strip()
            限制数量 = int(限制数量) if 限制数量.isdigit() else 50
            查看黑名单(限制数量=限制数量)
        
        elif 选择 == "4":
            # 搜索黑名单
            print("\n搜索黑名单")
            print("-" * 80)
            关键词 = input("请输入搜索关键词: ").strip()
            if 关键词:
                搜索黑名单(关键词)
        
        elif 选择 == "5":
            # 批量添加到黑名单
            print("\n批量添加到黑名单")
            print("-" * 80)
            print("请输入小组链接或ID（每行一个，输入空行结束）:")
            小组列表 = []
            while True:
                行 = input().strip()
                if not 行:
                    break
                小组列表.append(行)
            
            if 小组列表:
                原因 = input("请输入添加原因（可选，直接回车跳过）: ").strip() or None
                批量添加到黑名单(小组列表, 原因=原因)
        
        elif 选择 == "6":
            # 从文件导入黑名单
            print("\n从文件导入黑名单")
            print("-" * 80)
            文件路径 = input("请输入文件路径: ").strip()
            if 文件路径:
                原因 = input("请输入添加原因（可选，直接回车跳过）: ").strip() or None
                从文件导入黑名单(文件路径, 原因=原因)
        
        elif 选择 == "7":
            # 导出黑名单到文件
            print("\n导出黑名单到文件")
            print("-" * 80)
            文件路径 = input("请输入文件路径: ").strip()
            if 文件路径:
                导出黑名单到文件(文件路径)
        
        elif 选择 == "8":
            # 显示统计信息
            显示统计信息()
        
        elif 选择 == "9":
            # 清空黑名单
            清空黑名单()
        
        else:
            print("无效选项，请重新选择")
        
        input("\n按回车键继续...")

# ==================== 入口 ====================

if __name__ == "__main__":
    try:
        主循环()
    except KeyboardInterrupt:
        print("\n\n已中断")
    except Exception as e:
        print(f"\n✗ 发生错误: {e}")
        import traceback
        traceback.print_exc()

