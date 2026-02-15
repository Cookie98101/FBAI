"""
账号个性画像系统
功能: 为每个账号生成独特的个性画像，让行为更加随机化和真实化
作者: AI Assistant
日期: 2025-12-30
"""

import random
import json
import os
from typing import Dict, List, Optional
from datetime import datetime


class 账号个性画像:
    """
    账号个性画像类
    
    每个账号有独特的:
    1. 性格特征 - 影响操作风格
    2. 操作习惯 - 影响具体行为
    3. 兴趣偏好 - 影响内容选择
    4. 行为模式 - 影响时间和频率
    5. 风险偏好 - 影响激进程度
    """
    
    def __init__(self, 账号ID: str, 自动生成: bool = True):
        """
        初始化账号个性画像
        
        参数:
            账号ID: 账号唯一标识
            自动生成: 是否自动生成随机画像
        """
        self.账号ID = 账号ID
        self.创建时间 = datetime.now().isoformat()
        
        # 核心属性
        self.性格特征 = {}
        self.操作习惯 = {}
        self.兴趣偏好 = {}
        self.行为模式 = {}
        self.风险偏好 = {}
        
        if 自动生成:
            self._生成随机画像()
    
    def _生成随机画像(self):
        """生成随机的个性画像"""
        
        # 1. 性格特征（0-100分）
        self.性格特征 = {
            "外向度": random.randint(30, 90),
            "谨慎度": random.randint(40, 95),
            "活跃度": random.randint(30, 85),
            "友好度": random.randint(40, 90),
            "耐心度": random.randint(35, 90),
        }
        
        # 2. 操作习惯
        self.操作习惯 = {
            # 速度相关
            "打字速度": self._随机选择(["很慢", "慢", "正常", "快", "很快"], [0.1, 0.2, 0.4, 0.2, 0.1]),
            "鼠标速度": self._随机选择(["慢", "正常", "快"], [0.2, 0.6, 0.2]),
            "阅读速度": self._随机选择(["慢", "正常", "快"], [0.25, 0.5, 0.25]),
            
            # 习惯性动作
            "点击前滚动": random.random() < 0.7,
            "操作前犹豫": random.random() < 0.6,
            "喜欢回看": random.random() < 0.5,
            "频繁停顿": random.random() < 0.3,
            "二次确认": random.random() < 0.4,
            
            # 错误倾向
            "打字错误率": random.uniform(0.03, 0.12),
            "鼠标抖动": random.random() < 0.4,
            
            # 浏览习惯
            "滚动方式": self._随机选择(["平滑", "跳跃", "混合"], [0.4, 0.3, 0.3]),
            "注意力集中度": random.randint(40, 90),
        }
        
        # 3. 兴趣偏好
        self.兴趣偏好 = {
            # 内容偏好
            "内容相关性要求": random.randint(50, 80),
            
            # 互动偏好
            "点赞倾向": random.uniform(0.5, 1.0),
            "评论倾向": random.uniform(0.3, 1.0),
            "加好友倾向": random.uniform(0.2, 0.9),
            "私信倾向": random.uniform(0.1, 0.7),
            
            # 社交风格
            "社交风格": self._随机选择(
                ["观察者", "轻度互动", "积极互动", "社交达人"],
                [0.2, 0.4, 0.3, 0.1]
            ),
        }
        
        # 4. 行为模式
        self.行为模式 = {
            # 活跃时间
            "活跃时段": self._生成活跃时段(),
            
            # 操作节奏
            "每日目标": random.randint(10, 40),
            "单次持续时间": random.randint(20, 90),
            "休息频率": random.randint(3, 10),
            
            # 疲劳特征
            "疲劳速度": self._随机选择(["慢", "正常", "快"], [0.3, 0.5, 0.2]),
            "恢复速度": self._随机选择(["慢", "正常", "快"], [0.2, 0.6, 0.2]),
        }
        
        # 5. 风险偏好
        self.风险偏好 = {
            "风险等级": self._随机选择(
                ["极度保守", "保守", "中等", "激进", "极度激进"],
                [0.15, 0.35, 0.35, 0.12, 0.03]
            ),
            "操作激进度": random.randint(20, 80),
            "延迟容忍度": random.uniform(0.7, 1.5),
        }
        
        # 生成个性标签
        self._生成个性标签()
    
    def _随机选择(self, 选项: List[str], 权重: List[float]) -> str:
        """根据权重随机选择"""
        return random.choices(选项, weights=权重)[0]
    
    def _生成活跃时段(self) -> List[int]:
        """生成活跃时段（小时列表）"""
        模式 = random.choice(["早鸟型", "夜猫型", "正常型", "全天型"])
        
        if 模式 == "早鸟型":
            return list(range(6, 12)) + random.sample(range(14, 18), 2)
        elif 模式 == "夜猫型":
            return list(range(19, 24)) + random.sample(range(9, 13), 2)
        elif 模式 == "正常型":
            return list(range(9, 18))
        else:
            return list(range(8, 23))
    
    def _生成个性标签(self):
        """根据属性生成个性标签"""
        标签 = []
        
        if self.性格特征["外向度"] > 70:
            标签.append("外向")
        elif self.性格特征["外向度"] < 40:
            标签.append("内向")
        
        if self.性格特征["谨慎度"] > 80:
            标签.append("谨慎")
        elif self.性格特征["谨慎度"] < 50:
            标签.append("冲动")
        
        if self.性格特征["活跃度"] > 70:
            标签.append("活跃")
        
        if self.操作习惯["打字速度"] in ["很快", "快"]:
            标签.append("快手")
        elif self.操作习惯["打字速度"] in ["很慢", "慢"]:
            标签.append("慢性子")
        
        if self.操作习惯["频繁停顿"]:
            标签.append("思考型")
        
        标签.append(self.兴趣偏好["社交风格"])
        标签.append(self.风险偏好["风险等级"])
        
        self.个性标签 = 标签

    
    # ==================== 行为调整方法 ====================
    
    def 获取速度系数(self, 操作类型: str) -> float:
        """获取操作速度系数"""
        速度映射 = {
            "很快": 0.6, "快": 0.8, "正常": 1.0, "慢": 1.3, "很慢": 1.6
        }
        
        if 操作类型 == "打字":
            速度 = self.操作习惯["打字速度"]
        elif 操作类型 == "鼠标":
            速度 = self.操作习惯["鼠标速度"]
        elif 操作类型 == "阅读":
            速度 = self.操作习惯["阅读速度"]
        else:
            return 1.0
        
        return 速度映射.get(速度, 1.0)
    
    def 获取延迟系数(self) -> float:
        """获取延迟时间系数"""
        基础系数 = self.风险偏好["延迟容忍度"]
        谨慎系数 = self.性格特征["谨慎度"] / 100.0
        return 基础系数 * (0.8 + 谨慎系数 * 0.4)
    
    def 获取互动概率系数(self, 互动类型: str) -> float:
        """获取互动概率系数"""
        映射 = {
            "点赞": "点赞倾向",
            "评论": "评论倾向",
            "加好友": "加好友倾向",
            "私信": "私信倾向"
        }
        键 = 映射.get(互动类型)
        return self.兴趣偏好[键] if 键 else 1.0
    
    def 是否应该操作(self, 操作名称: str) -> bool:
        """判断是否应该执行某个习惯性操作"""
        return self.操作习惯.get(操作名称, False)
    
    def 获取AI阈值调整(self) -> int:
        """获取AI判断阈值调整"""
        要求 = self.兴趣偏好["内容相关性要求"]
        return 要求 - 60
    
    def 当前是否活跃(self) -> bool:
        """判断当前时间是否在活跃时段"""
        当前小时 = datetime.now().hour
        return 当前小时 in self.行为模式["活跃时段"]
    
    def 获取疲劳系数调整(self) -> float:
        """获取疲劳累积速度调整"""
        速度映射 = {"慢": 0.7, "正常": 1.0, "快": 1.4}
        return 速度映射.get(self.行为模式["疲劳速度"], 1.0)
    
    # ==================== 数据持久化 ====================
    
    def 转为字典(self) -> Dict:
        """转换为字典格式"""
        return {
            "账号ID": self.账号ID,
            "创建时间": self.创建时间,
            "性格特征": self.性格特征,
            "操作习惯": self.操作习惯,
            "兴趣偏好": self.兴趣偏好,
            "行为模式": self.行为模式,
            "风险偏好": self.风险偏好,
            "个性标签": self.个性标签
        }
    
    @classmethod
    def 从字典创建(cls, 数据: Dict) -> '账号个性画像':
        """从字典创建实例"""
        实例 = cls(数据["账号ID"], 自动生成=False)
        实例.创建时间 = 数据.get("创建时间", datetime.now().isoformat())
        实例.性格特征 = 数据.get("性格特征", {})
        实例.操作习惯 = 数据.get("操作习惯", {})
        实例.兴趣偏好 = 数据.get("兴趣偏好", {})
        实例.行为模式 = 数据.get("行为模式", {})
        实例.风险偏好 = 数据.get("风险偏好", {})
        实例.个性标签 = 数据.get("个性标签", [])
        return 实例
    
    def 保存到文件(self, 文件路径: str):
        """保存到JSON文件"""
        with open(文件路径, 'w', encoding='utf-8') as f:
            json.dump(self.转为字典(), f, ensure_ascii=False, indent=2)
    
    @classmethod
    def 从文件加载(cls, 文件路径: str) -> '账号个性画像':
        """从JSON文件加载"""
        with open(文件路径, 'r', encoding='utf-8') as f:
            数据 = json.load(f)
        return cls.从字典创建(数据)
    
    def 打印画像(self):
        """打印个性画像信息"""
        print("\n" + "="*60)
        print(f"账号个性画像 - {self.账号ID}")
        print("="*60)
        
        print("\n📊 性格特征:")
        for 特征, 分数 in self.性格特征.items():
            print(f"  {特征}: {分数}/100 {'█' * (分数 // 10)}")
        
        print("\n⚙️ 操作习惯:")
        for 习惯, 值 in self.操作习惯.items():
            if isinstance(值, bool):
                print(f"  {习惯}: {'✓' if 值 else '✗'}")
            elif isinstance(值, float):
                print(f"  {习惯}: {值:.2f}")
            else:
                print(f"  {习惯}: {值}")
        
        print("\n💡 兴趣偏好:")
        for 偏好, 值 in self.兴趣偏好.items():
            if isinstance(值, float):
                print(f"  {偏好}: {值:.2f}")
            else:
                print(f"  {偏好}: {值}")
        
        print("\n⏰ 行为模式:")
        print(f"  活跃时段: {self.行为模式['活跃时段']}")
        print(f"  每日目标: {self.行为模式['每日目标']} 个")
        print(f"  单次持续: {self.行为模式['单次持续时间']} 分钟")
        
        print("\n🎯 风险偏好:")
        for 偏好, 值 in self.风险偏好.items():
            if isinstance(值, float):
                print(f"  {偏好}: {值:.2f}")
            else:
                print(f"  {偏好}: {值}")
        
        print("\n🏷️ 个性标签:")
        print(f"  {', '.join(self.个性标签)}")
        print("="*60 + "\n")



class 个性画像管理器:
    """个性画像管理器"""
    
    def __init__(self, 存储目录: str = "profiles"):
        """初始化管理器"""
        self.存储目录 = 存储目录
        if not os.path.exists(存储目录):
            os.makedirs(存储目录)
        self.画像缓存: Dict[str, 账号个性画像] = {}
    
    def 获取或创建画像(self, 账号ID: str) -> 账号个性画像:
        """获取或创建账号的个性画像"""
        if 账号ID in self.画像缓存:
            return self.画像缓存[账号ID]
        
        文件路径 = self._获取文件路径(账号ID)
        if os.path.exists(文件路径):
            try:
                画像 = 账号个性画像.从文件加载(文件路径)
                self.画像缓存[账号ID] = 画像
                return 画像
            except Exception as e:
                print(f"⚠️ 加载画像失败: {e}，将创建新画像")
        
        画像 = 账号个性画像(账号ID, 自动生成=True)
        画像.保存到文件(文件路径)
        self.画像缓存[账号ID] = 画像
        return 画像
    
    def 保存画像(self, 画像: 账号个性画像):
        """保存画像到文件"""
        文件路径 = self._获取文件路径(画像.账号ID)
        画像.保存到文件(文件路径)
        self.画像缓存[画像.账号ID] = 画像
    
    def 删除画像(self, 账号ID: str):
        """删除账号的画像"""
        文件路径 = self._获取文件路径(账号ID)
        if os.path.exists(文件路径):
            os.remove(文件路径)
        if 账号ID in self.画像缓存:
            del self.画像缓存[账号ID]
    
    def 列出所有画像(self) -> List[str]:
        """列出所有已保存的画像ID"""
        画像列表 = []
        for 文件名 in os.listdir(self.存储目录):
            if 文件名.endswith('.json'):
                账号ID = 文件名[:-5]
                画像列表.append(账号ID)
        return 画像列表
    
    def _获取文件路径(self, 账号ID: str) -> str:
        """获取画像文件路径"""
        安全ID = 账号ID.replace('/', '_').replace('\\', '_')
        return os.path.join(self.存储目录, f"{安全ID}.json")
    
    def 批量生成画像(self, 账号ID列表: List[str]):
        """批量生成画像"""
        for 账号ID in 账号ID列表:
            self.获取或创建画像(账号ID)
            print(f"✓ 已生成画像: {账号ID}")


class 个性化行为适配器:
    """个性化行为适配器"""
    
    def __init__(self, 个性画像: 账号个性画像):
        """初始化适配器"""
        self.个性画像 = 个性画像
    
    def 调整延迟时间(self, 基础延迟: float) -> float:
        """根据个性调整延迟时间"""
        调整后延迟 = 基础延迟 * self.个性画像.获取延迟系数()
        耐心系数 = self.个性画像.性格特征["耐心度"] / 100.0
        调整后延迟 *= (0.8 + 耐心系数 * 0.4)
        
        if self.个性画像.性格特征["谨慎度"] > 70:
            波动 = random.uniform(0.95, 1.05)
        else:
            波动 = random.uniform(0.85, 1.15)
        
        return 调整后延迟 * 波动
    
    def 调整互动概率(self, 互动类型: str, 基础概率: float) -> float:
        """根据个性调整互动概率"""
        个性系数 = self.个性画像.获取互动概率系数(互动类型)
        调整后概率 = 基础概率 * 个性系数
        
        if 互动类型 in ["评论", "加好友", "私信"]:
            外向系数 = self.个性画像.性格特征["外向度"] / 100.0
            调整后概率 *= (0.7 + 外向系数 * 0.6)
        
        if 互动类型 in ["点赞", "评论"]:
            友好系数 = self.个性画像.性格特征["友好度"] / 100.0
            调整后概率 *= (0.8 + 友好系数 * 0.4)
        
        return max(0.0, min(1.0, 调整后概率))
    
    def 获取打字参数(self) -> Dict:
        """获取个性化的打字参数"""
        速度系数 = self.个性画像.获取速度系数("打字")
        return {
            "速度系数": 速度系数,
            "错误率": self.个性画像.操作习惯["打字错误率"],
            "停顿概率": 0.3 if self.个性画像.操作习惯["频繁停顿"] else 0.15,
            "二次确认": self.个性画像.操作习惯["二次确认"]
        }
    
    def 获取鼠标参数(self) -> Dict:
        """获取个性化的鼠标参数"""
        速度系数 = self.个性画像.获取速度系数("鼠标")
        return {
            "速度系数": 速度系数,
            "抖动": self.个性画像.操作习惯["鼠标抖动"],
            "点击前滚动": self.个性画像.操作习惯["点击前滚动"],
            "操作前犹豫": self.个性画像.操作习惯["操作前犹豫"]
        }
    
    def 获取阅读参数(self) -> Dict:
        """获取个性化的阅读参数"""
        速度系数 = self.个性画像.获取速度系数("阅读")
        return {
            "速度系数": 速度系数,
            "注意力集中度": self.个性画像.操作习惯["注意力集中度"],
            "喜欢回看": self.个性画像.操作习惯["喜欢回看"],
            "滚动方式": self.个性画像.操作习惯["滚动方式"]
        }


# 测试代码
if __name__ == "__main__":
    print("="*60)
    print("账号个性画像系统测试")
    print("="*60)
    
    # 创建个性画像
    print("\n1. 创建个性画像...")
    画像1 = 账号个性画像("test_account_001")
    画像1.打印画像()
    
    # 测试管理器
    print("\n2. 测试管理器...")
    管理器 = 个性画像管理器("test_profiles")
    画像2 = 管理器.获取或创建画像("test_account_002")
    print(f"✓ 创建画像: {画像2.账号ID}")
    print(f"  个性标签: {', '.join(画像2.个性标签)}")
    
    # 测试适配器
    print("\n3. 测试适配器...")
    适配器 = 个性化行为适配器(画像2)
    基础延迟 = 5.0
    调整后延迟 = 适配器.调整延迟时间(基础延迟)
    print(f"  基础延迟: {基础延迟}秒")
    print(f"  调整后延迟: {调整后延迟:.2f}秒")
    
    print("\n" + "="*60)
    print("✅ 账号个性画像系统测试完成")
    print("="*60)
