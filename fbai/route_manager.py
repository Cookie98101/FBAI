"""
路由管理模块
用于统一管理所有路由配置和端点信息
"""

class RouteManager:
    """路由管理器"""
    
    def __init__(self):
        """初始化路由管理器"""
        # 路由配置
        self.routes = {
            # 核心数据路由
            'get_current_data': {
                'endpoint': '/get_current_data',
                'method': 'GET',
                'description': '获取当前数据'
            },
            
            'get_data_history': {
                'endpoint': '/get_data_history',
                'method': 'GET',
                'description': '获取历史数据'
            },
            
            # 日志路由
            'get_request_logs': {
                'endpoint': '/get_request_logs',
                'method': 'GET',
                'description': '获取请求日志'
            },
            
            # 扩展功能路由
            'execute_program': {
                'endpoint': '/execute_program',
                'method': 'POST',
                'description': '执行外部程序'
            },
            
            'get_system_info': {
                'endpoint': '/get_system_info',
                'method': 'GET',
                'description': '获取系统信息'
            },
            
            'update_config': {
                'endpoint': '/update_config',
                'method': 'POST',
                'description': '更新配置'
            },
            
            'get_config': {
                'endpoint': '/get_config',
                'method': 'GET',
                'description': '获取当前配置'
            },
            
            # 新增的扩展功能路由
            'execute_desktop_program': {
                'endpoint': '/execute_desktop_program',
                'method': 'POST',
                'description': '执行桌面端程序'
            },
            
            'execute_backend_program': {
                'endpoint': '/execute_backend_program',
                'method': 'POST',
                'description': '通过后台服务执行程序'
            },
            
            'get_available_routes': {
                'endpoint': '/get_available_routes',
                'method': 'GET',
                'description': '获取所有可用路由'
            }
        }
        
        # 创建反向查找字典
        self.endpoints = {route['endpoint']: name for name, route in self.routes.items()}
        self.descriptions = {route['description']: name for name, route in self.routes.items()}
    
    def get_route(self, name):
        """
        根据路由名称获取路由信息
        
        Args:
            name (str): 路由名称
            
        Returns:
            dict: 路由信息，如果未找到返回None
        """
        return self.routes.get(name)
    
    def get_endpoint(self, name):
        """
        根据路由名称获取端点
        
        Args:
            name (str): 路由名称
            
        Returns:
            str: 路由端点，如果未找到返回None
        """
        route = self.routes.get(name)
        return route['endpoint'] if route else None
    
    def get_method(self, name):
        """
        根据路由名称获取HTTP方法
        
        Args:
            name (str): 路由名称
            
        Returns:
            str: HTTP方法，如果未找到返回None
        """
        route = self.routes.get(name)
        return route['method'] if route else None
    
    def get_description(self, name):
        """
        根据路由名称获取描述
        
        Args:
            name (str): 路由名称
            
        Returns:
            str: 路由描述，如果未找到返回None
        """
        route = self.routes.get(name)
        return route['description'] if route else None
    
    def find_by_endpoint(self, endpoint):
        """
        根据端点查找路由名称
        
        Args:
            endpoint (str): 路由端点
            
        Returns:
            str: 路由名称，如果未找到返回None
        """
        return self.endpoints.get(endpoint)
    
    def find_by_description(self, description):
        """
        根据描述查找路由名称
        
        Args:
            description (str): 路由描述
            
        Returns:
            str: 路由名称，如果未找到返回None
        """
        return self.descriptions.get(description)
    
    def list_routes(self):
        """
        列出所有路由
        
        Returns:
            dict: 所有路由信息
        """
        return self.routes.copy()

# 创建全局路由管理器实例
route_manager = RouteManager()

# 便捷函数
def get_route(name):
    """获取路由信息"""
    return route_manager.get_route(name)

def get_endpoint(name):
    """获取路由端点"""
    return route_manager.get_endpoint(name)

def get_method(name):
    """获取路由方法"""
    return route_manager.get_method(name)

def get_description(name):
    """获取路由描述"""
    return route_manager.get_description(name)