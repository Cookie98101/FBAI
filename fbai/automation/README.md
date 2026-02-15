# 自动化模块架构说明

## 概述

本模块用于控制比特浏览器执行自动化任务，支持**热更新**机制，打包后仍可更新脚本逻辑。

## 架构图

```
┌─────────────────────────────────────────────────────────────────┐
│                        打包进 EXE（不可热更新）                    │
│  ┌─────────────────┐      ┌─────────────────────────────────┐  │
│  │ facebook_       │      │ automation/                     │  │
│  │ dashboard.py    │─────▶│   ├── bootstrap.py (启动器)     │  │
│  │ (主界面)        │      │   ├── task_loader.py (加载器)   │  │
│  └─────────────────┘      │   └── bitbrowser_api.py        │  │
│                           └───────────────┬─────────────────┘  │
└───────────────────────────────────────────┼─────────────────────┘
                                            │ 动态加载
                                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                      外部文件（可热更新）                         │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ automation_scripts/  (打包后) 或 automation/scripts/     │   │
│  │   ├── main.py          ← 主控制器（可热更新）             │   │
│  │   └── tasks/           ← 任务脚本目录                    │   │
│  │         ├── baidu_search.py                             │   │
│  │         ├── read_article.py                             │   │
│  │         └── ...                                         │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

## 核心文件说明

### 打包进 EXE 的文件（不可热更新）

| 文件 | 作用 |
|------|------|
| `bootstrap.py` | 启动器，负责动态加载外部 main.py |
| `task_loader.py` | 任务加载器，支持 .py 和 .pyc 文件 |
| `bitbrowser_api.py` | 比特浏览器 API 封装 |

### 外部文件（可热更新）

| 文件 | 作用 |
|------|------|
| `scripts/main.py` | 主控制器，核心调度逻辑 |
| `tasks/*.py` | 具体任务脚本 |

## 热更新机制

### 工作原理

1. `bootstrap.py` 被打包进 exe，启动时查找外部 `main.py`
2. 使用 `importlib` 动态加载 `main.py` 模块
3. `main.py` 中的 `AutomationController` 负责加载和执行任务
4. 任务脚本通过 `task_loader.py` 动态加载

### 更新流程

```
修改 main.py 或 tasks/*.py
        ↓
替换用户电脑上的文件
        ↓
下次执行任务时自动生效（无需重启程序）
```

### 强制重新加载

```python
# 在代码中调用
automation_bootstrap.reload()  # 重新加载 main.py
```

## 目录结构

### 开发环境

```
项目根目录/
├── automation/
│   ├── __init__.py
│   ├── bootstrap.py        # 启动器（打包进exe）
│   ├── task_loader.py      # 任务加载器（打包进exe）
│   ├── compile_tasks.py    # 编译工具
│   ├── main.py             # 命令行入口
│   ├── scripts/
│   │   └── main.py         # 主控制器（可热更新）
│   └── tasks/
│       ├── __init__.py
│       ├── example_task.py
│       ├── baidu_search.py
│       └── read_article.py
├── bitbrowser_api.py
└── facebook_dashboard.py
```

### 打包后（分发给用户）

```
程序目录/
├── 主程序.exe
└── automation_scripts/     # 外部脚本目录
    ├── main.py             # 或 main.pyc
    └── tasks/
        ├── baidu_search.pyc
        └── ...
```

## 任务脚本开发

### 脚本模板

```python
"""
任务描述
"""

# 任务元信息（可选但推荐）
TASK_INFO = {
    "name": "任务名称",
    "description": "任务描述",
    "version": "1.0.0",
    "author": "作者",
    "params": {
        "param_name": {
            "type": "int",
            "default": 10,
            "description": "参数说明"
        }
    }
}

def execute(context):
    """
    任务执行入口（必须）
    
    :param context: TaskContext 对象
        - browser_id: 浏览器ID
        - browser_ws: WebSocket 连接地址
        - browser_info: {"driver": "...", "http": "..."}
        - params: 任务参数字典
        - controller: 主控制器引用
    
    :return: 
        - dict: {"success": bool, "message": str, "error": str}
        - bool: 简单的成功/失败
    """
    # 获取参数
    param_value = context.params.get("param_name", 10)
    
    # 获取 Selenium 连接信息
    driver_path = context.browser_info.get("driver")
    http_address = context.browser_info.get("http")
    
    # 执行任务逻辑
    # ...
    
    return {"success": True, "message": "完成"}
```

### Selenium 连接示例

```python
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options

def execute(context):
    driver_path = context.browser_info.get("driver")
    http_address = context.browser_info.get("http")
    
    # 连接到比特浏览器
    chrome_options = Options()
    chrome_options.add_experimental_option("debuggerAddress", http_address)
    
    chrome_service = Service(driver_path)
    driver = webdriver.Chrome(service=chrome_service, options=chrome_options)
    
    # 执行操作
    driver.get("https://www.baidu.com")
    # ...
    
    # 注意：不要调用 driver.quit()，会关闭整个浏览器
    return {"success": True}
```

## 代码保护

### 编译为字节码

```bash
# 编译 tasks 目录下的所有 .py 文件
python -m automation.compile_tasks

# 编译后删除源文件（发布用）
python -m automation.compile_tasks --delete-source

# 编译到指定目录
python -m automation.compile_tasks --output dist/automation_scripts/tasks
```

### 保护级别

| 方式 | 保护程度 | 说明 |
|------|----------|------|
| .py 源文件 | 无 | 明文可见 |
| .pyc 字节码 | 中等 | 可反编译，但需要工具 |
| 混淆 + .pyc | 较高 | 反编译后难以阅读 |

## 命令行使用

```bash
# 列出所有可用任务
python -m automation.main --list

# 列出所有浏览器
python -m automation.main --browsers

# 执行任务
python -m automation.main --browser <浏览器ID> --task <任务名>

# 带参数执行
python -m automation.main --browser abc123 --task baidu_search --params '{"keyword": "你好"}'
```

## UI 使用

1. 启动主程序
2. 切换到"自动化"标签页
3. 点击"检查连接"确认比特浏览器已启动
4. 点击"刷新列表"获取浏览器窗口
5. 勾选要操作的浏览器
6. 选择任务，填写参数
7. 点击"执行任务"

## 协同开发

其他开发者只需：

1. 参考 `tasks/example_task.py` 模板
2. 在 `tasks/` 目录创建新的任务脚本
3. 遵循 `execute(context)` 接口规范
4. 无需修改主程序代码

## 常见问题

### Q: 修改 main.py 后不生效？
A: 调用 `automation_bootstrap.reload()` 或重启程序

### Q: 用户需要安装 Python 吗？
A: 不需要，exe 内置了 Python 运行时

### Q: 如何调试任务脚本？
A: 使用命令行模式 `python -m automation.main` 更方便调试

### Q: .pyc 文件如何生成？
A: 运行 `python -m automation.compile_tasks`
