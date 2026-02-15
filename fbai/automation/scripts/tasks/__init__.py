"""
子任务模块

使用动态导入，避免某些模块不存在时导致整个包加载失败
"""

# 动态导入，如果模块不存在就跳过
__all__ = []

# 尝试导入各个模块，失败则跳过
try:
    from .到首页 import 到首页, 页面状态, 页面检测结果
    __all__.extend(['到首页', '页面状态', '页面检测结果'])
except ImportError:
    pass

try:
    from .阅读 import 阅读, 阅读配置, 真人模拟
    __all__.extend(['阅读', '阅读配置', '真人模拟'])
except ImportError:
    pass

try:
    from .设置头像 import 设置头像, 检测是否有头像, 获取随机头像, 获取随机评论图片
    __all__.extend(['设置头像', '检测是否有头像', '获取随机头像', '获取随机评论图片'])
except ImportError:
    pass

try:
    from .demo import demo任务, Demo配置
    __all__.extend(['demo任务', 'Demo配置'])
except ImportError:
    pass

try:
    from .视频功能 import 视频功能, 视频配置
    __all__.extend(['视频功能', '视频配置'])
except ImportError:
    pass

try:
    from .登录 import 检查待登录账号, 批量登录, Cookie登录, 账号密码登录
    __all__.extend(['检查待登录账号', '批量登录', 'Cookie登录', '账号密码登录'])
except ImportError:
    pass

# 自动化工具（供其他任务脚本使用）
try:
    from . import 自动化工具
    __all__.append('自动化工具')
except ImportError:
    pass
