<?php
/**
 * 调试通知API
 */

require_once __DIR__ . '/../config/config.php';

header('Content-Type: application/json; charset=utf-8');
header('Access-Control-Allow-Origin: *');
header('Access-Control-Allow-Methods: GET, POST, OPTIONS');
header('Access-Control-Allow-Headers: Content-Type');

// 记录所有接收到的数据
$debug_info = [
    'timestamp' => date('Y-m-d H:i:s'),
    'request_method' => $_SERVER['REQUEST_METHOD'],
    'get_params' => $_GET,
    'post_params' => $_POST,
    'action_from_get' => $_GET['action'] ?? 'not_set',
    'action_from_post' => $_POST['action'] ?? 'not_set',
    'final_action' => $_GET['action'] ?? $_POST['action'] ?? 'not_set',
    'admin_key_from_get' => $_GET['admin_key'] ?? 'not_set',
    'admin_key_from_post' => $_POST['admin_key'] ?? 'not_set',
];

// 测试通知功能
$action = $_GET['action'] ?? $_POST['action'] ?? '';
$adminKey = $_GET['admin_key'] ?? $_POST['admin_key'] ?? '';

$debug_info['extracted_action'] = $action;
$debug_info['extracted_admin_key'] = substr($adminKey, 0, 10) . '...';
$debug_info['action_matches_set'] = ($action === 'set_notification');
$debug_info['action_matches_get'] = ($action === 'get_notification');
$debug_info['admin_key_correct'] = ($adminKey === ADMIN_KEY);

// 测试switch逻辑
$switch_result = 'unknown';
switch ($action) {
    case 'set_notification':
        $switch_result = 'matched_set_notification';
        break;
    case 'get_notification':
        $switch_result = 'matched_get_notification';
        break;
    default:
        $switch_result = 'matched_default';
}

$debug_info['switch_result'] = $switch_result;

// 检查函数是否存在
$debug_info['handleSetNotification_exists'] = function_exists('handleSetNotification');
$debug_info['handleGetNotification_exists'] = function_exists('handleGetNotification');

echo json_encode($debug_info, JSON_PRETTY_PRINT | JSON_UNESCAPED_UNICODE);
?>
