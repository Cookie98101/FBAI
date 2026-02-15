<?php
/**
 * 系统配置文件
 */

// 数据文件路径
define('DATA_DIR', __DIR__ . '/../data/');
define('USERS_FILE', DATA_DIR . 'users.json');
define('LICENSES_FILE', DATA_DIR . 'licenses.json');
define('SESSIONS_FILE', DATA_DIR . 'sessions.json');
define('LOGS_FILE', DATA_DIR . 'logs.json');

// 系统设置
define('DEFAULT_MAX_SIMULATORS', 5);
define('DEFAULT_DAILY_HOURS', 24);
define('SESSION_TIMEOUT', 3600); // 1小时
define('HEARTBEAT_TIMEOUT', 300); // 5分钟

// 管理员密钥
define('ADMIN_KEY', 'fb_admin_2025');

// 创建数据目录
if (!file_exists(DATA_DIR)) {
    mkdir(DATA_DIR, 0755, true);
}

// 初始化数据文件
function initDataFiles() {
    $files = [
        USERS_FILE => [],
        LICENSES_FILE => [],
        SESSIONS_FILE => [],
        LOGS_FILE => []
    ];
    
    foreach ($files as $file => $defaultData) {
        if (!file_exists($file)) {
            file_put_contents($file, json_encode($defaultData, JSON_PRETTY_PRINT | JSON_UNESCAPED_UNICODE));
        }
    }
}

// 读取JSON文件
function readJsonFile($filename) {
    if (!file_exists($filename)) {
        return [];
    }
    $content = file_get_contents($filename);
    return json_decode($content, true) ?: [];
}

// 写入JSON文件
function writeJsonFile($filename, $data) {
    return file_put_contents($filename, json_encode($data, JSON_PRETTY_PRINT | JSON_UNESCAPED_UNICODE));
}

// 记录日志
function logAction($action, $user_id = null, $details = []) {
    $logs = readJsonFile(LOGS_FILE);
    $logs[] = [
        'timestamp' => date('Y-m-d H:i:s'),
        'action' => $action,
        'user_id' => $user_id,
        'ip' => $_SERVER['REMOTE_ADDR'] ?? 'unknown',
        'details' => $details
    ];
    
    // 只保留最近1000条日志
    if (count($logs) > 1000) {
        $logs = array_slice($logs, -1000);
    }
    
    writeJsonFile(LOGS_FILE, $logs);
}

// 生成随机字符串
function generateRandomString($length = 32) {
    return bin2hex(random_bytes($length / 2));
}

// 初始化
initDataFiles();
?>
