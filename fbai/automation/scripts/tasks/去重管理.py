"""
去重管理模块
用于记录和检查已操作过的帖子，避免重复操作

功能：
- 记录已评论/点赞的帖子ID和时间
- 检查帖子是否在指定时间内操作过
- 自动清理过期记录
- **全局去重**：多个账号共用记录，避免重复操作同一帖子
- 支持不同操作类型（评论、点赞等）

数据结构：
{
    "comment": {
        "帖子ID": "2024-01-15 10:30:00",
        ...
    },
    "like": {
        "帖子ID": "2024-01-15 10:30:00",
        ...
    }
}
"""

import os
import json
import re
from datetime import datetime, timedelta
from typing import Optional, Set

# ==================== 配置 ====================

# 去重记录文件路径
current_dir = os.path.dirname(os.path.abspath(__file__))
scripts_dir = os.path.dirname(current_dir)
去重记录目录 = os.path.join(scripts_dir, "脚本配置", "去重记录")
去重记录文件 = os.path.join(去重记录目录, "全局操作记录.json")

# 默认去重时间（天）
默认去重天数 = 15

# ==================== 工具函数 ====================

def 确保目录存在():
    """确保去重记录目录存在"""
    if not os.path.exists(去重记录目录):
        os.makedirs(去重记录目录)

def 加载记录() -> dict:
    """
    加载去重记录
    
    Returns:
        记录字典
    """
    确保目录存在()
    
    if not os.path.exists(去重记录文件):
        return {}
    
    try:
        with open(去重记录文件, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return {}

def 保存记录(记录: dict):
    """
    保存去重记录
    
    Args:
        记录: 记录字典
    """
    确保目录存在()
    
    try:
        with open(去重记录文件, 'w', encoding='utf-8') as f:
            json.dump(记录, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[去重] 保存记录失败: {e}")

def 清理过期记录(记录: dict, 保留天数: int = 默认去重天数) -> dict:
    """
    清理过期的记录
    
    Args:
        记录: 记录字典
        保留天数: 保留多少天内的记录
    
    Returns:
        清理后的记录
    """
    截止时间 = datetime.now() - timedelta(days=保留天数)
    截止时间字符串 = 截止时间.strftime("%Y-%m-%d %H:%M:%S")
    
    清理数量 = 0
    
    for 操作类型 in list(记录.keys()):
        操作记录 = 记录[操作类型]
        
        # 过滤掉过期的记录
        过期的帖子 = []
        for 帖子ID, 时间字符串 in 操作记录.items():
            if 时间字符串 < 截止时间字符串:
                过期的帖子.append(帖子ID)
        
        # 删除过期记录
        for 帖子ID in 过期的帖子:
            del 操作记录[帖子ID]
            清理数量 += 1
        
        # 如果操作类型为空，删除
        if not 操作记录:
            del 记录[操作类型]
    
    if 清理数量 > 0:
        print(f"[去重] 清理了 {清理数量} 条过期记录")
    
    return 记录

def 提取帖子ID(链接或元素) -> Optional[str]:
    """
    从链接或元素中提取 Facebook 帖子ID
    
    支持的格式：
    - fbid=数字
    - /posts/数字
    - /permalink/数字
    - /reel/数字
    - /videos/数字
    - story_fbid=数字
    - pfbid开头的字符串
    
    Args:
        链接或元素: URL字符串或 WebElement
    
    Returns:
        帖子ID，如果提取失败返回 None
    """
    try:
        # 如果是 WebElement，获取 href
        if hasattr(链接或元素, 'get_attribute'):
            链接 = 链接或元素.get_attribute('href') or ""
        else:
            链接 = str(链接或元素)
        
        if not 链接:
            return None
        
        # 方法1: 提取 fbid=数字
        match = re.search(r'fbid=(\d+)', 链接)
        if match:
            return match.group(1)
        
        # 方法2: 提取 /posts/数字
        match = re.search(r'/posts/(\d+)', 链接)
        if match:
            return match.group(1)
        
        # 方法3: 提取 /reel/数字
        match = re.search(r'/reel/(\d+)', 链接)
        if match:
            return match.group(1)
        
        # 方法4: 提取 /videos/数字
        match = re.search(r'/videos/(\d+)', 链接)
        if match:
            return match.group(1)
        
        # 方法5: 提取 /permalink/数字
        match = re.search(r'/permalink/(\d+)', 链接)
        if match:
            return match.group(1)
        
        # 方法6: 提取 story_fbid=数字
        match = re.search(r'story_fbid=(\d+)', 链接)
        if match:
            return match.group(1)
        
        # 方法7: 提取 pfbid 开头的字符串
        match = re.search(r'(pfbid[A-Za-z0-9]+)', 链接)
        if match:
            return match.group(1)
        
        return None
        
    except:
        return None

def 从元素查找帖子ID(元素, driver=None) -> Optional[str]:
    """
    从元素向上查找父元素中的帖子链接，提取帖子ID
    
    Args:
        元素: WebElement（通常是帖子内容元素）
        driver: WebDriver实例（可选）
    
    Returns:
        帖子ID，如果找不到返回 None
    """
    try:
        from selenium.webdriver.common.by import By
        
        # 向上查找最多10层父元素
        当前元素 = 元素
        for level in range(10):
            try:
                # 在当前层级查找所有链接
                links = 当前元素.find_elements(By.CSS_SELECTOR, "a[href]")
                
                for link in links:
                    帖子ID = 提取帖子ID(link)
                    if 帖子ID:
                        return 帖子ID
                
                # 向上一层
                当前元素 = 当前元素.find_element(By.XPATH, "..")
            except:
                break
        
        return None
        
    except:
        return None

# ==================== 主要接口 ====================

def 检查是否已操作(帖子ID: str, 操作类型: str = "comment", 
                  去重天数: int = 默认去重天数) -> bool:
    """
    检查帖子是否在指定时间内已操作过（全局检查，不区分账号）
    
    Args:
        帖子ID: 帖子唯一标识
        操作类型: 操作类型（comment/like/share等）
        去重天数: 去重时间范围（天）
    
    Returns:
        True: 已操作过（需要跳过）
        False: 未操作过（可以操作）
    """
    记录 = 加载记录()
    
    # 检查操作类型是否存在
    if 操作类型 not in 记录:
        return False
    
    操作记录 = 记录[操作类型]
    
    # 检查帖子是否存在
    if 帖子ID not in 操作记录:
        return False
    
    # 检查时间是否在范围内
    操作时间字符串 = 操作记录[帖子ID]
    try:
        操作时间 = datetime.strptime(操作时间字符串, "%Y-%m-%d %H:%M:%S")
        当前时间 = datetime.now()
        时间差 = 当前时间 - 操作时间
        
        if 时间差.days < 去重天数:
            return True  # 在去重时间内，已操作过
        else:
            return False  # 超过去重时间，可以重新操作
    except:
        return False

def 记录操作(帖子ID: str, 操作类型: str = "comment"):
    """
    记录一次操作（全局记录，不区分账号）
    
    Args:
        帖子ID: 帖子唯一标识
        操作类型: 操作类型（comment/like/share等）
    """
    记录 = 加载记录()
    
    # 确保操作类型记录存在
    if 操作类型 not in 记录:
        记录[操作类型] = {}
    
    操作记录 = 记录[操作类型]
    
    # 记录当前时间
    当前时间 = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    操作记录[帖子ID] = 当前时间
    
    # 保存记录
    保存记录(记录)

def 获取已操作帖子集合(操作类型: str = "comment", 
                    去重天数: int = 默认去重天数) -> Set[str]:
    """
    获取指定时间内已操作过的帖子ID集合（全局）
    
    Args:
        操作类型: 操作类型（comment/like/share等）
        去重天数: 去重时间范围（天）
    
    Returns:
        帖子ID集合
    """
    记录 = 加载记录()
    
    if 操作类型 not in 记录:
        return set()
    
    操作记录 = 记录[操作类型]
    
    # 过滤出在时间范围内的帖子
    截止时间 = datetime.now() - timedelta(days=去重天数)
    截止时间字符串 = 截止时间.strftime("%Y-%m-%d %H:%M:%S")
    
    有效帖子集合 = set()
    for 帖子ID, 时间字符串 in 操作记录.items():
        if 时间字符串 >= 截止时间字符串:
            有效帖子集合.add(帖子ID)
    
    return 有效帖子集合

def 清理所有过期记录(保留天数: int = 默认去重天数):
    """
    清理所有过期记录
    
    Args:
        保留天数: 保留多少天内的记录
    """
    记录 = 加载记录()
    记录 = 清理过期记录(记录, 保留天数)
    保存记录(记录)

def 获取统计信息() -> dict:
    """
    获取全局操作统计信息
    
    Returns:
        统计信息字典
    """
    记录 = 加载记录()
    
    统计 = {
        "总操作数": 0,
        "操作类型": {}
    }
    
    for 操作类型, 操作记录 in 记录.items():
        数量 = len(操作记录)
        统计["操作类型"][操作类型] = 数量
        统计["总操作数"] += 数量
    
    return 统计

# ==================== 调试和测试 ====================

def _测试():
    """测试去重功能"""
    print("=" * 60)
    print("去重管理 - 测试（全局去重）")
    print("=" * 60)
    
    # 1. 测试提取帖子ID
    print("\n1. 测试提取帖子ID")
    测试链接列表 = [
        "https://www.facebook.com/photo/?fbid=1477308121071179&set=a.535132401955427",
        "https://www.facebook.com/posts/123456789",
        "https://www.facebook.com/permalink/987654321",
        "https://www.facebook.com/story.php?story_fbid=111222333",
    ]
    
    for 链接 in 测试链接列表:
        帖子ID = 提取帖子ID(链接)
        print(f"链接: {链接[:60]}...")
        print(f"  → 帖子ID: {帖子ID}\n")
    
    # 2. 记录操作
    print("\n2. 记录操作（全局）")
    记录操作("1477308121071179", "comment")
    print(f"✓ 已记录评论: 1477308121071179")
    
    记录操作("123456789", "like")
    print(f"✓ 已记录点赞: 123456789")
    
    # 3. 检查是否已操作
    print("\n3. 检查是否已操作（全局）")
    已评论1 = 检查是否已操作("1477308121071179", "comment")
    已点赞1 = 检查是否已操作("1477308121071179", "like")
    已评论2 = 检查是否已操作("123456789", "comment")
    已点赞2 = 检查是否已操作("123456789", "like")
    
    print(f"帖子 1477308121071179 已评论: {已评论1} (应该是 True)")
    print(f"帖子 1477308121071179 已点赞: {已点赞1} (应该是 False)")
    print(f"帖子 123456789 已评论: {已评论2} (应该是 False)")
    print(f"帖子 123456789 已点赞: {已点赞2} (应该是 True)")
    
    # 4. 获取已操作帖子集合
    print("\n4. 获取已操作帖子集合（全局）")
    已评论集合 = 获取已操作帖子集合("comment")
    已点赞集合 = 获取已操作帖子集合("like")
    print(f"已评论帖子数: {len(已评论集合)}")
    print(f"已点赞帖子数: {len(已点赞集合)}")
    
    # 5. 获取统计信息
    print("\n5. 获取统计信息（全局）")
    统计 = 获取统计信息()
    print(f"总操作数: {统计['总操作数']}")
    print(f"操作类型: {统计['操作类型']}")
    
    # 6. 清理过期记录
    print("\n6. 清理过期记录")
    清理所有过期记录(保留天数=15)
    
    print("\n" + "=" * 60)
    print("测试完成！")
    print(f"记录文件位置: {去重记录文件}")
    print("=" * 60)
    print("\n说明：")
    print("- 全局去重：所有账号共用一个记录")
    print("- 目的：避免多个账号重复操作同一帖子")
    print("- 默认去重时间：15天")
    print("=" * 60)

if __name__ == "__main__":
    _测试()
