"""
比特浏览器 API 封装模块
官方文档: https://doc2.bitbrowser.cn/jiekou/liu-lan-qi-jie-kou.html
"""

import requests
import json
from typing import Optional, Dict, Any, List


class BitBrowserAPI:
    """比特浏览器 API 客户端"""
    
    def __init__(self, base_url: str = "http://127.0.0.1:54345"):
        self.base_url = base_url
        self.headers = {'Content-Type': 'application/json'}
    
    def _request(self, endpoint: str, data: Dict[str, Any] = None) -> Dict[str, Any]:
        """发送请求到比特浏览器 API"""
        try:
            url = f"{self.base_url}{endpoint}"
            if data:
                response = requests.post(url, data=json.dumps(data), headers=self.headers, timeout=30)
            else:
                response = requests.post(url, headers=self.headers, timeout=30)
            return response.json()
        except requests.exceptions.ConnectionError:
            return {"success": False, "msg": "无法连接到比特浏览器，请确保比特浏览器已启动"}
        except requests.exceptions.Timeout:
            return {"success": False, "msg": "请求超时"}
        except Exception as e:
            return {"success": False, "msg": f"请求失败: {str(e)}"}
    
    def get_browser_list(self, page: int = 0, page_size: int = 100) -> Dict[str, Any]:
        """
        获取浏览器窗口列表
        :param page: 页码，从0开始
        :param page_size: 每页数量
        :return: 浏览器列表
        """
        data = {
            "page": page,
            "pageSize": page_size
        }
        return self._request("/browser/list", data)
    
    def open_browser(self, browser_id: str, load_extensions: bool = True, 
                     args: List[str] = None) -> Dict[str, Any]:
        """
        打开浏览器窗口
        :param browser_id: 浏览器ID
        :param load_extensions: 是否加载扩展
        :param args: 启动参数
        :return: 包含 ws 连接地址等信息
        """
        data = {
            "id": browser_id,
            "loadExtensions": load_extensions
        }
        if args:
            data["args"] = args
        return self._request("/browser/open", data)
    
    def close_browser(self, browser_id: str) -> Dict[str, Any]:
        """
        关闭浏览器窗口
        :param browser_id: 浏览器ID
        :return: 操作结果
        """
        data = {"id": browser_id}
        return self._request("/browser/close", data)
    
    def create_browser(self, name: str, remark: str = "", 
                       proxy_type: str = "noproxy", 
                       core_version: str = "124",
                       **kwargs) -> Dict[str, Any]:
        """
        创建浏览器窗口
        :param name: 窗口名称
        :param remark: 备注
        :param proxy_type: 代理类型 ['noproxy', 'http', 'https', 'socks5', 'ssh']
        :param core_version: 内核版本
        :return: 包含新建浏览器ID
        """
        data = {
            "name": name,
            "remark": remark,
            "proxyMethod": 2,  # 自定义代理
            "proxyType": proxy_type,
            "browserFingerPrint": {
                "coreVersion": core_version
            }
        }
        data.update(kwargs)
        return self._request("/browser/update", data)
    
    def delete_browser(self, browser_id: str) -> Dict[str, Any]:
        """
        删除浏览器窗口
        :param browser_id: 浏览器ID
        :return: 操作结果
        """
        data = {"id": browser_id}
        return self._request("/browser/delete", data)
    
    def get_browser_detail(self, browser_id: str) -> Dict[str, Any]:
        """
        获取浏览器详情
        :param browser_id: 浏览器ID
        :return: 浏览器详细信息
        """
        data = {"id": browser_id}
        return self._request("/browser/detail", data)
    
    def check_connection(self) -> bool:
        """
        检查与比特浏览器的连接状态
        :return: 是否连接成功
        """
        try:
            result = self.get_browser_list(page=0, page_size=1)
            return result.get("success", False)
        except:
            return False
    
    def get_browser_pids(self, browser_ids: List[str]) -> Dict[str, Any]:
        """
        获取指定浏览器的进程PID
        :param browser_ids: 浏览器ID列表
        :return: {浏览器ID: PID} 的字典
        """
        data = {"ids": browser_ids}
        return self._request("/browser/pids", data)
    
    def get_all_browser_pids(self) -> Dict[str, Any]:
        """
        获取所有已打开浏览器的进程PID
        :return: {浏览器ID: PID} 的字典
        """
        return self._request("/browser/pids/all")
    
    def get_alive_browser_pids(self, browser_ids: List[str]) -> Dict[str, Any]:
        """
        获取活着的浏览器进程PID（会检查进程是否真的存在）
        :param browser_ids: 浏览器ID列表
        :return: {浏览器ID: PID} 的字典
        """
        data = {"ids": browser_ids}
        return self._request("/browser/pids/alive", data)


# 全局实例
bit_browser = BitBrowserAPI()
