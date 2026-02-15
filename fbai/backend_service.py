import json
import os
import subprocess
import sys
import threading
import time
import requests
from flask import Flask, request, jsonify
from flask_cors import CORS
from safe_file_manager import safe_read_json, safe_write_json
from datetime import datetime, timedelta
from collections import deque
from pathlib import Path

# 导入路由管理器
try:
    from route_manager import route_manager, get_endpoint, get_method
    routes_available = True
except ImportError:
    routes_available = False
    print("警告: 无法导入路由管理器，扩展功能可能不可用")

# 尝试导入路由处理模块
try:
    from route_handlers import register_routes as register_extension_routes
    extension_routes_available = True
except ImportError:
    extension_routes_available = False
    print("警告: 无法导入route_handlers模块")

# 设置标准输出编码为UTF-8
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

# 导入扩展路由
try:
    from routes import register_routes
    routes_available = True
except ImportError:
    routes_available = False
    print("警告: 未找到routes.py文件，扩展功能将不可用")

# 创建一个全局的日志队列，最多保存100条日志
request_logs = deque(maxlen=100)

# 全局变量：数据文件最后修改时间和数据版本号
data_file_mtime = 0
data_version = 0
cached_data = None

# 全局变量：用户配置
user_config = {
    'username': '朱老板',  # 默认用户名
    'remote_url': 'http://localhost/kf/submit.php'  # 远程提交URL（默认）
}

def load_remote_config():
    """加载远程地址配置"""
    try:
        import json
        import os
        config_file = "remote_config.json"
        if os.path.exists(config_file):
            with open(config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
                remote_address = config.get('remote_address', 'http://localhost')
                # 构建完整的远程提交URL
                return f"{remote_address}/kf/submit.php"
        else:
            return 'http://localhost/kf/submit.php'
    except Exception as e:
        print(f"[ERROR] 加载远程地址配置失败: {e}")
        return 'http://localhost/kf/submit.php'

def _获取AI_API_KEY():
    """从配置文件获取 AI API Key"""
    try:
        配置文件 = os.path.join("automation", "scripts", "脚本配置", "qwen_api_key.txt")
        
        if os.path.exists(配置文件):
            with open(配置文件, 'r', encoding='utf-8') as f:
                key = f.read().strip()
                if key:
                    return key
    except:
        pass
    
    # 默认API Key
    return "sk-uhidkjpeqtbttghqqxhepsywlziozhdztquhztqssikvxkwg"

def load_user_config_from_file():
    """从配置文件中加载用户配置"""
    try:
        # 尝试从simulator配置文件中读取用户名
        config_files = ["simulator_config.json", "monitor_config.json"]
        
        for config_file in config_files:
            if os.path.exists(config_file):
                with open(config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    if 'username' in config and config['username'].strip():
                        user_config['username'] = config['username'].strip()
                        print(f"从配置文件 {config_file} 加载用户名: {user_config['username']}")
                        return
        
        # 如果没有找到配置文件或用户名为空，使用默认值
        print(f"未找到配置文件，使用默认用户名: {user_config['username']}")
        
    except Exception as e:
        print(f"加载用户配置失败，使用默认值: {e}")
        print(f"默认用户名: {user_config['username']}")

def log_request(method, path, client_ip, user_agent, status_code=None):
    """记录请求日志"""
    log_entry = {
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'method': method,
        'path': path,
        'client_ip': client_ip,
        'user_agent': user_agent,
        'status_code': status_code
    }
    request_logs.append(log_entry)

def get_local_account_count():
    """获取本地账号数量（从比特浏览器获取）"""
    try:
        from bitbrowser_api import bit_browser
        
        # 获取浏览器列表
        result = bit_browser.get_browser_list(page=0, page_size=1000)  # 获取最多1000个
        
        if result.get("success"):
            data = result.get("data", {})
            total = data.get("totalNum", 0)  # 注意：字段名是 totalNum，不是 total
            print(f"从比特浏览器获取账号数量: {total}")
            return total
        else:
            print(f"获取比特浏览器列表失败: {result.get('msg', '未知错误')}")
            return 0
            
    except Exception as e:
        print(f"获取账号数量失败: {e}")
        return 0

def is_hidden_or_temp_file(filepath):
    """判断文件是否为隐藏文件或临时文件"""
    try:
        import stat
        # 获取文件名
        filename = os.path.basename(filepath)
        
        # 检查是否为隐藏文件（Windows）
        if filename.startswith('.'):
            return True
        
        # 检查Windows隐藏属性
        if os.name == 'nt':
            try:
                attrs = os.stat(filepath).st_file_attributes
                if attrs & stat.FILE_ATTRIBUTE_HIDDEN:
                    return True
            except (OSError, AttributeError):
                pass
        
        # 检查是否为临时文件
        temp_extensions = ['.tmp', '.temp', '.swp', '.bak']
        for ext in temp_extensions:
            if filename.lower().endswith(ext):
                return True
        
        return False
    except:
        return False

def submit_to_remote_server(local_data, date):
    """向远程服务器提交数据"""
    try:
        import requests
        
        # 重新加载用户配置以获取最新的用户名
        load_user_config_from_file()
        
        # 从传入的数据中获取账号数量（如果没有则重新获取）
        account_count = local_data.get('accounts', get_local_account_count())
        print(f"提交的账号数量: {account_count}")
        
        # 构建远程提交的数据
        # 初始化所有字段为0
        remote_data = {
            'username': user_config['username'],
            'date': date,
            'posts': 0,
            'shares': 0,
            'friends': 0,
            'snapshots': 0,  # 注意：这里是snapshots而不是likes
            'groups': 0,
            'comments': 0,
            'forwards': 0,  # 新增转发字段
            'accounts': account_count
        }
        
        # 只更新本地数据中提供的字段
        field_mapping = {
            'posts': 'posts',
            'shares': 'shares', 
            'friends': 'friends',
            'groups': 'groups',
            'comments': 'comments',
            'forwards': 'forwards',  # 转发字段直接对应
            # likes字段映射到snapshots
            'likes': 'snapshots'
        }
        
        for local_field, remote_field in field_mapping.items():
            if local_field in local_data:
                remote_data[remote_field] = local_data[local_field]
                print(f"映射字段: {local_field} -> {remote_field} = {local_data[local_field]}")
        
        print(f"本地数据: {local_data}")
        print(f"准备提交到远程服务器的数据: {remote_data}")
        
        # 动态加载远程地址配置
        remote_url = load_remote_config()
        print(f"远程转发URL: {remote_url}")
        
        # 发送POST请求到远程服务器
        response = requests.post(
            remote_url,
            data=remote_data,
            timeout=10,
            headers={'Content-Type': 'application/x-www-form-urlencoded'}
        )
        
        print(f"远程服务器响应状态码: {response.status_code}")
        print(f"远程服务器响应内容: {response.text}")
        
        if response.status_code == 200:
            return {
                'status': 'success',
                'message': '远程提交成功',
                'response': response.text
            }
        else:
            return {
                'status': 'error',
                'message': f'远程服务器返回错误状态码: {response.status_code}',
                'response': response.text
            }
            
    except Exception as e:
        print(f"远程提交异常详细信息: {str(e)}")
        print(f"异常类型: {type(e).__name__}")
        return {
            'status': 'error',
            'message': f'远程提交异常: {str(e)}'
        }
    # 同时打印到控制台，方便调试
    print(f"[{log_entry['timestamp']}] {method} {path} - {client_ip} - {user_agent}")

def create_app():
    """创建Flask应用"""
    app = Flask(__name__)
    
    # 启动时加载用户配置
    load_user_config_from_file()
    
    # 注册扩展路由
    if routes_available:
        try:
            from routes import register_routes
            register_routes(app)
            print("扩展路由注册成功")
        except ImportError:
            print("警告: 无法导入routes模块，扩展功能可能不可用")
        except Exception as e:
            print(f"注册扩展路由时出错: {e}")
    
    # 注册新的扩展路由处理函数
    if extension_routes_available:
        try:
            register_extension_routes(app)
            print("新的扩展路由注册成功")
        except Exception as e:
            print(f"注册新的扩展路由时出错: {e}")
    else:
        print("警告: route_handlers模块不可用，新的扩展功能可能不可用")
    
    @app.route('/shutdown', methods=['POST'])
    def shutdown():
        """关闭Flask服务器"""
        try:
            print("[后端服务] 收到关闭请求")
            # 使用werkzeug的shutdown功能
            func = request.environ.get('werkzeug.server.shutdown')
            if func is None:
                # 如果werkzeug.server.shutdown不可用，尝试其他方法
                import os
                import signal
                print("[后端服务] 使用信号方式关闭")
                os.kill(os.getpid(), signal.SIGTERM)
            else:
                func()
            return jsonify({'status': 'success', 'message': '服务器正在关闭'})
        except Exception as e:
            print(f"[后端服务] 关闭失败: {e}")
            return jsonify({'status': 'error', 'message': str(e)})
    
    @app.before_request
    def before_request():
        """在每个请求之前记录基本信息"""
        # 获取客户端IP
        if request.headers.get('X-Forwarded-For'):
            client_ip = request.headers.get('X-Forwarded-For').split(',')[0].strip()
        elif request.headers.get('X-Real-IP'):
            client_ip = request.headers.get('X-Real-IP')
        else:
            client_ip = request.remote_addr
            
        # 获取User-Agent
        user_agent = request.headers.get('User-Agent', 'Unknown')
        
        # 记录请求信息（状态码暂时设为None，将在请求结束后更新）
        log_request(request.method, request.path, client_ip, user_agent)
    
    @app.after_request
    def after_request(response):
        """在每个请求之后更新日志中的状态码"""
        # 更新最后一条日志记录的状态码
        if request_logs:
            request_logs[-1]['status_code'] = response.status_code
        return response
    
    @app.route('/')
    def index():
        """主页路由"""
        # 明确指定文件编码为UTF-8
        return send_from_directory('static', 'index.html', mimetype='text/html; charset=utf-8')
    
    @app.route('/get_request_logs')
    def get_request_logs():
        """获取请求日志"""
        # 将deque转换为列表并返回
        logs_list = list(request_logs)
        return jsonify({
            'status': 'success',
            'data': logs_list,
            'message': '请求日志获取成功'
        })
    
    @app.route('/check_data_version')
    def check_data_version():
        """检查数据版本（轻量级接口，只返回版本号）"""
        global data_version
        return jsonify({
            'status': 'success',
            'version': data_version,
            'message': '版本检查成功'
        })
    
    @app.route('/get_current_data')
    def get_current_data():
        """获取当前数据（带版本号）"""
        global data_file_mtime, data_version, cached_data
        
        try:
            # 使用绝对路径，确保打包后也能正确找到数据文件
            import sys
            if getattr(sys, 'frozen', False):
                # 打包后的exe运行时
                base_path = os.path.dirname(sys.executable)
            else:
                # 开发环境下
                base_path = os.path.dirname(os.path.abspath(__file__))
            data_file = os.path.join(base_path, "data", "facebook_data.json")
            
            if os.path.exists(data_file):
                # 检查文件是否被修改
                current_mtime = os.path.getmtime(data_file)
                
                if current_mtime != data_file_mtime or cached_data is None:
                    # 文件已修改，重新读取
                    with open(data_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    
                    # 更新缓存和版本号
                    data_file_mtime = current_mtime
                    data_version += 1
                    cached_data = data
                    
                    print("=" * 80)
                    print(f"[后端服务] 🔄 数据文件已更新")
                    print(f"[后端服务] ✓ 从文件读取数据: {len(data)} 条记录")
                    if data:
                        print(f"[后端服务] 日期范围: {data[0]['date']} 到 {data[-1]['date']}")
                    print(f"[后端服务] 数据版本: {data_version}")
                    print("=" * 80)
                else:
                    # 使用缓存数据
                    data = cached_data
                
                return jsonify({
                    'status': 'success',
                    'data': data,
                    'version': data_version,
                    'message': '数据获取成功'
                })
            else:
                # 文件不存在，生成示例数据并保存
                print(f"[后端服务] 数据文件不存在，生成新数据...")
                sample_data = generate_sample_data()
                print(f"[后端服务] ✓ 生成示例数据: {len(sample_data)} 条记录")
                if sample_data:
                    print(f"[后端服务] 日期范围: {sample_data[0]['date']} 到 {sample_data[-1]['date']}")
                # 保存示例数据到文件，避免每次都重新生成
                try:
                    os.makedirs(os.path.dirname(data_file), exist_ok=True)
                    with open(data_file, 'w', encoding='utf-8') as f:
                        json.dump(sample_data, f, ensure_ascii=False, indent=2)
                    print(f"[后端服务] ✓ 已保存示例数据到 {data_file}")
                except Exception as e:
                    print(f"[后端服务] ❌ 保存示例数据失败: {e}")
                    import traceback
                    traceback.print_exc()
                
                return jsonify({
                    'status': 'success',
                    'data': sample_data,
                    'message': '数据文件不存在，已生成并保存示例数据'
                })
        except Exception as e:
            return jsonify({
                'status': 'error',
                'message': f'获取数据时出错: {str(e)}'
            })
    
    @app.route('/api/generate_script', methods=['POST'])
    def generate_script():
        """AI文案生成API端点"""
        try:
            # 获取请求数据
            data = request.get_json()
            if not data:
                return jsonify({
                    'success': False,
                    'error': '缺少请求数据'
                }), 400
            
            prompt = data.get('prompt', '')
            max_length = data.get('max_length', 300)
            
            if not prompt:
                return jsonify({
                    'success': False,
                    'error': '缺少提示词参数'
                }), 400
            
            print(f"[AI文案生成] 收到请求: prompt={prompt}, max_length={max_length}")
            
            # 调用AI API生成文案
            # 这里使用SiliconFlow的Qwen2.5-7B-Instruct模型
            import requests
            import json
            
            api_url = "https://api.siliconflow.cn/v1/chat/completions"
            api_key = _获取AI_API_KEY()
            
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }
            
            # 构造AI提示词
            ai_prompt = f"根据以下主题生成一段短视频文案，长度不超过{max_length}字：{prompt}\n\n要求：\n1. 内容有趣且吸引人\n2. 适合短视频平台传播\n3. 包含引人入胜的开头和总结\n4. 语言简洁明了"
            
            payload = {
                "model": "Qwen/Qwen2.5-7B-Instruct",
                "messages": [
                    {
                        "role": "user",
                        "content": ai_prompt
                    }
                ],
                "stream": False,
                "max_tokens": min(max_length * 2, 512),  # 估算token数量
                "temperature": 0.7,
                "top_p": 0.7,
                "top_k": 50,
                "frequency_penalty": 0.5,
                "n": 1
            }
            
            print(f"[AI文案生成] 正在调用AI服务...")
            
            try:
                response = requests.post(api_url, headers=headers, json=payload, timeout=30)
                response.raise_for_status()
                
                result = response.json()
                ai_content = result['choices'][0]['message']['content'].strip()
                
                print(f"[AI文案生成] 成功生成文案: {ai_content[:100]}...")
                
                return jsonify({
                    'success': True,
                    'script': ai_content
                })
                
            except requests.exceptions.Timeout:
                print("[AI文案生成] AI接口请求超时")
                return jsonify({
                    'success': False,
                    'error': 'AI接口请求超时（30秒）'
                }), 500
            except requests.exceptions.RequestException as e:
                print(f"[AI文案生成] AI接口请求失败: {str(e)}")
                return jsonify({
                    'success': False,
                    'error': f'AI接口请求失败: {str(e)}'
                }), 500
            except (KeyError, IndexError, json.JSONDecodeError) as e:
                print(f"[AI文案生成] AI接口返回数据格式错误: {str(e)}")
                return jsonify({
                    'success': False,
                    'error': f'AI接口返回数据格式错误: {str(e)}'
                }), 500
                
        except Exception as e:
            print(f"[AI文案生成] 生成文案时发生错误: {str(e)}")
            import traceback
            traceback.print_exc()
            return jsonify({
                'success': False,
                'error': f'服务器内部错误: {str(e)}'
            }), 500
    
    @app.route('/get_data_history')
    def get_data_history():
        """获取历史数据"""
        try:
            # 获取分页参数
            page = int(request.args.get('page', 1))
            page_size = int(request.args.get('page_size', 10))
            
            # 读取历史数据文件
            history_file = "data/facebook_data_history.json"
            if os.path.exists(history_file):
                with open(history_file, 'r', encoding='utf-8') as f:
                    all_data = json.load(f)
                
                # 如果文件为空或不是列表，返回空数据
                if not isinstance(all_data, list):
                    all_data = []
                
                # 计算分页信息
                total = len(all_data)
                start_index = (page - 1) * page_size
                end_index = start_index + page_size
                
                # 获取当前页数据
                paginated_data = all_data[start_index:end_index]
                
                return jsonify({
                    'status': 'success',
                    'data': paginated_data,
                    'pagination': {
                        'current_page': page,
                        'page_size': page_size,
                        'total': total,
                        'total_pages': (total + page_size - 1) // page_size
                    },
                    'message': '历史数据获取成功'
                })
            else:
                return jsonify({
                    'status': 'error',
                    'message': '历史数据文件不存在'
                })
        except Exception as e:
            return jsonify({
                'status': 'error',
                'message': f'获取历史数据时出错: {str(e)}'
            })
    

    @app.route('/add_data', methods=['GET', 'POST'])
    def add_data():
        """通过GET或POST请求添加数据 - 支持单独上传某一项数据"""
        try:
            # 自动生成今天的日期
            today_date = datetime.now().strftime('%Y-%m-%d')
            
            # 根据请求方法获取数据
            if request.method == 'GET':
                # 从查询参数中获取数据
                data_fields = ['likes', 'comments', 'shares', 'friends', 'posts', 'groups', 'forwards']
                
                # 检查是否至少有一个数据字段
                provided_fields = []
                for field in data_fields:
                    if field in request.args:
                        provided_fields.append(field)
                
                if not provided_fields:
                    return jsonify({
                        'status': 'error',
                        'message': f'至少需要提供一个数据字段: {", ".join(data_fields)}'
                    }), 400
                
                # 初始化数据结构，只包含提供的字段
                data = {'date': today_date}
                for field in provided_fields:
                    try:
                        data[field] = int(request.args.get(field))
                    except ValueError:
                        return jsonify({
                            'status': 'error',
                            'message': f'字段 {field} 必须是整数'
                        }), 400
                        
            else:  # POST请求
                # 从JSON请求体中获取数据
                request_data = request.get_json()
                
                # 检查数据是否存在
                if not request_data:
                    return jsonify({
                        'status': 'error',
                        'message': '请求体必须包含JSON格式的数据'
                    }), 400
                
                # 检查是否至少有一个数据字段
                data_fields = ['likes', 'comments', 'shares', 'friends', 'posts', 'groups', 'forwards']
                provided_fields = []
                for field in data_fields:
                    if field in request_data:
                        provided_fields.append(field)
                
                if not provided_fields:
                    return jsonify({
                        'status': 'error',
                        'message': f'至少需要提供一个数据字段: {", ".join(data_fields)}'
                    }), 400
                
                # 初始化数据结构
                data = {'date': today_date}
                for field in provided_fields:
                    try:
                        data[field] = int(request_data[field])
                    except ValueError:
                        return jsonify({
                            'status': 'error',
                            'message': f'字段 {field} 必须是整数'
                        }), 400
            
            # 创建数据文件目录（如果不存在）
            data_dir = "data"
            if not os.path.exists(data_dir):
                os.makedirs(data_dir)
            
            # 获取最新的浏览器数量
            print("[DEBUG] 准备获取浏览器数量...")
            current_account_count = get_local_account_count()
            print(f"[DEBUG] 当前浏览器数量: {current_account_count}")
            
            # 读取现有数据或创建新数据
            data_file = os.path.join(data_dir, "facebook_data.json")
            existing_data = []
            if os.path.exists(data_file):
                with open(data_file, 'r', encoding='utf-8') as f:
                    existing_data = json.load(f)
            
            # 检查是否已存在相同日期的数据
            date_exists = False
            for i, existing_item in enumerate(existing_data):
                if existing_item['date'] == data['date']:
                    # 只更新提供的字段，进行累加
                    accumulative_fields = ['likes', 'comments', 'shares', 'friends', 'posts', 'groups', 'forwards']
                    for field in accumulative_fields:
                        if field in data:  # 只更新提供的字段
                            if field in existing_data[i]:
                                existing_data[i][field] += data[field]
                            else:
                                existing_data[i][field] = data[field]
                    # 更新账号数量为最新值
                    existing_data[i]['accounts'] = current_account_count
                    date_exists = True
                    break
            
            # 如果不存在相同日期的数据，则创建新数据记录
            if not date_exists:
                # 创建完整的数据记录，未提供的字段设为0
                new_record = {
                    'date': data['date'],
                    'likes': 0,
                    'comments': 0,
                    'shares': 0,
                    'friends': 0,
                    'posts': 0,
                    'accounts': current_account_count,  # 使用最新的浏览器数量
                    'groups': 0,
                    'forwards': 0
                }
                # 更新提供的字段
                for field in ['likes', 'comments', 'shares', 'friends', 'posts', 'groups', 'forwards']:
                    if field in data:
                        new_record[field] = data[field]
                
                existing_data.append(new_record)
            
            # 保存数据到文件
            with open(data_file, 'w', encoding='utf-8') as f:
                json.dump(existing_data, f, ensure_ascii=False, indent=2)
            
            # 更新全局变量以触发前端检测到数据变化
            global data_file_mtime, data_version, cached_data
            data_file_mtime = os.path.getmtime(data_file)
            data_version += 1
            cached_data = existing_data
            
            # 记录操作日志
            provided_fields = [field for field in ['likes', 'comments', 'shares', 'friends', 'posts', 'groups', 'forwards'] if field in data]
            log_message = f"数据更新成功 - 日期: {today_date}, 更新字段: {provided_fields}, 数据: {data}"
            print(log_message)
            
            # 向远程服务器提交数据（包含账号数量）
            try:
                # 添加账号数量到提交数据中
                data_with_accounts = data.copy()
                data_with_accounts['accounts'] = current_account_count
                remote_submit_result = submit_to_remote_server(data_with_accounts, today_date)
                print(f"远程提交结果: {remote_submit_result}")
            except Exception as e:
                print(f"远程提交失败: {e}")
                # 远程提交失败不影响本地数据保存
            
            # 返回成功响应
            return jsonify({
                'status': 'success',
                'message': '数据添加/更新成功',
                'date': today_date,
                'updated_fields': provided_fields,
                'data': data,
                'version': data_version
            })
        except Exception as e:
            return jsonify({
                'status': 'error',
                'message': f'服务器内部错误: {str(e)}'
            }), 500

    @app.route('/filter_data', methods=['GET'])
    def filter_data():
        """评论贴子链接管理 - 带15天数据保留"""
        try:
            # 获取GET参数
            account = request.args.get('account', '').strip()
            link = request.args.get('link', '').strip()
            action = request.args.get('action', 'add').strip().lower()  # add, check, query
            
            # 数据文件路径 - 使用绝对路径确保文件保存在正确位置
            script_dir = os.path.dirname(os.path.abspath(__file__))
            data_dir = os.path.join(script_dir, 'data')
            filter_data_file = os.path.join(data_dir, 'comment_links.json')
            
            # 确保数据目录存在
            os.makedirs(data_dir, exist_ok=True)
            
            print(f"[评论贴子链接] 操作: {action}, 账号: {account}, 链接: {link}")
            
            # 安全读取现有数据
            comment_data = safe_read_json(filter_data_file, {})
            
            # 清理过期数据（超过15天）
            current_date = datetime.now().strftime('%Y-%m-%d')
            cutoff_date = (datetime.now() - timedelta(days=15)).strftime('%Y-%m-%d')
            
            # 处理旧格式数据转换
            if comment_data and isinstance(list(comment_data.values())[0], list):
                # 旧格式：{account: [links]}，转换为新格式：{account: {date: [links]}}
                old_data = comment_data.copy()
                comment_data = {}
                for acc, links in old_data.items():
                    comment_data[acc] = {current_date: links}
                print(f"[评论贴子链接] 转换旧格式数据，涉及 {len(old_data)} 个账号")
            
            # 清理过期数据
            cleaned_data = {}
            total_cleaned = 0
            
            for acc, links_by_date in comment_data.items():
                if isinstance(links_by_date, dict):
                    cleaned_links = {}
                    for date, links in links_by_date.items():
                        if date >= cutoff_date:
                            cleaned_links[date] = links
                        else:
                            total_cleaned += len(links) if isinstance(links, list) else 1
                    
                    if cleaned_links:
                        cleaned_data[acc] = cleaned_links
                else:
                    # 处理异常格式
                    cleaned_data[acc] = {current_date: links_by_date if isinstance(links_by_date, list) else [links_by_date]}
            
            comment_data = cleaned_data
            if total_cleaned > 0:
                print(f"[评论贴子链接] 清理了 {total_cleaned} 个过期数据")
            
            # 处理不同操作
            if action == 'add':
                # 添加数据
                if not account or not link:
                    return jsonify({
                        'status': 'error',
                        'message': '账号和链接参数不能为空'
                    }), 400
                
                # 初始化账号数据
                if account not in comment_data:
                    comment_data[account] = {}
                
                # 初始化日期数据
                if current_date not in comment_data[account]:
                    comment_data[account][current_date] = []
                
                # 检查链接是否已存在（检查所有日期）
                exists = False
                for date, links in comment_data[account].items():
                    if link in links:
                        exists = True
                        break
                
                if exists:
                    return jsonify({
                        'status': 'success',
                        'message': '评论链接已存在',
                        'action': 'found',
                        'account': account,
                        'link': link,
                        'date': current_date,
                        'cleaned_expired': total_cleaned
                    })
                
                # 添加新链接到今天
                comment_data[account][current_date].append(link)
                
                # 安全保存数据
                safe_write_json(filter_data_file, comment_data)
                
                return jsonify({
                    'status': 'success',
                    'message': '评论链接已添加',
                    'action': 'added',
                    'account': account,
                    'link': link,
                    'date': current_date,
                    'cleaned_expired': total_cleaned
                })
            
            elif action == 'check':
                # 检查数据是否存在
                if not account or not link:
                    return jsonify({
                        'status': 'error',
                        'message': '账号和链接参数不能为空'
                    }), 400
                
                exists = False
                found_date = None
                
                if account in comment_data:
                    for date, links in comment_data[account].items():
                        if link in links:
                            exists = True
                            found_date = date
                            break
                
                return jsonify({
                    'status': 'success',
                    'message': '评论链接已存在' if exists else '评论链接不存在',
                    'account': account,
                    'link': link,
                    'exists': exists,
                    'found_date': found_date,
                    'cleaned_expired': total_cleaned
                })
            
            elif action == 'query':
                # 查询账号的所有链接
                if not account:
                    return jsonify({
                        'status': 'error',
                        'message': '账号参数不能为空'
                    }), 400
                
                if account not in comment_data:
                    return jsonify({
                        'status': 'success',
                        'message': f'账号 "{account}" 没有评论链接',
                        'account': account,
                        'exists': False,
                        'links_by_date': {},
                        'total_links': 0,
                        'cleaned_expired': total_cleaned
                    })
                
                links_by_date = comment_data[account]
                total_links = sum(len(links) for links in links_by_date.values())
                
                return jsonify({
                    'status': 'success',
                    'message': f'账号 "{account}" 有 {total_links} 个评论链接',
                    'account': account,
                    'exists': True,
                    'links_by_date': links_by_date,
                    'total_links': total_links,
                    'cleaned_expired': total_cleaned
                })
            
            else:
                return jsonify({
                    'status': 'error',
                    'message': f'不支持的操作: {action}'
                }), 400
                
        except Exception as e:
            return jsonify({
                'status': 'error',
                'message': f'服务器内部错误: {str(e)}'
            }), 500

    @app.route('/check_account_link', methods=['GET'])
    def check_account_link():
        """只查看账号和连接是否存在，不进行添加操作"""
        try:
            # 获取GET参数
            account = request.args.get('account', '').strip()
            link = request.args.get('link', '').strip()
            
            # 验证参数
            if not account:
                return jsonify({
                    'status': 'error',
                    'message': '账号参数不能为空'
                }), 400
            
            if not link:
                return jsonify({
                    'status': 'error', 
                    'message': '连接参数不能为空'
                }), 400
            
            # 数据文件路径
            script_dir = os.path.dirname(os.path.abspath(__file__))
            data_dir = os.path.join(script_dir, 'data')
            filter_data_file = os.path.join(data_dir, 'account_links.json')
            
            print(f"[查看账号连接] 检查文件: {filter_data_file}")
            print(f"[查看账号连接] 账号: {account}, 连接: {link}")
            
            # 读取现有数据
            account_links = {}
            if os.path.exists(filter_data_file):
                try:
                    with open(filter_data_file, 'r', encoding='utf-8') as f:
                        account_links = json.load(f)
                except Exception as e:
                    print(f"读取账号连接数据失败: {e}")
                    return jsonify({
                        'status': 'error',
                        'message': f'读取数据文件失败: {str(e)}'
                    }), 500
            
            # 检查账号是否存在
            if account not in account_links:
                return jsonify({
                    'status': 'success',
                    'message': '账号不存在',
                    'account': account,
                    'link': link,
                    'exists': False,
                    'account_exists': False,
                    'link_exists': False,
                    'all_links': []
                })
            
            # 账号存在，检查连接
            stored_links = account_links[account]
            
            # 确保stored_links是列表格式
            if not isinstance(stored_links, list):
                stored_links = [stored_links]
            
            # 检查连接是否存在
            link_exists = link in stored_links
            
            return jsonify({
                'status': 'success',
                'message': '连接已存在' if link_exists else '连接不存在',
                'account': account,
                'link': link,
                'exists': link_exists,
                'account_exists': True,
                'link_exists': link_exists,
                'all_links': stored_links,
                'total_links': len(stored_links)
            })
                
        except Exception as e:
            return jsonify({
                'status': 'error',
                'message': f'服务器内部错误: {str(e)}'
            }), 500

    @app.route('/query_accounts', methods=['GET'])
    def query_accounts():
        """查询账号信息 - 支持无账号参数的查询"""
        try:
            # 获取GET参数
            account = request.args.get('account', '').strip()
            link = request.args.get('link', '').strip()
            
            # 数据文件路径
            script_dir = os.path.dirname(os.path.abspath(__file__))
            data_dir = os.path.join(script_dir, 'data')
            filter_data_file = os.path.join(data_dir, 'account_links.json')
            
            print(f"[查询账号] 检查文件: {filter_data_file}")
            print(f"[查询账号] 账号: '{account}', 连接: '{link}'")
            
            # 读取现有数据
            account_links = {}
            if os.path.exists(filter_data_file):
                try:
                    with open(filter_data_file, 'r', encoding='utf-8') as f:
                        account_links = json.load(f)
                except Exception as e:
                    print(f"读取账号连接数据失败: {e}")
                    return jsonify({
                        'status': 'error',
                        'message': f'读取数据文件失败: {str(e)}'
                    }), 500
            
            # 情况1: 没有任何参数 - 返回所有账号信息
            if not account and not link:
                total_accounts = len(account_links)
                total_links = sum(len(links) if isinstance(links, list) else 1 
                                 for links in account_links.values())
                
                return jsonify({
                    'status': 'success',
                    'message': f'找到 {total_accounts} 个账号，共 {total_links} 个连接',
                    'query_type': 'all_accounts',
                    'total_accounts': total_accounts,
                    'total_links': total_links,
                    'accounts': list(account_links.keys()),
                    'account_details': {
                        acc: {
                            'links': links if isinstance(links, list) else [links],
                            'link_count': len(links) if isinstance(links, list) else 1
                        } for acc, links in account_links.items()
                    }
                })
            
            # 情况2: 只有连接参数 - 查找哪个账号有这个连接
            elif not account and link:
                matching_accounts = []
                for acc, links in account_links.items():
                    if isinstance(links, list):
                        if link in links:
                            matching_accounts.append({
                                'account': acc,
                                'all_links': links,
                                'link_count': len(links)
                            })
                    else:
                        if links == link:
                            matching_accounts.append({
                                'account': acc,
                                'all_links': [links],
                                'link_count': 1
                            })
                
                return jsonify({
                    'status': 'success',
                    'message': f'连接 "{link}" 找到 {len(matching_accounts)} 个匹配账号',
                    'query_type': 'by_link',
                    'link': link,
                    'found_count': len(matching_accounts),
                    'matching_accounts': matching_accounts
                })
            
            # 情况3: 只有账号参数 - 返回该账号的所有连接
            elif account and not link:
                if account not in account_links:
                    return jsonify({
                        'status': 'success',
                        'message': f'账号 "{account}" 不存在',
                        'query_type': 'by_account',
                        'account': account,
                        'exists': False,
                        'links': [],
                        'link_count': 0
                    })
                
                links = account_links[account]
                if not isinstance(links, list):
                    links = [links]
                
                return jsonify({
                    'status': 'success',
                    'message': f'账号 "{account}" 有 {len(links)} 个连接',
                    'query_type': 'by_account',
                    'account': account,
                    'exists': True,
                    'links': links,
                    'link_count': len(links)
                })
            
            # 情况4: 有账号和连接参数 - 调用原有的检查逻辑
            else:
                # 重定向到 check_account_link 的逻辑
                if account not in account_links:
                    return jsonify({
                        'status': 'success',
                        'message': '账号不存在',
                        'query_type': 'specific_check',
                        'account': account,
                        'link': link,
                        'exists': False,
                        'account_exists': False,
                        'link_exists': False,
                        'all_links': []
                    })
                
                stored_links = account_links[account]
                if not isinstance(stored_links, list):
                    stored_links = [stored_links]
                
                link_exists = link in stored_links
                
                return jsonify({
                    'status': 'success',
                    'message': '连接已存在' if link_exists else '连接不存在',
                    'query_type': 'specific_check',
                    'account': account,
                    'link': link,
                    'exists': link_exists,
                    'account_exists': True,
                    'link_exists': link_exists,
                    'all_links': stored_links,
                    'total_links': len(stored_links)
                })
                
        except Exception as e:
            return jsonify({
                'status': 'error',
                'message': f'服务器内部错误: {str(e)}'
            }), 500

    @app.route('/delete_account', methods=['GET', 'DELETE', 'POST'])
    def delete_account():
        """删除指定账号及其所有评论链接"""
        try:
            # 支持GET、DELETE和POST方法
            if request.method in ['GET', 'DELETE']:
                # GET和DELETE请求从查询参数获取
                account = request.args.get('account', '').strip()
            else:
                # POST请求从表单或JSON获取
                if request.is_json:
                    data = request.get_json()
                    account = data.get('account', '').strip() if data else ''
                else:
                    account = request.form.get('account', '').strip()
            
            # 验证参数
            if not account:
                return jsonify({
                    'status': 'error',
                    'message': '账号参数不能为空'
                }), 400
            
            # 数据文件路径
            script_dir = os.path.dirname(os.path.abspath(__file__))
            data_dir = os.path.join(script_dir, 'data')
            filter_data_file = os.path.join(data_dir, 'comment_links.json')
            
            print(f"[删除评论账号] 检查文件: {filter_data_file}")
            print(f"[删除评论账号] 要删除的账号: {account}")
            
            # 安全读取现有数据
            account_links = safe_read_json(filter_data_file, {})
            
            # 检查账号是否存在
            if account not in account_links:
                return jsonify({
                    'status': 'success',
                    'message': f'账号 "{account}" 不存在，无需删除',
                    'account': account,
                    'existed': False,
                    'deleted_links': [],
                    'deleted_count': 0
                })
            
            # 获取要删除的连接
            deleted_links = account_links[account]
            if not isinstance(deleted_links, list):
                deleted_links = [deleted_links]
            
            deleted_count = len(deleted_links)
            
            # 删除账号
            del account_links[account]
            
            # 安全保存更新后的数据
            safe_write_json(filter_data_file, account_links)
            
            print(f"[删除评论账号] 成功删除账号 '{account}'，删除了 {deleted_count} 个连接")
            
            return jsonify({
                    'status': 'success',
                    'message': f'账号 "{account}" 及其 {deleted_count} 个连接已删除',
                    'account': account,
                    'existed': True,
                    'deleted_links': deleted_links,
                    'deleted_count': deleted_count,
                    'remaining_accounts': len(account_links)
                })
                
        except Exception as e:
            return jsonify({
                'status': 'error',
                'message': f'服务器内部错误: {str(e)}'
            }), 500

    @app.route('/group_links', methods=['GET'])
    def manage_group_links():
        """管理小组链接 - 带15天数据保留"""
        try:
            # 获取参数
            account = request.args.get('account', '').strip()
            link = request.args.get('link', '').strip()
            action = request.args.get('action', 'add').strip().lower()  # add, check, query
            
            # 数据文件路径
            script_dir = os.path.dirname(os.path.abspath(__file__))
            data_dir = os.path.join(script_dir, 'data')
            group_links_file = os.path.join(data_dir, 'group_links.json')
            
            # 确保数据目录存在
            os.makedirs(data_dir, exist_ok=True)
            
            print(f"[小组链接] 操作: {action}, 账号: {account}, 链接: {link}")
            
            # 安全读取现有数据
            group_data = safe_read_json(group_links_file, {})
            
            # 清理过期数据（超过15天）
            current_date = datetime.now().strftime('%Y-%m-%d')
            cutoff_date = (datetime.now() - timedelta(days=15)).strftime('%Y-%m-%d')
            
            cleaned_data = {}
            total_cleaned = 0
            
            for acc, links_by_date in group_data.items():
                cleaned_links = {}
                for date, links in links_by_date.items():
                    if date >= cutoff_date:
                        cleaned_links[date] = links
                    else:
                        total_cleaned += len(links) if isinstance(links, list) else 1
                
                if cleaned_links:
                    cleaned_data[acc] = cleaned_links
            
            group_data = cleaned_data
            if total_cleaned > 0:
                print(f"[小组链接] 清理了 {total_cleaned} 个过期数据")
            
            # 处理不同操作
            if action == 'add':
                # 添加数据
                if not account or not link:
                    return jsonify({
                        'status': 'error',
                        'message': '账号和链接参数不能为空'
                    }), 400
                
                # 初始化账号数据
                if account not in group_data:
                    group_data[account] = {}
                
                # 初始化日期数据
                if current_date not in group_data[account]:
                    group_data[account][current_date] = []
                
                # 检查链接是否已存在
                if link in group_data[account][current_date]:
                    return jsonify({
                        'status': 'success',
                        'message': '小组链接已存在',
                        'action': 'found',
                        'account': account,
                        'link': link,
                        'date': current_date
                    })
                
                # 添加新链接
                group_data[account][current_date].append(link)
                
                # 安全保存数据
                safe_write_json(group_links_file, group_data)
                
                return jsonify({
                    'status': 'success',
                    'message': '小组链接已添加',
                    'action': 'added',
                    'account': account,
                    'link': link,
                    'date': current_date,
                    'cleaned_expired': total_cleaned
                })
            
            elif action == 'check':
                # 检查数据是否存在
                if not account or not link:
                    return jsonify({
                        'status': 'error',
                        'message': '账号和链接参数不能为空'
                    }), 400
                
                exists = False
                found_date = None
                
                if account in group_data:
                    for date, links in group_data[account].items():
                        if link in links:
                            exists = True
                            found_date = date
                            break
                
                return jsonify({
                    'status': 'success',
                    'message': '小组链接已存在' if exists else '小组链接不存在',
                    'account': account,
                    'link': link,
                    'exists': exists,
                    'found_date': found_date,
                    'cleaned_expired': total_cleaned
                })
            
            elif action == 'query':
                # 查询账号的所有链接
                if not account:
                    return jsonify({
                        'status': 'error',
                        'message': '账号参数不能为空'
                    }), 400
                
                if account not in group_data:
                    return jsonify({
                        'status': 'success',
                        'message': f'账号 "{account}" 没有小组链接',
                        'account': account,
                        'exists': False,
                        'links_by_date': {},
                        'total_links': 0,
                        'cleaned_expired': total_cleaned
                    })
                
                links_by_date = group_data[account]
                total_links = sum(len(links) for links in links_by_date.values())
                
                return jsonify({
                    'status': 'success',
                    'message': f'账号 "{account}" 有 {total_links} 个小组链接',
                    'account': account,
                    'exists': True,
                    'links_by_date': links_by_date,
                    'total_links': total_links,
                    'cleaned_expired': total_cleaned
                })
            
            else:
                return jsonify({
                    'status': 'error',
                    'message': f'不支持的操作: {action}'
                }), 400
                
        except Exception as e:
            return jsonify({
                'status': 'error',
                'message': f'服务器内部错误: {str(e)}'
            }), 500

    @app.route('/delete_group_account', methods=['GET', 'DELETE', 'POST'])
    def delete_group_account():
        """删除账号的所有小组链接"""
        try:
            # 支持GET、DELETE和POST方法
            if request.method in ['GET', 'DELETE']:
                account = request.args.get('account', '').strip()
            else:
                if request.is_json:
                    data = request.get_json()
                    account = data.get('account', '').strip() if data else ''
                else:
                    account = request.form.get('account', '').strip()
            
            if not account:
                return jsonify({
                    'status': 'error',
                    'message': '账号参数不能为空'
                }), 400
            
            # 数据文件路径
            script_dir = os.path.dirname(os.path.abspath(__file__))
            data_dir = os.path.join(script_dir, 'data')
            group_links_file = os.path.join(data_dir, 'group_links.json')
            
            print(f"[删除小组账号] 账号: {account}")
            
            # 读取现有数据
            group_data = {}
            if os.path.exists(group_links_file):
                try:
                    with open(group_links_file, 'r', encoding='utf-8') as f:
                        group_data = json.load(f)
                except Exception as e:
                    return jsonify({
                        'status': 'error',
                        'message': f'读取数据文件失败: {str(e)}'
                    }), 500
            
            # 检查账号是否存在
            if account not in group_data:
                return jsonify({
                    'status': 'success',
                    'message': f'账号 "{account}" 不存在小组链接，无需删除',
                    'account': account,
                    'existed': False,
                    'deleted_links': {},
                    'deleted_count': 0
                })
            
            # 获取要删除的数据
            deleted_links = group_data[account]
            deleted_count = sum(len(links) for links in deleted_links.values())
            
            # 删除账号
            del group_data[account]
            
            # 安全保存数据
            safe_write_json(group_links_file, group_data)
            
            print(f"[删除小组账号] 成功删除账号 '{account}'，删除了 {deleted_count} 个链接")
            
            return jsonify({
                'status': 'success',
                'message': f'账号 "{account}" 的 {deleted_count} 个小组链接已删除',
                'account': account,
                'existed': True,
                'deleted_links': deleted_links,
                'deleted_count': deleted_count,
                'remaining_accounts': len(group_data)
            })
            
        except Exception as e:
            return jsonify({
                'status': 'error',
                'message': f'服务器内部错误: {str(e)}'
            }), 500

    @app.route('/friend_links', methods=['GET'])
    def manage_friend_links():
        """管理加好友链接 - 永久保存，不自动清理"""
        try:
            # 获取参数
            account = request.args.get('account', '').strip()
            link = request.args.get('link', '').strip()
            action = request.args.get('action', 'add').strip().lower()  # add, check, query
            
            # 数据文件路径
            script_dir = os.path.dirname(os.path.abspath(__file__))
            data_dir = os.path.join(script_dir, 'data')
            friend_links_file = os.path.join(data_dir, 'friend_links.json')
            
            # 确保数据目录存在
            os.makedirs(data_dir, exist_ok=True)
            
            print(f"[加好友链接] 操作: {action}, 账号: {account}, 链接: {link}")
            
            # 安全读取现有数据
            friend_data = safe_read_json(friend_links_file, {})
            
            # 不进行数据清理，永久保存
            current_date = datetime.now().strftime('%Y-%m-%d')
            
            # 处理不同操作
            if action == 'add':
                # 添加数据
                if not account or not link:
                    return jsonify({
                        'status': 'error',
                        'message': '账号和链接参数不能为空'
                    }), 400
                
                # 初始化账号数据
                if account not in friend_data:
                    friend_data[account] = {}
                
                # 初始化日期数据
                if current_date not in friend_data[account]:
                    friend_data[account][current_date] = []
                
                # 检查链接是否已存在（检查所有日期）
                exists = False
                for date, links in friend_data[account].items():
                    if link in links:
                        exists = True
                        break
                
                if exists:
                    return jsonify({
                        'status': 'success',
                        'message': '加好友链接已存在',
                        'action': 'found',
                        'account': account,
                        'link': link,
                        'date': current_date
                    })
                
                # 添加新链接到今天
                friend_data[account][current_date].append(link)
                
                # 安全保存数据
                safe_write_json(friend_links_file, friend_data)
                
                return jsonify({
                    'status': 'success',
                    'message': '加好友链接已添加',
                    'action': 'added',
                    'account': account,
                    'link': link,
                    'date': current_date
                })
            
            elif action == 'check':
                # 检查数据是否存在
                if not account or not link:
                    return jsonify({
                        'status': 'error',
                        'message': '账号和链接参数不能为空'
                    }), 400
                
                exists = False
                found_date = None
                
                if account in friend_data:
                    for date, links in friend_data[account].items():
                        if link in links:
                            exists = True
                            found_date = date
                            break
                
                return jsonify({
                    'status': 'success',
                    'message': '加好友链接已存在' if exists else '加好友链接不存在',
                    'account': account,
                    'link': link,
                    'exists': exists,
                    'found_date': found_date
                })
            
            elif action == 'query':
                # 查询账号的所有链接
                if not account:
                    return jsonify({
                        'status': 'error',
                        'message': '账号参数不能为空'
                    }), 400
                
                if account not in friend_data:
                    return jsonify({
                        'status': 'success',
                        'message': f'账号 "{account}" 没有加好友链接',
                        'account': account,
                        'exists': False,
                        'links_by_date': {},
                        'total_links': 0
                    })
                
                links_by_date = friend_data[account]
                total_links = sum(len(links) for links in links_by_date.values())
                
                return jsonify({
                    'status': 'success',
                    'message': f'账号 "{account}" 有 {total_links} 个加好友链接',
                    'account': account,
                    'exists': True,
                    'links_by_date': links_by_date,
                    'total_links': total_links
                })
            
            else:
                return jsonify({
                    'status': 'error',
                    'message': f'不支持的操作: {action}'
                }), 400
                
        except Exception as e:
            return jsonify({
                'status': 'error',
                'message': f'服务器内部错误: {str(e)}'
            }), 500

    @app.route('/delete_friend_account', methods=['GET', 'DELETE', 'POST'])
    def delete_friend_account():
        """删除账号的所有加好友链接"""
        try:
            # 支持GET、DELETE和POST方法
            if request.method in ['GET', 'DELETE']:
                account = request.args.get('account', '').strip()
            else:
                if request.is_json:
                    data = request.get_json()
                    account = data.get('account', '').strip() if data else ''
                else:
                    account = request.form.get('account', '').strip()
            
            if not account:
                return jsonify({
                    'status': 'error',
                    'message': '账号参数不能为空'
                }), 400
            
            # 数据文件路径
            script_dir = os.path.dirname(os.path.abspath(__file__))
            data_dir = os.path.join(script_dir, 'data')
            friend_links_file = os.path.join(data_dir, 'friend_links.json')
            
            print(f"[删除加好友账号] 账号: {account}")
            
            # 读取现有数据
            friend_data = {}
            if os.path.exists(friend_links_file):
                try:
                    with open(friend_links_file, 'r', encoding='utf-8') as f:
                        friend_data = json.load(f)
                except Exception as e:
                    return jsonify({
                        'status': 'error',
                        'message': f'读取数据文件失败: {str(e)}'
                    }), 500
            
            # 检查账号是否存在
            if account not in friend_data:
                return jsonify({
                    'status': 'success',
                    'message': f'账号 "{account}" 不存在加好友链接，无需删除',
                    'account': account,
                    'existed': False,
                    'deleted_links': {},
                    'deleted_count': 0
                })
            
            # 获取要删除的数据
            deleted_links = friend_data[account]
            deleted_count = sum(len(links) for links in deleted_links.values())
            
            # 删除账号
            del friend_data[account]
            
            # 安全保存数据
            safe_write_json(friend_links_file, friend_data)
            
            print(f"[删除加好友账号] 成功删除账号 '{account}'，删除了 {deleted_count} 个链接")
            
            return jsonify({
                'status': 'success',
                'message': f'账号 "{account}" 的 {deleted_count} 个加好友链接已删除',
                'account': account,
                'existed': True,
                'deleted_links': deleted_links,
                'deleted_count': deleted_count,
                'remaining_accounts': len(friend_data)
            })
            
        except Exception as e:
            return jsonify({
                'status': 'error',
                'message': f'服务器内部错误: {str(e)}'
            }), 500
    
    return app

def generate_sample_data():
    """生成示例数据"""
    sample_data = []
    # 生成15天的数据
    for i in range(15):
        date = (datetime.now() - timedelta(days=14-i)).strftime('%Y-%m-%d')
        sample_data.append({
            'date': date,
            'likes': random.randint(50, 500),
            'comments': random.randint(10, 200),
            'shares': random.randint(5, 100),
            'friends': random.randint(1, 50),
            'posts': random.randint(1, 20),
            'accounts': random.randint(1, 10),
            'groups': random.randint(1, 30),
            'forwards': random.randint(1, 50)
        })
    return sample_data

def start_backend_service():
    """启动后端服务"""
    app = create_app()
    return app

# 创建全局的app实例，供外部导入使用
app = create_app()

# 全局变量：waitress服务器实例
_waitress_server = None

def start_waitress_server(host='0.0.0.0', port=8805, threads=4):
    """使用waitress启动服务器（生产级WSGI服务器）"""
    global _waitress_server
    try:
        from waitress import serve
        import socket
        
        # 设置 SO_REUSEADDR，允许立即重用端口
        # 这样即使端口处于 TIME_WAIT 状态也能绑定
        import socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((host, port))
        sock.close()
        
        print(f"[Waitress] 正在启动服务器 ({host}:{port})...")
        print(f"[Waitress] 使用 {threads} 个工作线程")
        
        # 使用waitress启动服务器
        # threads: 工作线程数
        # channel_timeout: 通道超时时间（秒）
        # cleanup_interval: 清理间隔（秒）
        serve(app, host=host, port=port, threads=threads, 
              channel_timeout=30, cleanup_interval=10)
              
    except ImportError:
        print("[ERROR] waitress未安装，请运行: pip install waitress")
        print("[FALLBACK] 使用Flask开发服务器（不推荐生产环境）")
        app.run(host=host, port=port, debug=False, threaded=True)
    except Exception as e:
        print(f"[ERROR] 启动服务器失败: {e}")
        raise

def stop_waitress_server():
    """停止waitress服务器"""
    global _waitress_server
    if _waitress_server:
        try:
            print("[Waitress] 正在停止服务器...")
            _waitress_server.close()
            _waitress_server = None
            print("[Waitress] 服务器已停止")
        except Exception as e:
            print(f"[ERROR] 停止服务器失败: {e}")

def main():
    """主函数 - 独立运行后端服务"""
    print("正在启动后端服务...")
    print("后端服务已启动，监听端口 8805")
    print("请访问 http://localhost:8805 查看页面")
    print("按 Ctrl+C 停止服务")
    
    try:
        # 使用waitress启动服务（生产级服务器）
        start_waitress_server(host='0.0.0.0', port=8805, threads=4)
    except KeyboardInterrupt:
        print("\n收到停止信号，正在关闭服务器...")
        stop_waitress_server()

if __name__ == "__main__":
    main()