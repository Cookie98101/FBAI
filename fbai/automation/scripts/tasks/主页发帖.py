"""
主页发帖任务
在 Facebook 公共主页发布帖子

特性：
- 支持文本发帖
- 支持AI生成发帖内容
- 模拟真人操作
- 支持调试模式
- 支持Selenium和JavaScript两种方式

使用方法：
- Selenium方式：主页发帖(driver, 提示词, ...)
- JavaScript方式：生成JavaScript代码用于QtWebEngine
- 调试模式：修改 DEBUG_BROWSER_ID，直接运行此文件
"""

import os
import sys
import time
import random
import re
from typing import TYPE_CHECKING, Optional, Callable
from urllib.parse import urlparse, parse_qs

if TYPE_CHECKING:
    from selenium.webdriver.remote.webdriver import WebDriver

# ==================== 调试配置 ====================

# 优先使用调试面板传入的浏览器ID（facebook_dashboard.py 会设置环境变量 DEBUG_BROWSER_ID）
DEBUG_BROWSER_ID = os.environ.get("DEBUG_BROWSER_ID") or ""  # 修改为你的浏览器ID进行调试

# ==================== JavaScript代码生成 ====================

def 生成发帖JavaScript(内容: str, 使用AI: bool = False, 媒体文件路径: str = None) -> str:
    """
    生成用于QtWebEngine的JavaScript发帖代码
    
    Args:
        内容: 发帖内容或提示词
        使用AI: 是否使用AI生成内容（暂不支持）
        媒体文件路径: 媒体文件的完整路径（可选）
    
    Returns:
        JavaScript代码字符串
    """
    # 转义文本
    escaped_text = 内容.replace('\\', '\\\\').replace("'", "\\'").replace('\n', '\\n').replace('\r', '')
    
    # 注意：JavaScript无法直接访问本地文件系统
    # 媒体上传需要通过Python端处理，这里只是占位
    has_media = 媒体文件路径 is not None
    
    js_code = f'''
    (async function() {{
        console.log('🚀 开始自动化发帖（公共主页）...');
        console.log('📊 媒体文件: {has_media}');
        
        // 延迟函数
        const delay = ms => new Promise(r => setTimeout(r, ms));
        
        // 模拟真实点击
        function click(el) {{
            if (!el) return false;
            el.dispatchEvent(new MouseEvent('mousedown', {{bubbles: true, cancelable: true, view: window}}));
            el.dispatchEvent(new MouseEvent('mouseup', {{bubbles: true, cancelable: true, view: window}}));
            el.dispatchEvent(new MouseEvent('click', {{bubbles: true, cancelable: true, view: window}}));
            return true;
        }}
        
        // 等待元素出现
        async function waitFor(finder, timeout = 10000, interval = 300) {{
            const start = Date.now();
            while (Date.now() - start < timeout) {{
                const el = finder();
                if (el) return el;
                await delay(interval);
            }}
            return null;
        }}
        
        try {{
            // ========== 步骤1: 点击发帖入口 ==========
            console.log('📝 步骤1: 查找发帖入口...');
            
            let postEntry = null;
            const allElements = document.querySelectorAll('*');
            console.log('📊 页面总元素数:', allElements.length);
            
            for (const el of allElements) {{
                const text = el.textContent || '';
                
                // 跳过顶层元素（HTML, BODY, HEAD）
                if (['HTML', 'BODY', 'HEAD'].includes(el.tagName)) {{
                    continue;
                }}
                
                if ((text.includes('分享') && text.includes('新鲜事')) || 
                    (text.toLowerCase().includes('share') && text.toLowerCase().includes('something'))) {{
                    
                    // 确保文本长度合理（不是整个页面的文本）
                    if (text.length > 500) {{
                        continue;
                    }}
                    
                    console.log('✓ 找到匹配元素:', el.tagName, text.substring(0, 50));
                    
                    // 向上查找可点击的父元素
                    let current = el;
                    for (let i = 0; i < 15; i++) {{
                        if (!current) break;
                        
                        // 跳过顶层元素
                        if (['HTML', 'BODY', 'HEAD'].includes(current.tagName)) {{
                            current = current.parentElement;
                            continue;
                        }}
                        
                        const role = current.getAttribute('role');
                        const tabindex = current.getAttribute('tabindex');
                        const onclick = current.onclick;
                        
                        console.log(`  层级${{i}}: ${{current.tagName}}, role=${{role}}, tabindex=${{tabindex}}, has_onclick=${{!!onclick}}`);
                        
                        if (role === 'button' || role === 'link' || tabindex === '0' || onclick) {{
                            postEntry = current;
                            console.log('🎯 找到可点击父元素');
                            break;
                        }}
                        
                        current = current.parentElement;
                    }}
                    
                    if (postEntry) break;
                }}
            }}
            
            if (!postEntry) {{
                throw new Error('未找到发帖入口');
            }}
            
            click(postEntry);
            console.log('✅ 已点击发帖入口');
            await delay(3000);
            
            // 验证弹窗是否出现
            let dialogsCheck = document.querySelectorAll('[role="dialog"]');
            if (dialogsCheck.length === 0) {{
                console.log('⚠️ 未检测到弹窗，尝试再次点击...');
                click(postEntry);
                await delay(3000);
            }} else {{
                console.log('✓ 检测到弹窗');
            }}
            
            // ========== 步骤2: 查找编辑器 ==========
            console.log('📝 步骤2: 查找编辑器...');
            
            // 先调试：查看弹窗内容
            const dialogs = document.querySelectorAll('[role="dialog"]');
            console.log(`📊 弹窗数量: ${{dialogs.length}}`);
            
            dialogs.forEach((dlg, idx) => {{
                console.log(`弹窗 ${{idx + 1}}:`);
                const editables = dlg.querySelectorAll('[contenteditable="true"]');
                console.log(`  - contenteditable元素数: ${{editables.length}}`);
                editables.forEach((el, i) => {{
                    console.log(`    [${{i}}] 标签:${{el.tagName}}, role:${{el.getAttribute('role')}}, 可见:${{el.offsetParent !== null}}, 文本:${{el.textContent.substring(0, 30)}}`);
                }});
                
                const textboxes = dlg.querySelectorAll('[role="textbox"]');
                console.log(`  - role=textbox元素数: ${{textboxes.length}}`);
                textboxes.forEach((el, i) => {{
                    console.log(`    [${{i}}] 标签:${{el.tagName}}, contenteditable:${{el.getAttribute('contenteditable')}}, 可见:${{el.offsetParent !== null}}`);
                }});
                
                const inputs = dlg.querySelectorAll('input, textarea');
                console.log(`  - input/textarea元素数: ${{inputs.length}}`);
            }});
            
            let editor = await waitFor(() => {{
                const dialogs = document.querySelectorAll('[role="dialog"]');
                for (const dlg of dialogs) {{
                    // 方法1: 查找contenteditable
                    const editables = dlg.querySelectorAll('[contenteditable="true"]');
                    for (const el of editables) {{
                        if (el.offsetParent !== null) {{
                            console.log('✓ 通过contenteditable找到编辑器');
                            return el;
                        }}
                    }}
                    
                    // 方法2: 查找role=textbox
                    const textboxes = dlg.querySelectorAll('[role="textbox"]');
                    for (const el of textboxes) {{
                        if (el.offsetParent !== null) {{
                            console.log('✓ 通过role=textbox找到编辑器');
                            return el;
                        }}
                    }}
                    
                    // 方法3: 查找特定class（Facebook常用）
                    const fbEditors = dlg.querySelectorAll('.notranslate, [data-lexical-editor="true"]');
                    for (const el of fbEditors) {{
                        if (el.offsetParent !== null && el.getAttribute('contenteditable') === 'true') {{
                            console.log('✓ 通过Facebook特定class找到编辑器');
                            return el;
                        }}
                    }}
                }}
                return null;
            }}, 10000);
            
            if (!editor) {{
                console.log('❌ 所有方法都未找到编辑器');
                throw new Error('未找到编辑器');
            }}
            
            console.log('✅ 找到编辑器:', editor.tagName, editor.className);
            
            // ========== 步骤3: 输入文本 ==========
            const postText = '{escaped_text}';
            editor.focus();
            await delay(500);
            
            editor.innerHTML = '';
            await delay(200);
            
            document.execCommand('insertText', false, postText);
            if (!editor.textContent || editor.textContent.trim() === '') {{
                editor.textContent = postText;
            }}
            
            editor.dispatchEvent(new InputEvent('input', {{bubbles: true, data: postText}}));
            editor.dispatchEvent(new Event('change', {{bubbles: true}}));
            
            console.log('✅ 已输入文本');
            await delay(2000);
            
            // ========== 步骤3.5: 点击"更多"按钮（三个点）==========
            console.log('📝 步骤3.5: 查找并点击"更多"按钮...');
            
            let moreBtn = null;
            const moreSelectors = [
                '[aria-label="更多"]',
                '[aria-label="More"]',
                '[aria-label="更多选项"]',
                '[aria-label="More options"]'
            ];
            
            for (const selector of moreSelectors) {{
                try {{
                    const btns = document.querySelectorAll(selector);
                    for (const btn of btns) {{
                        if (btn.offsetParent !== null) {{
                            moreBtn = btn;
                            console.log(`✓ 找到"更多"按钮: ${{selector}}`);
                            break;
                        }}
                    }}
                    if (moreBtn) break;
                }} catch(e) {{}}
            }}
            
            if (moreBtn) {{
                click(moreBtn);
                console.log('✅ 已点击"更多"按钮');
                await delay(2000);
                
                // 查找并点击"接收 WhatsApp 消息"或类似选项
                console.log('📝 查找WhatsApp选项...');
                const whatsappTexts = ['WhatsApp', 'whatsapp'];
                let whatsappOption = null;
                
                for (const text of whatsappTexts) {{
                    const elements = document.querySelectorAll(`[role="menuitem"], [role="button"]`);
                    for (const el of elements) {{
                        if (el.textContent.includes(text) && el.offsetParent !== null) {{
                            whatsappOption = el;
                            console.log('✓ 找到WhatsApp选项');
                            break;
                        }}
                    }}
                    if (whatsappOption) break;
                }}
                
                if (whatsappOption) {{
                    click(whatsappOption);
                    console.log('✅ 已点击WhatsApp选项');
                    await delay(2000);
                }} else {{
                    console.log('⚠️ 未找到WhatsApp选项，继续...');
                }}
                
                // 如果有媒体文件，查找并操作文件输入元素
                if ({str(has_media).lower()}) {{
                    console.log('📝 步骤: 上传媒体文件...');
                    
                    // 步骤1: 查找 input[type="file"]
                    let fileInput = null;
                    const fileInputs = document.querySelectorAll('input[type="file"]');
                    console.log(`找到 ${{fileInputs.length}} 个文件输入元素`);
                    
                    for (const input of fileInputs) {{
                        const inDialog = input.closest('[role="dialog"]');
                        if (inDialog || input.offsetParent !== null) {{
                            fileInput = input;
                            console.log('✓ 找到文件输入元素（在弹窗中）');
                            break;
                        }}
                    }}
                    
                    if (!fileInput && fileInputs.length > 0) {{
                        fileInput = fileInputs[fileInputs.length - 1];
                        console.log('✓ 使用最后一个文件输入元素');
                    }}
                    
                    if (fileInput) {{
                        console.log('✅ 准备触发文件选择');
                        console.log('  accept:', fileInput.getAttribute('accept'));
                        console.log('  multiple:', fileInput.hasAttribute('multiple'));
                        
                        // 触发文件选择（Python端会自动填充文件）
                        fileInput.click();
                        console.log('✅ 已触发文件选择');
                        
                        // 等待文件选择完成
                        await delay(1000);
                        console.log('⏳ 文件已选择，通知Python点击按钮');
                        
                        // 返回特殊标记，让Python知道需要点击按钮
                        return {{success: false, error: '需要Python点击添加照片/视频按钮', needPythonClick: true}};
                    }} else {{
                        console.log('❌ 未找到文件输入元素');
                        console.log('⚠️ 将尝试纯文本发帖');
                    }}
                }} else {{
                    console.log('ℹ️ 没有媒体文件，纯文本发帖');
                }}
            }} else {{
                console.log('⚠️ 未找到"更多"按钮，直接查找发布按钮...');
            }}
            
            // ========== 步骤4: 点击发布按钮 ==========
            console.log('📝 步骤4: 查找发布按钮...');
            
            let submitBtn = await waitFor(() => {{
                const dialogs = document.querySelectorAll('[role="dialog"]');
                for (const dlg of dialogs) {{
                    let btn = dlg.querySelector('[aria-label="发布"]') ||
                              dlg.querySelector('[aria-label="Post"]');
                    if (btn) return btn;
                    
                    const btns = dlg.querySelectorAll('[role="button"], button');
                    for (const b of btns) {{
                        const txt = (b.textContent || '').trim();
                        if ((txt === '发布' || txt === 'Post') && b.offsetParent !== null) {{
                            return b;
                        }}
                    }}
                }}
                return null;
            }}, 8000);
            
            if (!submitBtn) {{
                throw new Error('未找到发布按钮');
            }}
            
            console.log('✅ 找到发布按钮');
            
            // 检查按钮状态
            if (submitBtn.getAttribute('aria-disabled') === 'true') {{
                console.log('⚠️ 发布按钮被禁用，等待...');
                await delay(3000);
            }}
            
            click(submitBtn);
            console.log('✅ 已点击发布按钮');
            await delay(2000);
            
            console.log('🎉 发帖流程完成！');
            return {{success: true}};
            
        }} catch (error) {{
            console.error('❌ 发帖失败:', error);
            return {{success: false, error: error.message}};
        }}
    }})();
    '''
    
    return js_code

# ==================== 媒体文件处理 ====================

def 计算文件MD5(文件路径: str) -> str:
    """
    计算文件的MD5值
    
    Args:
        文件路径: 文件的完整路径
    
    Returns:
        MD5哈希值（32位十六进制字符串）
    """
    import hashlib
    
    md5_hash = hashlib.md5()
    try:
        with open(文件路径, 'rb') as f:
            # 分块读取，避免大文件占用过多内存
            for chunk in iter(lambda: f.read(4096), b""):
                md5_hash.update(chunk)
        return md5_hash.hexdigest()
    except Exception as e:
        print(f"[MD5计算] 计算失败: {e}")
        return "unknown"

def 修改媒体文件MD5(原始文件路径: str, log_func: Callable = None) -> str:
    """
    创建媒体文件的副本并修改其MD5值
    通过添加随机元数据来改变文件指纹，避免被Facebook检测为重复内容
    
    Args:
        原始文件路径: 原始媒体文件的完整路径
        log_func: 日志函数（可选）
    
    Returns:
        修改后的临时文件路径
    """
    import hashlib
    import shutil
    from PIL import Image
    from PIL.PngImagePlugin import PngInfo
    
    def log(msg):
        if log_func:
            log_func(msg)
        print(msg)
    
    try:
        # 计算原始文件的MD5
        原始MD5 = 计算文件MD5(原始文件路径)
        log(f"[MD5修改] 原始文件MD5: {原始MD5}")
        
        # 获取文件扩展名
        文件名, 扩展名 = os.path.splitext(原始文件路径)
        扩展名 = 扩展名.lower()
        
        # 创建临时文件路径
        临时目录 = os.path.join(os.path.dirname(原始文件路径), ".temp_media")
        os.makedirs(临时目录, exist_ok=True)
        
        随机标识 = hashlib.md5(str(time.time()).encode()).hexdigest()[:8]
        临时文件路径 = os.path.join(临时目录, f"modified_{随机标识}{扩展名}")
        
        # 图片文件：添加元数据
        if 扩展名 in ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp']:
            try:
                img = Image.open(原始文件路径)
                
                # 生成随机元数据
                随机数据 = {
                    'timestamp': str(time.time()),
                    'random': str(random.randint(100000, 999999)),
                    'uuid': hashlib.md5(str(random.random()).encode()).hexdigest()
                }
                
                if 扩展名 == '.png':
                    # PNG格式：添加文本元数据
                    metadata = PngInfo()
                    for key, value in 随机数据.items():
                        metadata.add_text(key, value)
                    img.save(临时文件路径, pnginfo=metadata, optimize=False)
                    
                elif 扩展名 in ['.jpg', '.jpeg']:
                    # JPEG格式：修改EXIF数据
                    from PIL import ExifTags
                    
                    exif = img.getexif()
                    if exif is None:
                        exif = {}
                    
                    # 添加/修改注释字段
                    exif[0x9286] = f"Modified_{随机数据['uuid']}"  # UserComment
                    
                    img.save(临时文件路径, exif=exif, quality=95, optimize=False)
                    
                else:
                    # 其他格式：直接保存（会重新编码）
                    img.save(临时文件路径, optimize=False)
                
                # 计算修改后的MD5
                修改后MD5 = 计算文件MD5(临时文件路径)
                log(f"[MD5修改] 修改后MD5: {修改后MD5}")
                log(f"[MD5修改] ✅ MD5已改变，文件: {os.path.basename(临时文件路径)}")
                
                return 临时文件路径
                
            except Exception as img_error:
                log(f"[媒体处理] 图片处理失败，使用原文件: {img_error}")
                return 原始文件路径
        
        # 视频文件：在文件末尾添加随机字节
        elif 扩展名 in ['.mp4', '.avi', '.mov', '.mkv', '.flv', '.wmv', '.webm']:
            try:
                # 复制原文件
                shutil.copy2(原始文件路径, 临时文件路径)
                
                # 在文件末尾添加随机注释（不影响视频播放）
                with open(临时文件路径, 'ab') as f:
                    # 添加随机字节作为注释
                    随机字节 = os.urandom(random.randint(100, 500))
                    注释标记 = b'\x00\x00\x00\x00RANDOM_METADATA\x00'
                    f.write(注释标记 + 随机字节)
                
                # 计算修改后的MD5
                修改后MD5 = 计算文件MD5(临时文件路径)
                log(f"[MD5修改] 修改后MD5: {修改后MD5}")
                log(f"[MD5修改] ✅ MD5已改变，文件: {os.path.basename(临时文件路径)}")
                
                return 临时文件路径
                
            except Exception as video_error:
                log(f"[媒体处理] 视频处理失败，使用原文件: {video_error}")
                return 原始文件路径
        
        else:
            # 不支持的格式，返回原文件
            log(f"[媒体处理] 不支持的格式 {扩展名}，使用原文件")
            return 原始文件路径
            
    except Exception as e:
        log(f"[媒体处理] 处理失败: {e}")
        return 原始文件路径

def 清理临时媒体文件(文件路径: str):
    """
    清理临时创建的媒体文件
    
    Args:
        文件路径: 临时文件路径
    """
    try:
        if ".temp_media" in 文件路径 and os.path.exists(文件路径):
            os.remove(文件路径)
            print(f"[媒体处理] 已清理临时文件: {os.path.basename(文件路径)}")
            
            # 如果临时目录为空，删除目录
            临时目录 = os.path.dirname(文件路径)
            if os.path.exists(临时目录) and not os.listdir(临时目录):
                os.rmdir(临时目录)
                print(f"[媒体处理] 已清理临时目录")
    except Exception as e:
        print(f"[媒体处理] 清理临时文件失败: {e}")

# ==================== AI 内容生成 ====================

def 清理AI响应(response: str) -> str:
    """
    清理 AI 响应，提取【】中的内容
    
    Args:
        response: AI 原始响应
    
    Returns:
        清理后的内容
    """
    if not response:
        return ""
    
    # 尝试提取【】中的内容
    match = re.search(r'【(.+?)】', response, re.DOTALL)
    if match:
        content = match.group(1).strip()
        return content
    
    # 如果没有【】，去除 think 标签等
    response = re.sub(r'<think>.*?</think>', '', response, flags=re.DOTALL)
    response = re.sub(r'<[^>]+>', '', response)
    return response.strip()

def AI生成主页发帖内容(提示词: str) -> str:
    """
    使用 AI 根据提示词生成主页发帖内容
    
    Args:
        提示词: 用户输入的提示词
    
    Returns:
        生成的发帖内容，失败时返回提示词本身
    """
    import requests
    
    # AI API 配置
    AI_API_URL = "https://api.siliconflow.cn/v1/chat/completions"
    AI_MODEL = "Qwen/Qwen3-8b"
    AI_TIMEOUT = 60
    
    def 获取API_KEY() -> str:
        """从配置文件获取 AI API Key"""
        try:
            配置文件 = os.path.join(scripts_dir, "脚本配置", "qwen_api_key.txt")
            if os.path.exists(配置文件):
                with open(配置文件, 'r', encoding='utf-8') as f:
                    key = f.read().strip()
                    if key:
                        return key
        except:
            pass
        return "sk-synvthmozuvymapxavwcxjyuhoxypyygdurmhnhbqntwgcst"
    
    try:
        # 直接使用用户的提示词，不添加产品类目
        prompt = f"""你是一名专业的社交媒体内容创作者。请根据以下用户提示词生成一条适合在Facebook公共主页发布的帖子。

用户提示词：{提示词}

要求：
1. 严格按照用户提示词的要求生成内容
2. 内容要吸引人、有互动性
3. 适当使用emoji增加趣味性
4. 长度控制在50-150字之间
5. 语言风格要自然、亲切
6. 可以包含号召性用语（如：欢迎留言、点赞分享等）

请将生成的帖子内容用【】包围，格式为：【这里是帖子内容】"""
        
        # 请求数据
        request_data = {
            "model": AI_MODEL,
            "messages": [
                {"role": "user", "content": prompt}
            ]
        }
        
        # 发送请求
        response = requests.post(
            AI_API_URL,
            json=request_data,
            headers={
                "Authorization": f"Bearer {获取API_KEY()}",
                "Content-Type": "application/json"
            },
            timeout=AI_TIMEOUT
        )
        
        if response.status_code == 200:
            result = response.json()
            if result.get("choices") and len(result["choices"]) > 0:
                content = result["choices"][0].get("message", {}).get("content", "")
                cleaned = 清理AI响应(content)
                if cleaned:
                    print(f"[AI主页发帖] 生成内容: {cleaned[:50]}...")
                    return cleaned
        
        print(f"[AI主页发帖] API 返回错误: {response.status_code}")
        
    except Exception as e:
        print(f"[AI主页发帖] 调用 API 出错: {e}")
        import traceback
        traceback.print_exc()
    
    # 失败时返回原始提示词
    return 提示词

# ==================== 主页发帖核心函数 ====================

def 主页发帖(driver: "WebDriver", 提示词: str, log_func: Callable = None, 
            使用AI: bool = True, debug: bool = False, 媒体文件路径: str = None, 联系方式: str = "") -> tuple:
    """
    在 Facebook 公共主页发布帖子
    
    Args:
        driver: WebDriver/浏览器实例
        提示词: AI提示词
        log_func: 日志函数
        使用AI: 是否使用AI生成内容
        debug: 是否开启调试模式
        媒体文件路径: 媒体文件的完整路径（可选，支持图片和视频）
        联系方式: 联系方式文本（可选）
    
    Returns:
        (是否发帖成功, 帖子URL)
    """
    from selenium.webdriver.common.by import By
    from selenium.webdriver.common.keys import Keys
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    
    def log(msg):
        if log_func:
            log_func(msg)
        print(msg)
    
    # 用于清理的变量
    处理后的媒体路径 = None
    
    try:
        # 如果使用AI，先生成内容
        发帖内容 = 提示词
        if 使用AI and 提示词:
            log("正在使用AI生成发帖内容...")
            ai_内容 = AI生成主页发帖内容(提示词)
            
            # 组合AI内容和联系方式
            if 联系方式:
                发帖内容 = f"{ai_内容}\n\n{联系方式}"
            else:
                发帖内容 = ai_内容
        else:
            # 不使用AI时，直接组合提示词和联系方式
            if 联系方式:
                发帖内容 = f"{提示词}\n\n{联系方式}"
            else:
                发帖内容 = 提示词
        
        if not 发帖内容:
            log("❌ 发帖内容为空")
            return False, ""
        
        log(f"📝 发帖内容: {发帖内容[:50]}...")
        
        # 检查并处理媒体文件
        if 媒体文件路径:
            if not os.path.exists(媒体文件路径):
                log(f"❌ 媒体文件不存在: {媒体文件路径}")
                return False, ""
            
            log(f"📎 原始媒体文件: {媒体文件路径}")
            
            # 修改MD5值以避免被检测为重复内容
            try:
                处理后的媒体路径 = 修改媒体文件MD5(媒体文件路径, log_func=log)
                if 处理后的媒体路径 != 媒体文件路径:
                    log(f"✅ 已修改媒体文件MD5，使用临时文件")
                else:
                    log(f"ℹ️ 使用原始媒体文件")
            except Exception as e:
                log(f"⚠️ MD5修改失败，使用原始文件: {e}")
                处理后的媒体路径 = 媒体文件路径
        
        # 使用处理后的媒体路径
        实际媒体路径 = 处理后的媒体路径 if 处理后的媒体路径 else 媒体文件路径
        
        # ========== 步骤1: 点击"分享你的新鲜事"输入框 ==========
        log("📝 步骤1: 查找并点击发帖入口...")
        
        # 改进的查找策略：直接查找可点击的元素
        try:
            点击结果 = driver.execute_script("""
                console.log('🔍 开始查找发帖入口...');
                
                // 策略1: 查找包含"分享"文本的可点击元素
                function findPostButton() {
                    // 先查找所有role=button或有tabindex的元素
                    const clickableElements = document.querySelectorAll('[role="button"], [tabindex="0"], a, button');
                    console.log(`📊 找到 ${clickableElements.length} 个可点击元素`);
                    
                    for (let el of clickableElements) {
                        const text = el.textContent || '';
                        
                        // 查找包含"分享"和"新鲜事"的元素
                        if ((text.includes('分享') && text.includes('新鲜事')) || 
                            (text.toLowerCase().includes('share') && text.toLowerCase().includes('something'))) {
                            
                            // 确保文本长度合理
                            if (text.length < 100) {
                                console.log('✓ 找到发帖入口:', el.tagName, text.substring(0, 50));
                                
                                // 直接点击
                                el.click();
                                console.log('✅ 已点击发帖入口');
                                
                                return {
                                    success: true,
                                    element: el.tagName,
                                    role: el.getAttribute('role'),
                                    text: text.substring(0, 50)
                                };
                            }
                        }
                    }
                    
                    console.log('❌ 未找到发帖入口');
                    return {success: false, message: '未找到发帖入口'};
                }
                
                return findPostButton();
            """)
            
            if 点击结果.get('success'):
                log(f"✅ 找到并点击了发帖入口:")
                log(f"   标签: {点击结果.get('element')}")
                log(f"   Role: {点击结果.get('role')}")
                log(f"   文本: {点击结果.get('text')}")
            else:
                log(f"❌ 未找到发帖入口: {点击结果.get('message')}")
                return False, ""
                
        except Exception as e:
            log(f"❌ JavaScript执行失败: {e}")
            import traceback
            traceback.print_exc()
            return False, ""
        
        log("等待弹窗出现...")
        time.sleep(random.uniform(3, 4))
        
        # ========== 步骤2: 等待弹窗并查找"更多"按钮 ==========
        log("📝 步骤2: 查找弹窗和更多按钮...")

        # 等待弹窗出现（带重试，适应网络/VPN延迟）
        dialogs = []
        try:
            尝试次数 = 5
            for i in range(尝试次数):
                try:
                    dialogs = driver.find_elements(By.CSS_SELECTOR, "[role='dialog']")
                    if dialogs:
                        if debug:
                            log(f"  弹窗已出现（第 {i+1}/{尝试次数} 次，{len(dialogs)} 个）")
                        break
                except:
                    pass
                time.sleep(2)
            if not dialogs:
                # 兜底再用一次显式等待
                WebDriverWait(driver, 8).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "[role='dialog']"))
                )
                dialogs = driver.find_elements(By.CSS_SELECTOR, "[role='dialog']")
                if debug:
                    log(f"  显式等待后检测到 {len(dialogs)} 个弹窗")
        except:
            log("⚠️ 未检测到弹窗，尝试继续...")
        
        # 查找"更多"按钮（带重试）
        更多按钮 = None
        try:
            最大更多尝试 = 8
            间隔秒_更多 = 3
            for attempt in range(1, 最大更多尝试 + 1):
                try:
                    更多按钮 = driver.find_element(By.CSS_SELECTOR, "[aria-label='更多']")
                except:
                    try:
                        更多按钮 = driver.find_element(By.CSS_SELECTOR, "[aria-label='More']")
                    except:
                        更多按钮 = None

                if 更多按钮 and 更多按钮.is_displayed():
                    log(f"✅ 找到更多按钮（第 {attempt}/{最大更多尝试} 次）")
                    break

                if attempt < 最大更多尝试:
                    time.sleep(间隔秒_更多)

        except Exception as e:
            if debug:
                log(f"⚠️ 查找更多按钮时出错: {e}")
            更多按钮 = None

        if 更多按钮:
            try:
                driver.execute_script("arguments[0].click();", 更多按钮)
                log("✅ 已点击更多按钮")
                time.sleep(random.uniform(2, 3))  # 增加等待时间，让菜单完全展开
                
                # ========== 步骤3: 点击"接收 WhatsApp 消息"（可选）==========
                # 注意：这一步不是必需的，如果找不到就跳过
                log("📝 步骤3: 查找WhatsApp选项（可选）...")
                
                # 简化逻辑：WhatsApp选项不是必需的，快速查找后继续
                try:
                    # 只尝试一次快速查找
                    whatsapp_found = False
                    dialogs = driver.find_elements(By.CSS_SELECTOR, "[role='dialog']")
                    
                    if debug:
                        log(f"  找到 {len(dialogs)} 个弹窗")
                    
                    for idx, dlg in enumerate(dialogs):
                        try:
                            # 方法1: 查找所有可能包含WhatsApp文本的元素
                            all_elements = dlg.find_elements(By.XPATH, ".//*[contains(text(), 'WhatsApp') or contains(text(), 'whatsapp')]")
                            
                            if debug:
                                log(f"  弹窗 {idx + 1} 找到 {len(all_elements)} 个包含WhatsApp的元素")
                            
                            for el_idx, el in enumerate(all_elements):
                                try:
                                    el_text = el.text.strip()
                                    if debug:
                                        log(f"    元素 {el_idx + 1}: 文本='{el_text[:50]}', 标签={el.tag_name}")
                                    
                                    # 检查文本是否包含"WhatsApp"和"消息"（放宽条件）
                                    if "WhatsApp" in el_text and "消息" in el_text:
                                        if debug:
                                            log(f"    ✓ 找到匹配的元素")
                                        
                                        # 向上查找可点击的父元素（增加到10层）
                                        clickable = el
                                        found_clickable = False
                                        for level in range(10):
                                            role = clickable.get_attribute("role")
                                            tag = clickable.tag_name
                                            
                                            if debug:
                                                log(f"      层级 {level}: 标签={tag}, role={role}")
                                            
                                            if role in ["menuitem", "button"] or tag in ["button", "a"]:
                                                driver.execute_script("arguments[0].click();", clickable)
                                                log("✅ 已点击WhatsApp选项")
                                                whatsapp_found = True
                                                found_clickable = True
                                                time.sleep(2)
                                                break
                                            try:
                                                clickable = clickable.find_element(By.XPATH, "..")
                                            except:
                                                break
                                        
                                        # 如果向上10层都没找到可点击元素，直接点击原始元素
                                        if not found_clickable:
                                            if debug:
                                                log(f"      未找到可点击父元素，直接点击原始元素")
                                            try:
                                                driver.execute_script("arguments[0].click();", el)
                                                log("✅ 已点击WhatsApp选项")
                                                whatsapp_found = True
                                                time.sleep(2)
                                            except Exception as click_error:
                                                if debug:
                                                    log(f"      点击失败: {click_error}")
                                        
                                        if whatsapp_found:
                                            break
                                except Exception as el_error:
                                    if debug:
                                        log(f"    处理元素失败: {el_error}")
                                    continue
                            
                            # 方法2: 如果方法1没找到，尝试查找所有menuitem
                            if not whatsapp_found:
                                menuitems = dlg.find_elements(By.CSS_SELECTOR, "[role='menuitem']")
                                if debug:
                                    log(f"  弹窗 {idx + 1} 找到 {len(menuitems)} 个menuitem")
                                
                                for mi_idx, item in enumerate(menuitems):
                                    try:
                                        item_text = item.text.strip()
                                        if debug:
                                            log(f"    menuitem {mi_idx + 1}: '{item_text[:50]}'")
                                        
                                        if "WhatsApp" in item_text:
                                            driver.execute_script("arguments[0].click();", item)
                                            log("✅ 已点击WhatsApp选项")
                                            whatsapp_found = True
                                            time.sleep(2)
                                            break
                                    except:
                                        continue
                        except Exception as dlg_error:
                            if debug:
                                log(f"  处理弹窗 {idx + 1} 失败: {dlg_error}")
                            pass
                        
                        if whatsapp_found:
                            break
                    
                    if not whatsapp_found:
                        log("⚠️ 未找到WhatsApp选项，跳过此步骤")
                except Exception as e:
                    log(f"⚠️ WhatsApp选项查找失败: {e}，跳过此步骤")
                    if debug:
                        import traceback
                        traceback.print_exc()
                    
            except:
                log("⚠️ 点击更多按钮失败")
        else:
            log("⚠️ 未找到更多按钮，直接查找编辑器...")
        
        # ========== 步骤3.5: 上传媒体文件（如果有）==========
        if 媒体文件路径:
            log("📝 步骤3.5: 上传媒体文件...")
            
            try:
                # 查找文件输入元素
                file_inputs = driver.find_elements(By.CSS_SELECTOR, "input[type='file']")
                log(f"  找到 {len(file_inputs)} 个文件输入元素")
                
                # 优先选择在弹窗中的文件输入
                file_input = None
                for inp in file_inputs:
                    try:
                        # 检查是否在弹窗中
                        parent_dialog = inp.find_element(By.XPATH, "ancestor::*[@role='dialog']")
                        if parent_dialog:
                            file_input = inp
                            log("  ✓ 找到弹窗中的文件输入元素")
                            break
                    except:
                        continue
                
                # 如果没找到弹窗中的，使用最后一个
                if not file_input and file_inputs:
                    file_input = file_inputs[-1]
                    log("  ✓ 使用最后一个文件输入元素")
                
                if file_input:
                    try:
                        # 发送文件路径（使用处理后的媒体文件）
                        log(f"  正在上传文件: {实际媒体路径}")
                        file_input.send_keys(实际媒体路径)
                        log("  ✅ 文件已发送到input元素")
                    except Exception as send_error:
                        log(f"  ❌ 发送文件路径失败: {send_error}")
                        log("  ⚠️ 将尝试纯文本发帖")
                        # 继续执行，不要中断
                    
                    # 等待上传完成 - 查找"上传完成"和"100%"标记
                    log("  ⏳ 等待文件上传...")
                    time.sleep(3)  # 等待3秒让文件开始上传
                    
                    # 检查上传是否完成
                    try:
                        upload_complete = False
                        max_wait = 60  # 最多等待60秒
                        
                        for i in range(max_wait):
                            # 方法1: 查找 aria-label="上传完成" 的元素
                            try:
                                complete_icons = driver.find_elements(By.CSS_SELECTOR, "[aria-label='上传完成'], [aria-label='Upload complete']")
                                if complete_icons:
                                    log("  ✅ 检测到「上传完成」标记")
                                    upload_complete = True
                                    break
                            except:
                                pass
                            
                            # 方法2: 查找包含"100%"文本的元素
                            try:
                                percent_elements = driver.find_elements(By.XPATH, "//*[contains(text(), '100%')]")
                                if percent_elements:
                                    log("  ✅ 检测到「100%」标记")
                                    upload_complete = True
                                    break
                            except:
                                pass
                            
                            # 方法3: 检查是否还有上传进度条（如果没有了，说明上传完成或失败）
                            try:
                                progress_bars = driver.find_elements(By.CSS_SELECTOR, "[role='progressbar']")
                                if not progress_bars and i > 5:  # 至少等待5秒后才认为没有进度条是正常的
                                    log("  ✅ 未检测到进度条，上传可能已完成")
                                    upload_complete = True
                                    break
                            except:
                                pass
                            
                            # 每秒检查一次
                            time.sleep(1)
                            
                            # 每10秒输出一次进度
                            if (i + 1) % 10 == 0:
                                log(f"  ⏳ 已等待 {i + 1} 秒...")
                        
                        if not upload_complete:
                            log("  ⚠️ 上传超时（60秒），但继续发帖流程")
                        else:
                            log("  ✅ 上传完成，继续发帖")
                            
                    except Exception as progress_error:
                        log(f"  ⚠️ 检查上传进度失败: {progress_error}")
                        log("  ✅ 继续发帖流程")
                    
                    time.sleep(2)
                else:
                    log("  ❌ 未找到文件输入元素")
                    log("  ⚠️ 将尝试纯文本发帖")
                    
            except Exception as e:
                log(f"  ❌ 上传媒体文件失败: {e}")
                log("  ⚠️ 将尝试纯文本发帖")
                if debug:
                    import traceback
                    traceback.print_exc()
        
        # ========== 步骤4: 查找编辑器并输入文本 ==========
        log("📝 步骤4: 查找编辑器...")
        
        编辑器 = None

        try:
            最大编辑器尝试 = 10
            间隔秒_编辑器 = 3

            for attempt in range(1, 最大编辑器尝试 + 1):
                # 在弹窗中查找
                try:
                    dialogs = driver.find_elements(By.CSS_SELECTOR, "[role='dialog']")
                    for dlg in dialogs:
                        try:
                            editables = dlg.find_elements(By.CSS_SELECTOR, "[contenteditable='true']")
                            for el in editables:
                                if el.is_displayed():
                                    编辑器 = el
                                    break
                        except:
                            continue
                        if 编辑器:
                            break
                except:
                    pass

                # 全局查找
                if not 编辑器:
                    try:
                        editables = driver.find_elements(By.CSS_SELECTOR, "[contenteditable='true']")
                        for el in editables:
                            if el.is_displayed():
                                role = el.get_attribute("role")
                                try:
                                    in_dialog = el.find_element(By.XPATH, "ancestor::*[@role='dialog']")
                                except:
                                    in_dialog = None
                                if role == "textbox" or in_dialog is not None:
                                    编辑器 = el
                                    break
                    except:
                        pass

                if 编辑器:
                    log(f"✅ 找到编辑器（第 {attempt}/{最大编辑器尝试} 次）")
                    break

                if attempt < 最大编辑器尝试:
                    time.sleep(间隔秒_编辑器)

        except Exception as e:
            if debug:
                log(f"⚠️ 查找编辑器时出错: {e}")
            编辑器 = None

        if not 编辑器:
            log("❌ 未找到编辑器")
            return False, ""
        
        log("✅ 找到编辑器")
        
        # 点击并聚焦编辑器
        try:
            driver.execute_script("arguments[0].click();", 编辑器)
            driver.execute_script("arguments[0].focus();", 编辑器)
        except:
            编辑器.click()
        
        time.sleep(0.5)
        
        # 清空并输入内容 - 使用JavaScript避免emoji问题
        try:
            编辑器.clear()
        except:
            pass
        
        time.sleep(0.3)
        
        # 使用JavaScript直接设置内容，避免ChromeDriver的BMP限制
        try:
            # 转义特殊字符
            escaped_content = 发帖内容.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n').replace('\r', '\\r')
            
            # 使用JavaScript设置内容
            driver.execute_script(f'''
                var editor = arguments[0];
                editor.focus();
                
                // 清空内容
                editor.innerHTML = '';
                
                // 设置文本内容
                var text = "{escaped_content}";
                editor.textContent = text;
                
                // 触发输入事件
                editor.dispatchEvent(new InputEvent('input', {{bubbles: true, data: text}}));
                editor.dispatchEvent(new Event('change', {{bubbles: true}}));
            ''', 编辑器)
            
            log(f"✅ 已输入文本")
        except Exception as e:
            log(f"❌ JavaScript输入失败，尝试send_keys: {e}")
            # 如果JavaScript失败，尝试send_keys（但可能会因为emoji失败）
            try:
                for char in 发帖内容:
                    编辑器.send_keys(char)
                    time.sleep(random.uniform(0.02, 0.08))
                log(f"✅ 已输入文本")
            except Exception as e2:
                log(f"❌ send_keys也失败: {e2}")
                return False, ""
        
        time.sleep(random.uniform(1.5, 2.5))
        
        # ========== 步骤4.5: 点击"继续"按钮（两次）==========
        log("📝 步骤4.5: 查找并点击继续按钮...")

        try:
            最大继续尝试 = 8
            间隔秒_继续 = 3

            # 第一次点击"继续"，带重试
            继续按钮 = None
            for attempt in range(1, 最大继续尝试 + 1):
                dialogs = driver.find_elements(By.CSS_SELECTOR, "[role='dialog']")
                for dlg in dialogs:
                    try:
                        btns = dlg.find_elements(By.CSS_SELECTOR, "[role='button']")
                        for btn in btns:
                            txt = (btn.text or "").strip()
                            if txt in ["继续", "Continue", "下一步", "Next"] and btn.is_displayed():
                                继续按钮 = btn
                                break
                    except:
                        continue
                    if 继续按钮:
                        break
                if 继续按钮:
                    log(f"✅ 找到第一个继续按钮（第 {attempt}/{最大继续尝试} 次）")
                    break
                if attempt < 最大继续尝试:
                    time.sleep(间隔秒_继续)

            if 继续按钮:
                try:
                    driver.execute_script("arguments[0].click();", 继续按钮)
                except Exception:
                    try:
                        继续按钮.click()
                    except Exception:
                        pass
                log("✅ 已点击第一个继续按钮")
                time.sleep(random.uniform(3, 4))

                # 第二次点击"继续"，同样带重试
                继续按钮2 = None
                for attempt in range(1, 最大继续尝试 + 1):
                    dialogs = driver.find_elements(By.CSS_SELECTOR, "[role='dialog']")
                    for dlg in dialogs:
                        try:
                            btns = dlg.find_elements(By.CSS_SELECTOR, "[role='button']")
                            for btn in btns:
                                txt = (btn.text or "").strip()
                                if txt in ["继续", "Continue", "下一步", "Next"] and btn.is_displayed():
                                    继续按钮2 = btn
                                    break
                        except:
                            continue
                        if 继续按钮2:
                            break
                    if 继续按钮2:
                        log(f"✅ 找到第二个继续按钮（第 {attempt}/{最大继续尝试} 次）")
                        break
                    if attempt < 最大继续尝试:
                        time.sleep(间隔秒_继续)

                if 继续按钮2:
                    try:
                        driver.execute_script("arguments[0].click();", 继续按钮2)
                    except Exception:
                        try:
                            继续按钮2.click()
                        except Exception:
                            pass
                    log("✅ 已点击第二个继续按钮")
                    time.sleep(random.uniform(3, 4))
                else:
                    log("⚠️ 未找到第二个继续按钮，继续查找发布按钮")
            else:
                log("⚠️ 未找到继续按钮，直接查找发布按钮")

        except Exception as e:
            log(f"⚠️ 查找继续按钮失败: {e}")
        
        # ========== 步骤5: 点击发布按钮 ==========
        log("📝 步骤5: 查找发布按钮...")
        
        发布按钮 = None

        # 为发布按钮增加重试机制
        最大发布尝试 = 10
        间隔秒_发布 = 3

        for attempt in range(1, 最大发布尝试 + 1):
            # 方法1: 在弹窗中通过 aria-label 查找
            try:
                dialogs = driver.find_elements(By.CSS_SELECTOR, "[role='dialog']")
                if debug:
                    log(f"  第 {attempt}/{最大发布尝试} 次查找发布按钮，找到 {len(dialogs)} 个弹窗")

                for idx, dlg in enumerate(dialogs):
                    if debug:
                        log(f"  检查弹窗 {idx + 1}")

                    # 通过aria-label查找
                    try:
                        发布按钮 = dlg.find_element(By.CSS_SELECTOR, "[aria-label='发布']")
                        if debug:
                            log(f"  在弹窗 {idx + 1} 找到发布按钮（aria-label='发布'）")
                        break
                    except:
                        pass

                    try:
                        发布按钮 = dlg.find_element(By.CSS_SELECTOR, "[aria-label='Post']")
                        if debug:
                            log(f"  在弹窗 {idx + 1} 找到发布按钮（aria-label='Post'）")
                        break
                    except:
                        pass

                    # 通过文本查找所有按钮
                    try:
                        btns = dlg.find_elements(By.CSS_SELECTOR, "[role='button']")
                        if debug:
                            log(f"  弹窗 {idx + 1} 有 {len(btns)} 个按钮")

                        for btn in btns:
                            try:
                                txt = (btn.text or "").strip()
                                if debug and txt:
                                    log(f"    按钮文本: '{txt}'")

                                if txt in ["发布", "Post", "发帖", "Share"] and btn.is_displayed():
                                    发布按钮 = btn
                                    if debug:
                                        log(f"  找到发布按钮（文本='{txt}'）")
                                    break
                            except:
                                continue
                    except:
                        pass

                    if 发布按钮:
                        break
            except Exception as e:
                if debug:
                    log(f"  方法1失败: {e}")

            # 方法2: 全局查找（通过 aria-label）
            if not 发布按钮:
                if debug:
                    log("  尝试全局查找发布按钮...")

                try:
                    发布按钮 = driver.find_element(By.CSS_SELECTOR, "[aria-label='发布']")
                    if debug:
                        log("  全局找到发布按钮（aria-label='发布']")
                except:
                    try:
                        发布按钮 = driver.find_element(By.CSS_SELECTOR, "[aria-label='Post']")
                        if debug:
                            log("  全局找到发布按钮（aria-label='Post']")
                    except:
                        pass

            # 方法3: 全局查找所有按钮，通过文本匹配
            if not 发布按钮:
                if debug:
                    log("  尝试全局文本匹配发布按钮...")

                try:
                    all_btns = driver.find_elements(By.CSS_SELECTOR, "[role='button']")
                    if debug:
                        log(f"  全局找到 {len(all_btns)} 个按钮")

                    for btn in all_btns:
                        try:
                            txt = (btn.text or "").strip()
                            if txt in ["发布", "Post", "发帖", "Share"] and btn.is_displayed():
                                发布按钮 = btn
                                if debug:
                                    log(f"  全局找到发布按钮（文本='{txt}'）")
                                break
                        except:
                            continue
                except Exception as e:
                    if debug:
                        log(f"  方法3失败: {e}")

            if 发布按钮:
                log(f"✅ 找到发布按钮（第 {attempt}/{最大发布尝试} 次）")
                break

            if attempt < 最大发布尝试:
                time.sleep(间隔秒_发布)

        if not 发布按钮:
            log("❌ 未找到发布按钮")
            if debug:
                # 输出所有可见按钮的信息帮助调试
                try:
                    all_btns = driver.find_elements(By.CSS_SELECTOR, "[role='button']")
                    log(f"  调试：共有 {len(all_btns)} 个按钮")
                    visible_count = 0
                    for btn in all_btns[:20]:  # 只显示前20个
                        try:
                            if btn.is_displayed():
                                txt = (btn.text or "").strip()
                                aria = btn.get_attribute("aria-label") or ""
                                log(f"    可见按钮: text='{txt}', aria-label='{aria}'")
                                visible_count += 1
                        except:
                            pass
                    log(f"  共 {visible_count} 个可见按钮")
                except:
                    pass
            return False, ""
        
        log("✅ 找到发布按钮")
        
        # 检查按钮状态
        try:
            is_disabled = 发布按钮.get_attribute("aria-disabled") == "true"
            if is_disabled:
                log("⚠️ 发布按钮暂时禁用，等待...")
                time.sleep(3)
        except:
            pass
        
        # 点击发布
        try:
            driver.execute_script("arguments[0].click();", 发布按钮)
        except:
            try:
                发布按钮.click()
            except Exception as e:
                log(f"❌ 点击发布按钮失败: {e}")
                return False
        
        log("✅ 已点击发布按钮")
        # 点击发布后，先等待一段固定时间，让 Facebook 完成“正在发布/发送中”的处理
        log("⏳ 已点击发布按钮，等待 10 秒再开始检查帖子...")
        time.sleep(10)

        log("🎉 发帖流程完成，开始尝试获取帖子URL...")
        
        # ========== 尝试在当前页面中定位刚刚发布的帖子 ========== 
        帖子URL = None
        try:
            # 取一段内容片段用于匹配，避免整段太长
            原始片段 = ""
            if 发帖内容:
                原始片段 = 发帖内容.strip().split("\n")[0][:60]
            if not 原始片段 and 联系方式:
                原始片段 = 联系方式.strip()[:60]

            # 构造多个候选匹配片段，依次尝试，任一成功即可
            匹配片段列表 = []

            if 原始片段:
                try:
                    # 1) 保留标点和空格的短前缀（尽量贴近 DOM 实际展示）
                    前缀_含标点 = 原始片段[:30]
                    if 前缀_含标点:
                        匹配片段列表.append(前缀_含标点)

                    # 2) 去掉常见 emoji 后的短前缀
                    cleaned = re.sub(r"[\u2600-\u27FF]", "", 原始片段)
                    cleaned = re.sub(r"\s+", " ", cleaned).strip()
                    if cleaned:
                        匹配片段列表.append(cleaned[:30])

                    # 3) 只保留中文字符的短前缀（防止标点过多打断）
                    chinese_parts = re.findall(r"[\u4e00-\u9fff]+", cleaned or 原始片段)
                    if chinese_parts:
                        pure_chinese = "".join(chinese_parts)
                        if pure_chinese:
                            匹配片段列表.append(pure_chinese[:30])

                    # 去重，保持顺序
                    去重后的 = []
                    for frag in 匹配片段列表:
                        frag = frag.strip()
                        if frag and frag not in 去重后的:
                            去重后的.append(frag)
                    匹配片段列表 = 去重后的

                except Exception:
                    # 退化到只用原始片段
                    匹配片段列表 = [原始片段[:30]]

            if 匹配片段列表:
                from selenium.webdriver.common.by import By
                from selenium.common.exceptions import NoSuchElementException

                def _根据内容片段查找帖子链接(说明: str) -> str:
                    """在当前页面中根据内容片段尝试多次查找帖子链接，找到则返回URL，否则返回空串。"""
                    非local_帖子URL = ""
                    最大尝试次数 = 10  # 每次约 5-6 秒，总时长接近 1 分钟
                    间隔秒 = 6
                    # 控制异常日志输出次数，避免 StaleElementReference 等错误刷屏
                    错误日志计数 = 0
                    最大错误日志 = 5

                    # 内部标准化函数：去掉 emoji、标点和多余空白，只保留中英文和数字，便于模糊匹配
                    def _标准化文本(s: str) -> str:
                        if not s:
                            return ""
                        try:
                            # 去掉常见 emoji
                            s2 = re.sub(r"[\u2600-\u27FF]", "", s)
                            # 去掉所有空白
                            s2 = re.sub(r"\s+", "", s2)
                            # 只保留中英文和数字
                            parts = re.findall(r"[\u4e00-\u9fffA-Za-z0-9]+", s2)
                            return "".join(parts)
                        except Exception:
                            return s.replace(" ", "")

                    # 预先为所有片段计算标准化形式
                    标准化片段列表 = []  # (原始片段, 标准化片段)
                    for frag in 匹配片段列表:
                        norm_frag = _标准化文本(frag)
                        if norm_frag:
                            标准化片段列表.append((frag, norm_frag))
                    if not 标准化片段列表:
                        标准化片段列表 = [(frag, _标准化文本(frag)) for frag in 匹配片段列表]
                    for attempt in range(1, 最大尝试次数 + 1):
                        try:
                            articles = driver.find_elements(By.XPATH, "//*[@role='article']")
                        except Exception as locate_round_error:
                            if debug:
                                log(f"  {说明}，本轮获取帖子容器时出错: {locate_round_error}")
                            articles = []

                        # 依次尝试每个候选片段
                        for 原片段, 标准化片段 in 标准化片段列表:
                            log(f"🔍 {说明}，尝试根据内容片段定位帖子，第 {attempt}/{最大尝试次数} 次，片段: '{原片段}'")

                            for art in articles:
                                try:
                                    if not art.is_displayed():
                                        continue

                                    # 聚合帖子容器中的主要文本，并进行标准化后再匹配
                                    text_nodes = art.find_elements(By.XPATH, ".//*[@dir='auto' and not(@role='button')]")
                                    combined_text = " ".join(
                                        (t.text or "").strip() for t in text_nodes if (t.text or "").strip()
                                    )
                                    if not combined_text:
                                        continue

                                    norm_text = _标准化文本(combined_text)
                                    if 标准化片段 and 标准化片段 not in norm_text:
                                        continue

                                    # 在帖子容器中寻找 facebook 链接，按优先级选帖子的详情链接
                                    links = art.find_elements(By.XPATH, ".//a[contains(@href, 'facebook.com')]")
                                    candidate_href = ""
                                    for a in links:
                                        href = a.get_attribute("href") or ""
                                        if not href:
                                            continue

                                        # 这里只把真正指向帖子详情页的链接作为候选：reel / watch?v / posts / story.php
                                        if "reel/" in href:
                                            candidate_href = href
                                            break
                                        if "watch" in href and "?v=" in href:
                                            if not candidate_href:
                                                candidate_href = href
                                            continue
                                        if "posts/" in href or "story.php" in href:
                                            if not candidate_href:
                                                candidate_href = href
                                            continue

                                    if candidate_href:
                                        非local_帖子URL = candidate_href
                                        log(f"✅ {说明}，使用片段 '{原片段}' 已在当前页面定位到帖子链接")
                                        break

                                except Exception as locate_error:
                                    # 针对动态刷新的 DOM，可能出现 stale element，直接略过当前帖子容器即可
                                    if debug and 错误日志计数 < 最大错误日志:
                                        # 只在前几次打印错误类型，避免 Selenium 内置的长堆栈刷屏
                                        log(f"  片段 '{原片段}' 在帖子容器中匹配时出错: {type(locate_error).__name__}")
                                        错误日志计数 += 1
                                    continue

                            if 非local_帖子URL:
                                break

                        if 非local_帖子URL:
                            break

                        # 本轮未找到，则等待一段时间再重试，给 Facebook 更多时间刷新（尤其是视频）
                        if attempt < 最大尝试次数:
                            time.sleep(间隔秒)

                    # 所有尝试结束仍未找到时，如果处于调试模式，输出当前页面可见帖子摘要，便于分析
                    if not 非local_帖子URL and debug:
                        try:
                            log(f"⚠️ {说明}，所有片段多次尝试仍未找到匹配帖子，开始调试输出当前页面帖子列表...")
                            # 尝试枚举前若干个帖子容器
                            articles = driver.find_elements(By.XPATH, "//*[@role='article']")
                            log(f"  调试：当前页面检测到 {len(articles)} 个 role='article' 容器")
                            for idx, art in enumerate(articles[:5]):  # 只打印前5条，避免过多日志
                                try:
                                    # 提取帖子的主要文本内容前缀
                                    text_nodes = art.find_elements(By.XPATH, ".//*[@dir='auto' and not(@role='button')]")
                                    combined_text = " ".join(
                                        (t.text or "").strip() for t in text_nodes if (t.text or "").strip()
                                    )
                                    combined_text = combined_text[:120]

                                    # 提取帖子里的 facebook 链接
                                    links = art.find_elements(By.XPATH, ".//a[contains(@href, 'facebook.com')]")
                                    hrefs = []
                                    for a in links:
                                        href = a.get_attribute("href") or ""
                                        if href and href not in hrefs:
                                            hrefs.append(href)

                                    log(f"  帖子 {idx + 1} 文本前缀: '{combined_text}'")
                                    for h_idx, h in enumerate(hrefs[:5]):
                                        log(f"    链接 {h_idx + 1}: {h}")
                                except Exception as art_err:
                                    log(f"  调试：解析帖子 {idx + 1} 时出错: {art_err}")
                        except Exception as debug_err:
                            log(f"  调试：输出帖子列表时出错: {debug_err}")

                    return 非local_帖子URL

                # 第一阶段：在当前页面（通常是首页）查找
                帖子URL = _根据内容片段查找帖子链接("在当前页面")

                # 如果当前页面未找到，尝试刷新当前页面后再查一轮
                if not 帖子URL:
                    try:
                        log("⚠️ 当前页面未找到帖子，刷新页面后再试一次...")
                        try:
                            log("🔄 刷新页面以加载最新帖子...")
                            driver.refresh()
                        except Exception as refresh_err:
                            if debug:
                                log(f"⚠️ 刷新页面时出错: {refresh_err}")

                        # 刷新后给予页面一定加载时间
                        time.sleep(5)

                        # 在刷新后的当前页面再次按内容片段轮询查找
                        帖子URL = _根据内容片段查找帖子链接("在刷新后的当前页面")
                    except Exception as refresh_round_err:
                        if debug:
                            log(f"⚠️ 刷新后再次查找帖子时出错: {refresh_round_err}")

                # 如果刷新后的当前页面依然未找到，尝试进入个人主页/主页时间线再查找一轮
                if not 帖子URL:
                    try:
                        log("⚠️ 当前页面及刷新后页面均未找到帖子，尝试进入个人主页再查找...")

                        # 优先点击 "你的个人主页" 按钮（中文界面）
                        profile_btn = None
                        try:
                            profile_btn = driver.find_element(By.CSS_SELECTOR, "[aria-label='你的个人主页']")
                        except Exception:
                            # 尝试英文界面
                            try:
                                profile_btn = driver.find_element(By.CSS_SELECTOR, "[aria-label='Your profile']")
                            except Exception:
                                profile_btn = None

                        if profile_btn and profile_btn.is_displayed():
                            try:
                                driver.execute_script("arguments[0].click();", profile_btn)
                            except Exception:
                                try:
                                    profile_btn.click()
                                except Exception:
                                    pass
                            log("✅ 已点击个人主页入口，等待页面加载...")
                            time.sleep(8)

                            # 在个人主页/主页时间线页面再次按内容片段轮询查找
                            帖子URL = _根据内容片段查找帖子链接("在个人主页页面")
                        else:
                            log("⚠️ 未找到个人主页入口按钮，跳过个人主页查找")

                    except Exception as profile_err:
                        if debug:
                            log(f"⚠️ 进入个人主页并查找帖子时出错: {profile_err}")

            # 如果根据内容未找到，则尝试用当前URL 作为兜底，但仅当它看起来确实是某条帖子的详情页
            if not 帖子URL:
                try:
                    current_url = driver.current_url
                    if current_url:
                        # 必须包含典型的帖子URL特征之一，且不能是纯首页或纯个人主页
                        if any(k in current_url for k in ("reel/", "watch", "posts/", "story.php")):
                            if not current_url.startswith("https://www.facebook.com/profile.php") and current_url not in ("https://www.facebook.com/", "https://www.facebook.com"):
                                帖子URL = current_url
                except Exception as cur_err:
                    if debug:
                        log(f"  获取当前URL失败: {cur_err}")
        except Exception as url_err:
            if debug:
                log(f"⚠️ 获取帖子URL时出错: {url_err}")
        
        # 尝试解析帖子ID（如果URL可用），并在可能的情况下返回一个不带追踪参数的干净URL
        if 帖子URL:
            try:
                parsed = urlparse(帖子URL)
                post_id = ""
                # story.php?story_fbid=xxx&id=yyy 形式
                if "story.php" in parsed.path:
                    qs = parse_qs(parsed.query)
                    post_id = (qs.get("story_fbid") or [""])[0]
                elif "reel" in parsed.path:
                    # /reel/{id}/ 形式
                    parts = [p for p in parsed.path.split("/") if p]
                    if "reel" in parts:
                        idx = parts.index("reel")
                        if idx + 1 < len(parts):
                            post_id = parts[idx + 1]
                elif "watch" in parsed.path:
                    # /watch?v={id} 形式
                    qs = parse_qs(parsed.query)
                    post_id = (qs.get("v") or [""])[0]
                else:
                    # /.../posts/{post_id}/ 形式
                    parts = [p for p in parsed.path.split("/") if p]
                    if "posts" in parts:
                        idx = parts.index("posts")
                        if idx + 1 < len(parts):
                            post_id = parts[idx + 1]

                # 如果成功拿到 post_id，则尽量构造一个干净的帖子详情URL
                if post_id:
                    base = f"{parsed.scheme}://{parsed.netloc}"
                    clean_url = 帖子URL
                    try:
                        if "reel" in parsed.path:
                            clean_url = f"{base}/reel/{post_id}/"
                        elif "watch" in parsed.path:
                            clean_url = f"{base}/watch/?v={post_id}"
                        elif "story.php" in parsed.path:
                            clean_url = f"{base}/story.php?story_fbid={post_id}"
                        elif "posts" in parsed.path:
                            # /.../posts/{post_id}/，尽量保留前缀路径
                            parts = [p for p in parsed.path.split("/") if p]
                            if "posts" in parts:
                                idx = parts.index("posts")
                                prefix = "/".join(parts[:idx + 1])
                                clean_url = f"{base}/{prefix}/{post_id}/"
                    except Exception:
                        # 如果构造干净URL失败，则退回到原始URL
                        clean_url = 帖子URL

                    帖子URL = clean_url
                    log(f"📎 帖子URL: {帖子URL}")
                    log(f"🆔 帖子ID: {post_id}")
                else:
                    log(f"📎 帖子URL: {帖子URL} (未能解析出ID)")
            except Exception as parse_err:
                if debug:
                    log(f"⚠️ 解析帖子ID失败: {parse_err}")
                log(f"📎 帖子URL: {帖子URL}")
        else:
            log("⚠️ 未能获取帖子URL")
        
        return (True, 帖子URL)
    
    finally:
        # 无论成功或失败，都清理临时媒体文件
        try:
            if 处理后的媒体路径 and 处理后的媒体路径 != 媒体文件路径:
                清理临时媒体文件(处理后的媒体路径)
        except Exception as cleanup_error:
            if debug:
                print(f"[清理] 清理临时文件时出错: {cleanup_error}")

# ==================== 调试入口 ====================

if __name__ == "__main__":
    if not DEBUG_BROWSER_ID:
        print("请设置 DEBUG_BROWSER_ID 后再运行调试")
        print("在文件顶部找到 DEBUG_BROWSER_ID 变量，填入你的浏览器ID")
        sys.exit(1)
    
    print(f"调试模式 - 浏览器ID: {DEBUG_BROWSER_ID}")
    
    # 连接到浏览器
    try:
        from bitbrowser_api import BitBrowserAPI
        
        api = BitBrowserAPI()
        result = api.open_browser(DEBUG_BROWSER_ID)
        
        if not result.get("success"):
            print(f"打开浏览器失败: {result}")
            sys.exit(1)
        
        driver_path = result.get("driver")
        debug_port = result.get("http")
        
        from selenium import webdriver
        from selenium.webdriver.chrome.service import Service
        from selenium.webdriver.chrome.options import Options
        
        options = Options()
        options.add_experimental_option("debuggerAddress", debug_port)
        
        service = Service(driver_path)
        driver = webdriver.Chrome(service=service, options=options)
        
        print("已连接到浏览器")
        print("请确保浏览器已打开Facebook公共主页")
        
        # 测试发帖
        测试内容 = "今天天气真好，分享一下我的心情！"
        
        input("按回车开始测试发帖...")
        
        结果 = 主页发帖(driver, 测试内容, debug=True)
        
        if 结果:
            print("\n✅ 发帖成功！")
        else:
            print("\n❌ 发帖失败")
        
    except Exception as e:
        print(f"调试出错: {e}")
        import traceback
        traceback.print_exc()
