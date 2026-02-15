<?php
// 版本检查文件
header('Content-Type: application/json; charset=utf-8');

$adminPhpPath = __DIR__ . '/admin.php';
$content = file_get_contents($adminPhpPath);

// 检查是否包含通知功能
$hasSetNotification = strpos($content, "case 'set_notification':") !== false;
$hasGetNotification = strpos($content, "case 'get_notification':") !== false;
$hasHandleSetNotification = strpos($content, "function handleSetNotification()") !== false;
$hasHandleGetNotification = strpos($content, "function handleGetNotification()") !== false;

echo json_encode([
    'file_size' => filesize($adminPhpPath),
    'last_modified' => date('Y-m-d H:i:s', filemtime($adminPhpPath)),
    'has_set_notification_case' => $hasSetNotification,
    'has_get_notification_case' => $hasGetNotification,
    'has_handleSetNotification_function' => $hasHandleSetNotification,
    'has_handleGetNotification_function' => $hasHandleGetNotification,
    'all_checks_passed' => $hasSetNotification && $hasGetNotification && $hasHandleSetNotification && $hasHandleGetNotification
], JSON_PRETTY_PRINT);
?>
