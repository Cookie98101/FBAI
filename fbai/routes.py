import os
import sys
import json
import subprocess
from flask import jsonify, request
from datetime import datetime

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def register_routes(app):
    """注册扩展功能路由"""
    
    @app.route('/execute_program', methods=['POST'])
    def execute_program():
        """执行外部程序"""
        try:
            # 获取请求数据
            data = request.get_json()
            if not data:
                return jsonify({
                    'status': 'error',
                    'message': '缺少请求数据'
                }), 400
            
            program_path = data.get('program_path')
            arguments = data.get('arguments', [])
            
            if not program_path:
                return jsonify({
                    'status': 'error',
                    'message': '缺少程序路径'
                }), 400
            
            # 检查程序文件是否存在
            if not os.path.exists(program_path):
                return jsonify({
                    'status': 'error',
                    'message': f'程序文件不存在: {program_path}'
                }), 400
            
            # 执行程序
            cmd = [program_path] + arguments
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30,  # 设置超时时间
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
            )
            
            return jsonify({
                'status': 'success',
                'message': '程序执行成功',
                'data': {
                    'return_code': result.returncode,
                    'stdout': result.stdout,
                    'stderr': result.stderr
                }
            })
            
        except subprocess.TimeoutExpired:
            return jsonify({
                'status': 'error',
                'message': '程序执行超时'
            }), 408
        except Exception as e:
            return jsonify({
                'status': 'error',
                'message': f'执行程序时出错: {str(e)}'
            }), 500
    
    @app.route('/generate_video', methods=['GET'])
    def generate_video():
        """通过GET请求生成视频"""
        try:
            print(f"[DEBUG] 收到视频生成请求: {request.args}")
            print(f"[DEBUG] 请求URL: {request.url}")
            print(f"[DEBUG] 请求方法: {request.method}")
            print(f"[DEBUG] 请求头: {dict(request.headers)}")
            # 获取GET参数
            prompt = request.args.get('prompt', '')  # AI提示词
            # 修复编码问题
            if prompt:
                try:
                    # 尝试解码URL编码的参数
                    import urllib.parse
                    prompt = urllib.parse.unquote(prompt, encoding='utf-8')
                except Exception as e:
                    print(f"[DEBUG] 解码提示词时出错: {e}")
            print(f"[DEBUG] 提示词: {prompt}")
            
            # 尝试从UI配置文件加载其他参数的默认值
            ui_config = {}
            ui_config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'moviepy', 'ui_config.json')
            if os.path.exists(ui_config_path):
                with open(ui_config_path, 'r', encoding='utf-8') as f:
                    ui_config = json.load(f)
            print(f"[DEBUG] UI配置: {ui_config}")
            
            # 从UI配置或默认值获取参数
            duration = request.args.get('duration') or ui_config.get('duration', '30')  # 视频时长（秒）
            style = request.args.get('style') or ui_config.get('style', '旅行')  # 视频风格
            video_folder = request.args.get('video_folder') or ui_config.get('video_folder', '视频素材')  # 视频素材文件夹
            audio_folder = request.args.get('audio_folder') or ui_config.get('audio_folder', '音频素材')  # 音频素材文件夹
            no_audio = request.args.get('no_audio', '').lower() == 'true' or ui_config.get('no_audio', False)  # 是否无音频
            
            print(f"[DEBUG] 参数 - 时长: {duration}, 风格: {style}, 视频文件夹: {video_folder}, 音频文件夹: {audio_folder}, 无音频: {no_audio}")
            
            # 构建命令行参数
            cmd = [
                sys.executable, 
                os.path.join(os.path.dirname(os.path.abspath(__file__)), 'moviepy', 'random_video_editor.py'),
                '--prompt', prompt,
                '--duration', duration,
                '--style', style,
                '--video-folder', video_folder,
                '--audio-folder', audio_folder
            ]
            
            # 如果需要无音频，添加相应参数
            if no_audio:
                cmd.append('--no-audio')
            
            print(f"[DEBUG] 执行命令: {' '.join(cmd)}")
            
            # 执行视频生成脚本
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding='utf-8',  # 显式设置编码为UTF-8
                timeout=300,  # 设置较长的超时时间（5分钟）
                cwd=os.path.dirname(os.path.abspath(__file__)),  # 设置工作目录
                env={**os.environ, 'PYTHONIOENCODING': 'utf-8'},  # 设置环境变量确保子进程使用UTF-8编码
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
            )
            
            print(f"[DEBUG] 命令执行完成，返回码: {result.returncode}")
            print(f"[DEBUG] 标准输出: {result.stdout}")
            print(f"[DEBUG] 错误输出: {result.stderr}")
            
            # 返回执行结果
            if result.returncode == 0:
                response_data = {
                    'status': 'success',
                    'message': '视频生成成功',
                    'data': {
                        'return_code': result.returncode,
                        'stdout': result.stdout,
                        'stderr': result.stderr
                    }
                }
                print(f"[DEBUG] 返回成功响应: {response_data}")
                response = jsonify(response_data)
                response.headers['Content-Type'] = 'application/json; charset=utf-8'
                return response
            else:
                response_data = {
                    'status': 'error',
                    'message': '视频生成失败',
                    'data': {
                        'return_code': result.returncode,
                        'stdout': result.stdout,
                        'stderr': result.stderr
                    }
                }
                print(f"[DEBUG] 返回错误响应: {response_data}")
                response = jsonify(response_data)
                response.headers['Content-Type'] = 'application/json; charset=utf-8'
                return response, 500
                
        except subprocess.TimeoutExpired:
            return jsonify({
                'status': 'error',
                'message': '视频生成超时'
            }), 500
        except Exception as e:
            return jsonify({
                'status': 'error',
                'message': f'视频生成过程中发生错误: {str(e)}'
            }), 500
    
    @app.route('/get_system_info')
    def get_system_info():
        """获取系统信息"""
        try:
            import platform
            info = {
                'system': platform.system(),
                'release': platform.release(),
                'version': platform.version(),
                'machine': platform.machine(),
                'processor': platform.processor(),
                'python_version': platform.python_version()
            }
            
            return jsonify({
                'status': 'success',
                'data': info,
                'message': '系统信息获取成功'
            })
        except Exception as e:
            return jsonify({
                'status': 'error',
                'message': f'获取系统信息时出错: {str(e)}'
            }), 500
    
    @app.route('/update_config', methods=['POST'])
    def update_config():
        """更新配置文件"""
        try:
            # 获取请求数据
            data = request.get_json()
            if not data:
                return jsonify({
                    'status': 'error',
                    'message': '缺少请求数据'
                }), 400
            
            config_file = "config.json"
            
            # 读取现有配置
            config = {}
            if os.path.exists(config_file):
                with open(config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
            
            # 更新配置
            config.update(data)
            
            # 保存配置
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
            
            return jsonify({
                'status': 'success',
                'message': '配置更新成功',
                'data': config
            })
        except Exception as e:
            return jsonify({
                'status': 'error',
                'message': f'更新配置时出错: {str(e)}'
            }), 500
    
    @app.route('/get_config')
    def get_config():
        """获取配置文件"""
        try:
            config_file = "config.json"
            
            # 检查配置文件是否存在
            if not os.path.exists(config_file):
                return jsonify({
                    'status': 'success',
                    'data': {},
                    'message': '配置文件不存在'
                })
            
            # 读取配置
            with open(config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            return jsonify({
                'status': 'success',
                'data': config,
                'message': '配置获取成功'
            })
        except Exception as e:
            return jsonify({
                'status': 'error',
                'message': f'获取配置时出错: {str(e)}'
            }), 500
    
    return app