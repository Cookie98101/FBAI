#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FFmpeg配置模块
用于打包后正确配置FFmpeg路径
"""

import os
import sys

def setup_ffmpeg():
    """
    配置FFmpeg路径（打包后使用）
    
    返回:
        bool: 配置是否成功
    """
    try:
        # 检测是否是打包后的环境
        if getattr(sys, 'frozen', False):
            # 打包后的路径
            base_path = sys._MEIPASS
            print(f"[FFmpeg配置] 检测到打包环境，Base Path: {base_path}")
            
            # 可能的FFmpeg位置（按优先级）
            ffmpeg_candidates = [
                # PyInstaller onefile模式
                os.path.join(base_path, 'imageio_ffmpeg', 'binaries', 'ffmpeg-win64-v4.2.2.exe'),
                os.path.join(base_path, 'imageio_ffmpeg', 'binaries', 'ffmpeg-win-x86_64-v7.1.exe'),
                os.path.join(base_path, 'imageio_ffmpeg', 'binaries', 'ffmpeg.exe'),
                
                # PyInstaller onedir模式
                os.path.join(base_path, '..', 'imageio_ffmpeg', 'binaries', 'ffmpeg.exe'),
                
                # 独立FFmpeg（如果手动添加）
                os.path.join(base_path, 'ffmpeg.exe'),
                os.path.join(base_path, 'bin', 'ffmpeg.exe'),
            ]
            
            # 查找FFmpeg并验证权限
            ffmpeg_path = None
            for candidate in ffmpeg_candidates:
                if os.path.exists(candidate):
                    # 检查文件是否可读和可执行
                    if os.access(candidate, os.R_OK | os.X_OK):
                        ffmpeg_path = candidate
                        print(f"[FFmpeg配置] ✓ 找到FFmpeg: {ffmpeg_path}")
                        print(f"[FFmpeg配置] ✓ 权限检查通过")
                        break
                    else:
                        print(f"[FFmpeg配置] ⚠️ 找到FFmpeg但权限不足: {candidate}")
                        print(f"[FFmpeg配置] ⚠️ 提示：请尝试以管理员身份运行程序")
            
            if not ffmpeg_path:
                print(f"[FFmpeg配置] ✗ 未找到可用的FFmpeg，尝试的路径：")
                for candidate in ffmpeg_candidates:
                    exists = "存在" if os.path.exists(candidate) else "不存在"
                    print(f"  - {candidate} ({exists})")
                print(f"[FFmpeg配置] ⚠️ 警告：视频编辑功能可能无法使用")
                print(f"[FFmpeg配置] 💡 建议：")
                print(f"  1. 以管理员身份运行程序")
                print(f"  2. 将程序移到非系统目录（如D:\\Program\\）")
                print(f"  3. 添加到杀毒软件白名单")
                return False
            
            # 设置环境变量
            os.environ['IMAGEIO_FFMPEG_EXE'] = ffmpeg_path
            os.environ['FFMPEG_BINARY'] = ffmpeg_path
            print(f"[FFmpeg配置] ✓ 环境变量已设置")
            
            # 配置moviepy
            try:
                import moviepy.config as moviepy_config
                moviepy_config.FFMPEG_BINARY = ffmpeg_path
                print(f"[FFmpeg配置] ✓ MoviePy配置成功")
            except Exception as e:
                print(f"[FFmpeg配置] ⚠️ MoviePy配置警告: {e}")
            
            # 配置imageio
            try:
                import imageio_ffmpeg
                # 强制设置ffmpeg路径
                imageio_ffmpeg._exe = ffmpeg_path
                print(f"[FFmpeg配置] ✓ imageio_ffmpeg配置成功")
            except Exception as e:
                print(f"[FFmpeg配置] ⚠️ imageio_ffmpeg配置警告: {e}")
            
            return True
            
        else:
            # 开发环境，使用默认配置
            print(f"[FFmpeg配置] ✓ 开发环境，使用系统FFmpeg")
            
            # 验证FFmpeg是否可用
            try:
                import imageio_ffmpeg
                ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
                print(f"[FFmpeg配置] ✓ 系统FFmpeg: {ffmpeg_exe}")
                return True
            except Exception as e:
                print(f"[FFmpeg配置] ✗ 系统FFmpeg错误: {e}")
                return False
            
    except Exception as e:
        print(f"[FFmpeg配置] ✗ 配置失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_ffmpeg():
    """
    测试FFmpeg是否正常工作
    
    返回:
        bool: 测试是否通过
    """
    try:
        print("\n[FFmpeg测试] 开始测试FFmpeg功能...")
        
        # 测试1：导入moviepy
        try:
            import moviepy
            print(f"[FFmpeg测试] ✓ MoviePy版本: {moviepy.__version__}")
        except Exception as e:
            print(f"[FFmpeg测试] ✗ MoviePy导入失败: {e}")
            return False
        
        # 测试2：检查FFmpeg路径
        try:
            import imageio_ffmpeg
            ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
            print(f"[FFmpeg测试] ✓ FFmpeg路径: {ffmpeg_exe}")
            
            if not os.path.exists(ffmpeg_exe):
                print(f"[FFmpeg测试] ✗ FFmpeg文件不存在")
                return False
                
            file_size = os.path.getsize(ffmpeg_exe) / (1024 * 1024)
            print(f"[FFmpeg测试] ✓ FFmpeg大小: {file_size:.2f} MB")
            
        except Exception as e:
            print(f"[FFmpeg测试] ✗ FFmpeg路径检查失败: {e}")
            return False
        
        # 测试3：尝试导入关键模块
        try:
            from moviepy.video.io.VideoFileClip import VideoFileClip
            from moviepy.audio.io.AudioFileClip import AudioFileClip
            print(f"[FFmpeg测试] ✓ MoviePy关键模块导入成功")
        except Exception as e:
            print(f"[FFmpeg测试] ✗ MoviePy模块导入失败: {e}")
            return False
        
        print(f"[FFmpeg测试] ✓ 所有测试通过\n")
        return True
        
    except Exception as e:
        print(f"[FFmpeg测试] ✗ 测试失败: {e}\n")
        return False


def print_ffmpeg_info():
    """打印FFmpeg相关信息（用于调试）"""
    print("\n" + "=" * 70)
    print("FFmpeg调试信息")
    print("=" * 70)
    
    # 1. 运行环境
    if getattr(sys, 'frozen', False):
        print(f"✓ 运行环境: 打包后")
        print(f"  Base Path (_MEIPASS): {sys._MEIPASS}")
    else:
        print(f"✓ 运行环境: 开发环境")
        print(f"  工作目录: {os.getcwd()}")
    
    # 2. Python信息
    print(f"\nPython信息:")
    print(f"  版本: {sys.version}")
    print(f"  可执行文件: {sys.executable}")
    
    # 3. FFmpeg路径
    print(f"\nFFmpeg路径:")
    try:
        import imageio_ffmpeg
        ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
        print(f"  路径: {ffmpeg_exe}")
        print(f"  文件存在: {os.path.exists(ffmpeg_exe)}")
        if os.path.exists(ffmpeg_exe):
            print(f"  文件大小: {os.path.getsize(ffmpeg_exe)} 字节")
    except Exception as e:
        print(f"  错误: {e}")
    
    # 4. 环境变量
    print(f"\n环境变量:")
    print(f"  IMAGEIO_FFMPEG_EXE: {os.environ.get('IMAGEIO_FFMPEG_EXE', '未设置')}")
    print(f"  FFMPEG_BINARY: {os.environ.get('FFMPEG_BINARY', '未设置')}")
    
    # 5. MoviePy配置
    print(f"\nMoviePy配置:")
    try:
        import moviepy.config as moviepy_config
        print(f"  FFMPEG_BINARY: {getattr(moviepy_config, 'FFMPEG_BINARY', '未设置')}")
    except Exception as e:
        print(f"  错误: {e}")
    
    # 6. 已安装的包
    print(f"\n相关包版本:")
    packages = ['moviepy', 'imageio', 'imageio-ffmpeg', 'proglog']
    for pkg in packages:
        try:
            module = __import__(pkg.replace('-', '_'))
            version = getattr(module, '__version__', '未知')
            print(f"  {pkg}: {version}")
        except:
            print(f"  {pkg}: 未安装")
    
    print("=" * 70 + "\n")


# 使用示例
if __name__ == "__main__":
    # 配置FFmpeg
    success = setup_ffmpeg()
    
    # 打印详细信息
    print_ffmpeg_info()
    
    # 测试FFmpeg
    if success:
        test_ffmpeg()
    
    print("\n提示: 在主程序中导入此模块并在启动时调用 setup_ffmpeg()")
