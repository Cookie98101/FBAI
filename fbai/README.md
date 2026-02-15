# Facebook数据展示程序

## 项目简介

这是一个用于展示Facebook数据分析的桌面应用程序。该程序使用PyQt5构建图形用户界面，通过Flask后端服务提供数据接口，并以图表和表格形式展示Facebook数据。

## 项目结构

```
数据展示测试/
├── facebook_dashboard.py     # 桌面应用主程序
├── backend_service.py        # 后端服务程序
├── route_manager.py          # 路由管理模块
├── route_handlers.py         # 路由处理模块
├── routes.py                 # 核心路由定义
├── requirements.txt          # 项目依赖
├── data/
│   └── facebook_data.json    # 示例数据文件
├── static/
│   └── index.html            # 静态页面文件
└── README.md                 # 项目说明文件
```

## 功能特性

1. **自动启动后端服务**：桌面应用启动时会自动检查并启动后端服务
2. **实时数据展示**：以图表和表格形式展示Facebook数据
3. **数据刷新**：支持手动刷新和自动刷新数据（每30秒自动刷新一次）
4. **数据导出**：支持将数据导出为CSV格式
5. **多数据源支持**：支持Facebook、Instagram、Twitter等多种数据源
6. **现代化UI界面**：采用暗色主题设计，具有窗口拖动、最小化、最大化和关闭功能
7. **模拟器监控**：实时显示模拟器状态
8. **请求日志**：显示数据请求日志信息
9. **扩展功能路由**：提供程序执行和系统信息查询等扩展功能
10. **路由管理系统**：统一管理所有API端点，支持动态路由注册

## 安装依赖

在运行程序之前，请确保安装了所有必要的依赖包：

```bash
pip install -r requirements.txt
```

## 依赖说明

- PyQt5: 用于构建桌面应用程序界面
- numpy: 用于数据处理和计算
- flask: 用于提供后端Web服务
- requests: 用于桌面应用与后端服务之间的通信

## 运行程序

### 方法一：直接运行（推荐）

只需运行桌面应用，它会自动启动后端服务：

```bash
python facebook_dashboard.py
```

### 方法二：分别运行

1. 首先启动后端服务：
```bash
python backend_service.py
```

2. 然后运行桌面应用：
```bash
python facebook_dashboard.py
```

## 使用说明

1. **启动程序**：运行`facebook_dashboard.py`文件启动桌面应用
2. **查看数据**：程序启动后会自动加载并显示Facebook数据
3. **刷新数据**：点击"刷新数据"按钮获取最新数据
4. **导出数据**：点击"导出数据"按钮将数据保存为CSV文件
5. **切换数据源**：使用下拉菜单切换不同的数据源类型

## API接口

后端服务提供以下API接口：

- `GET /`：返回主页面
- `GET /get_current_data`：获取当前数据
- `GET /get_data_history`：获取历史数据
- `GET /add_data`：通过GET请求添加新数据
- `POST /add_data`：通过POST请求添加新数据

GET请求返回的数据格式为JSON，包含以下字段：
- `date`：日期
- `likes`：点赞数
- `comments`：评论数
- `shares`：分享数
- `friends`：好友数
- `posts`：动态数
- `accounts`：账户数
- `groups`：群组数

## 扩展功能API接口

系统新增了扩展功能路由，提供以下API接口：

- `GET /get_available_routes`：获取所有可用路由列表
- `POST /execute_desktop_program`：执行桌面端程序
- `POST /execute_backend_program`：通过后台服务执行程序

### 获取可用路由列表

通过GET请求获取系统中所有可用的路由信息：

示例请求：
```bash
curl http://localhost:8805/get_available_routes
```

返回数据格式为JSON，包含所有路由的端点、HTTP方法和描述信息。

### 执行桌面端程序

通过POST请求执行指定的桌面端程序：

请求数据格式：
```json
{
  "program_path": "程序路径",
  "arguments": ["参数1", "参数2"]
}
```

示例POST请求：
```bash
curl -X POST http://localhost:8805/execute_desktop_program \
  -H "Content-Type: application/json" \
  -d '{
    "program_path": "notepad.exe",
    "arguments": []
  }'
```

### 通过后台服务执行程序

通过POST请求在后台执行指定的命令：

请求数据格式：
```json
{
  "command": "要执行的命令",
  "working_dir": "工作目录（可选）"
}
```

示例POST请求：
```bash
curl -X POST http://localhost:8805/execute_backend_program \
  -H "Content-Type: application/json" \
  -d '{
    "command": "echo Hello World",
    "working_dir": "."
  }'
```

### 通过GET请求添加数据

您可以通过GET请求向系统添加新数据，需要提供以下查询参数：
- `date`：日期（格式：YYYY-MM-DD）
- `likes`：点赞数
- `comments`：评论数
- `shares`：分享数
- `friends`：好友数
- `posts`：动态数
- `accounts`：账户数
- `groups`：群组数

示例GET请求：
```bash
curl "http://localhost:8805/add_data?date=2025-10-10&likes=150&comments=30&shares=15&friends=25&posts=5&accounts=3&groups=10"
```

### 通过POST请求添加数据

POST请求的数据格式应为JSON，包含以下字段：
- `date`：日期（格式：YYYY-MM-DD）
- `likes`：点赞数
- `comments`：评论数
- `shares`：分享数
- `friends`：好友数
- `posts`：动态数
- `accounts`：账户数
- `groups`：群组数

示例POST请求：
```bash
curl -X POST http://localhost:8805/add_data \
  -H "Content-Type: application/json" \
  -d '{
    "date": "2025-10-10",
    "likes": 150,
    "comments": 30,
    "shares": 15,
    "friends": 25,
    "posts": 5,
    "accounts": 3,
    "groups": 10
  }'
```

## 技术架构

- **前端**：PyQt5桌面应用
- **后端**：Flask Web服务
- **数据存储**：JSON文件
- **数据可视化**：自定义绘图组件
- **路由管理**：模块化路由系统（route_manager.py）
- **路由处理**：分布式路由处理函数（route_handlers.py）

## 端口配置

程序默认使用8805端口提供后端服务。如果需要更改端口，请修改`backend_service.py`文件中的以下行：

```python
app.run(host='localhost', port=8805, debug=False, threaded=True)
```

## 注意事项

1. 程序会自动在8805端口启动后端服务
2. 请确保8805端口未被其他程序占用
3. 如果需要更改端口，请修改`backend_service.py`文件中的端口配置
4. 程序会在启动时自动检查后端服务是否已在运行，避免重复启动
5. 数据文件位于`data`目录中，可以替换为实际数据
6. 静态页面已正确配置UTF-8编码以确保中文正常显示