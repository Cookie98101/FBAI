# 认证系统部署说明

## 环境自动切换

HTML已配置自动环境检测：
- **本地访问** (`localhost`)：自动使用 `http://localhost:8000/api`
- **服务器访问** (域名/IP)：自动使用 `http://你的域名/auth_backend/api`

## 部署方案

### 方案A：Apache服务器（推荐 - 使用80端口）

#### 1. 配置虚拟主机

在Apache配置文件中添加（通常是 `httpd.conf` 或 `sites-available/your-site.conf`）：

```apache
<VirtualHost *:80>
    ServerName your-domain.com
    DocumentRoot "D:/项目/AI测试项目/数据展示测试"
    
    # 启用PHP支持
    <FilesMatch \.php$>
        SetHandler application/x-httpd-php
    </FilesMatch>
    
    # auth_backend目录配置
    <Directory "D:/项目/AI测试项目/数据展示测试/auth_backend">
        Options Indexes FollowSymLinks
        AllowOverride All
        Require all granted
    </Directory>
    
    # 数据目录保护（禁止外部访问）
    <Directory "D:/项目/AI测试项目/数据展示测试/auth_backend/data">
        Require all denied
    </Directory>
</VirtualHost>
```

#### 2. 重启Apache
```bash
# Windows
httpd -k restart

# Linux
systemctl restart apache2
```

#### 3. 访问地址
```
http://your-domain.com/auth_backend/admin/index.html
```

**优点**：
- ✅ 使用标准80端口，无需额外开通端口
- ✅ 浏览器默认端口，用户访问方便
- ✅ 生产环境稳定可靠

---

### 方案B：Nginx服务器（使用80端口）

#### 1. 配置文件 (`/etc/nginx/sites-available/default`)

```nginx
server {
    listen 80;
    server_name your-domain.com;
    root /var/www/项目/AI测试项目/数据展示测试;
    index index.html index.php;

    # 处理PHP文件
    location ~ \.php$ {
        fastcgi_pass unix:/var/run/php/php8.1-fpm.sock;
        fastcgi_index index.php;
        include fastcgi_params;
        fastcgi_param SCRIPT_FILENAME $document_root$fastcgi_script_name;
    }

    # auth_backend目录
    location /auth_backend/ {
        try_files $uri $uri/ =404;
    }

    # 保护数据目录
    location /auth_backend/data/ {
        deny all;
        return 403;
    }
}
```

#### 2. 重启Nginx
```bash
systemctl restart nginx
```

**优点**：
- ✅ 高性能
- ✅ 使用标准80端口
- ✅ 配置灵活

---

### 方案C：PHP内置服务器（仅限本地开发）

**当前使用方案**，仅用于本地测试：

```bash
cd d:\项目\AI测试项目\数据展示测试\auth_backend
php -S localhost:8000
```

访问：`http://localhost:8000/admin/index.html`

**局限**：
- ⚠️ 仅单线程，性能差
- ⚠️ 不适合生产环境
- ⚠️ 需要手动启动

---

### 方案D：自定义端口（需要开通端口）

如果必须使用8000端口部署到服务器：

#### Apache配置
```apache
Listen 8000
<VirtualHost *:8000>
    ServerName your-domain.com
    DocumentRoot "D:/项目/AI测试项目/数据展示测试/auth_backend"
    # ... 其他配置同方案A
</VirtualHost>
```

#### 防火墙开放端口
```bash
# Linux - firewalld
firewall-cmd --permanent --add-port=8000/tcp
firewall-cmd --reload

# Linux - ufw
ufw allow 8000/tcp

# Windows防火墙
netsh advfirewall firewall add rule name="Auth Backend" dir=in action=allow protocol=TCP localport=8000
```

#### 访问地址
```
http://your-domain.com:8000/admin/index.html
```

**缺点**：
- ⚠️ 需要额外开通防火墙端口
- ⚠️ 用户需要记住端口号
- ⚠️ 某些企业网络可能屏蔽非标准端口

---

## 推荐部署流程

### 🔥 生产环境推荐

1. **使用Apache或Nginx**
2. **配置在80端口**（或443 HTTPS）
3. **无需开通额外端口**
4. **HTML会自动检测使用正确的API地址**

### 开发环境

1. 使用PHP内置服务器（当前方案）
2. 端口8000，仅本地访问
3. 快速测试，无需复杂配置

---

## 安全建议

1. **保护data目录**：禁止外部直接访问JSON数据文件
2. **修改管理员密钥**：`ADMIN_KEY` 改为复杂字符串
3. **启用HTTPS**：生产环境必须使用SSL证书
4. **限制访问IP**：如有需要，只允许特定IP访问管理后台

---

## 常见问题

### Q: 我需要开通8000端口吗？
**A**: 
- **本地开发**：不需要，只在本机访问
- **服务器部署**：**不推荐**使用8000端口，建议用标准80端口

### Q: 如何切换环境？
**A**: HTML已自动检测环境，无需手动修改：
- 访问 `localhost` → 自动用8000端口
- 访问域名/IP → 自动用80端口的 `/auth_backend/api`

### Q: 部署到服务器后还需要运行 `php -S` 命令吗？
**A**: **不需要**。使用Apache/Nginx后，它们会自动处理PHP请求。
