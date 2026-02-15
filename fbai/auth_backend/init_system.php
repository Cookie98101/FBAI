<?php
/**
 * 系统初始化脚本
 * 创建测试用户和基础数据
 */

require_once 'config/config.php';

echo "正在初始化认证系统...\n";

// 创建测试用户
$users = [
    [
        'id' => 1,
        'username' => 'test_user',
        'password_hash' => password_hash('123456', PASSWORD_DEFAULT),
        'email' => 'test@example.com',
        'status' => 'active',
        'created_at' => date('Y-m-d H:i:s')
    ],
    [
        'id' => 2,
        'username' => 'demo_user',
        'password_hash' => password_hash('demo123', PASSWORD_DEFAULT),
        'email' => 'demo@example.com',
        'status' => 'active',
        'created_at' => date('Y-m-d H:i:s')
    ]
];

// 创建测试授权
$licenses = [
    [
        'id' => 1,
        'user_id' => 1,
        'license_key' => generateRandomString(32),
        'expire_date' => date('Y-m-d H:i:s', strtotime('+30 days')),
        'max_simulators' => 5,
        'max_daily_hours' => 24,
        'status' => 'active',
        'created_at' => date('Y-m-d H:i:s')
    ],
    [
        'id' => 2,
        'user_id' => 2,
        'license_key' => generateRandomString(32),
        'expire_date' => date('Y-m-d H:i:s', strtotime('+7 days')),
        'max_simulators' => 3,
        'max_daily_hours' => 12,
        'status' => 'active',
        'created_at' => date('Y-m-d H:i:s')
    ]
];

// 写入数据文件
writeJsonFile(USERS_FILE, $users);
writeJsonFile(LICENSES_FILE, $licenses);
writeJsonFile(SESSIONS_FILE, []);
writeJsonFile(LOGS_FILE, []);

echo "✓ 用户数据已创建\n";
echo "✓ 授权数据已创建\n";
echo "✓ 会话数据已初始化\n";
echo "✓ 日志数据已初始化\n";

echo "\n测试账号信息:\n";
echo "==================\n";
echo "用户名: test_user\n";
echo "密码: 123456\n";
echo "授权期限: 30天\n";
echo "最大设备数: 5\n";
echo "每日最大使用时长: 24小时\n";
echo "\n";
echo "用户名: demo_user\n";
echo "密码: demo123\n";
echo "授权期限: 7天\n";
echo "最大设备数: 3\n";
echo "每日最大使用时长: 12小时\n";
echo "\n";

echo "管理员密钥: " . ADMIN_KEY . "\n";
echo "管理后台地址: http://localhost/auth_backend/admin/\n";
echo "\n";
echo "启动命令:\n";
echo "php -S localhost:80 -t .\n";

echo "\n系统初始化完成！\n";
?>
