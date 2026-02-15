<?php
/**
 * 版本检查API
 * 提供软件更新检查服务
 */

header('Content-Type: application/json; charset=utf-8');
header('Access-Control-Allow-Origin: *');

// 版本配置文件路径
define('VERSION_CONFIG_FILE', __DIR__ . '/../data/version_config.json');

/**
 * 获取版本信息
 */
function getVersionInfo() {
    if (!file_exists(VERSION_CONFIG_FILE)) {
        // 如果配置文件不存在，返回默认配置
        return [
            'status' => 'success',
            'data' => [
                'latest_version' => '1.0.0',
                'current_is_latest' => true,
                'message' => '当前已是最新版本'
            ]
        ];
    }
    
    $config = json_decode(file_get_contents(VERSION_CONFIG_FILE), true);
    
    // 获取客户端当前版本
    $client_version = $_GET['version'] ?? '0.0.0';
    
    // 获取最新版本信息
    $latest = $config['latest_version_info'] ?? null;
    
    if (!$latest) {
        return [
            'status' => 'error',
            'message' => '版本信息配置错误'
        ];
    }
    
    // 比较版本号
    $is_latest = version_compare($client_version, $latest['version'], '>=');
    
    return [
        'status' => 'success',
        'data' => [
            'client_version' => $client_version,
            'latest_version' => $latest['version'],
            'build_date' => $latest['build_date'],
            'release_date' => $latest['release_date'],
            'download_url' => $latest['download_url'],
            'file_size' => $latest['file_size'],
            'file_size_mb' => round($latest['file_size'] / 1024 / 1024, 2),
            'md5' => $latest['md5'],
            'changelog' => $latest['changelog'],
            'force_update' => $latest['force_update'] ?? false,
            'min_compatible_version' => $latest['min_compatible_version'] ?? '1.0.0',
            'current_is_latest' => $is_latest,
            'need_update' => !$is_latest,
            'message' => $is_latest ? '当前已是最新版本' : '发现新版本'
        ]
    ];
}

/**
 * 记录更新检查日志
 */
function logUpdateCheck($client_version, $client_ip) {
    $log_file = __DIR__ . '/../logs/update_check.log';
    $log_dir = dirname($log_file);
    
    if (!is_dir($log_dir)) {
        mkdir($log_dir, 0755, true);
    }
    
    $log_entry = sprintf(
        "[%s] IP: %s, Version: %s\n",
        date('Y-m-d H:i:s'),
        $client_ip,
        $client_version
    );
    
    file_put_contents($log_file, $log_entry, FILE_APPEND);
}

// 主逻辑
try {
    $client_version = $_GET['version'] ?? '0.0.0';
    $client_ip = $_SERVER['REMOTE_ADDR'] ?? 'unknown';
    
    // 记录检查日志
    logUpdateCheck($client_version, $client_ip);
    
    // 获取版本信息
    $result = getVersionInfo();
    
    echo json_encode($result, JSON_UNESCAPED_UNICODE | JSON_PRETTY_PRINT);
    
} catch (Exception $e) {
    echo json_encode([
        'status' => 'error',
        'message' => '服务器内部错误: ' . $e->getMessage()
    ], JSON_UNESCAPED_UNICODE);
}
?>
