<?php
header('Content-Type: application/json; charset=utf-8');

$adminPhpPath = __DIR__ . '/admin.php';

// 读取文件内容
$code = file_get_contents($adminPhpPath);

// 检查基本信息
$result = [
    'file' => $adminPhpPath,
    'file_size' => strlen($code),
    'php_open_tags' => substr_count($code, '<?php'),
    'php_close_tags' => substr_count($code, '?>'),
    'ends_with_php_close' => (substr(trim($code), -2) === '?>'),
    'last_100_chars' => substr($code, -100),
];

// 使用 php -l 检查语法
$output = [];
$return_var = 0;
exec("php -l " . escapeshellarg($adminPhpPath) . " 2>&1", $output, $return_var);

$result['syntax_check_output'] = implode("\n", $output);
$result['has_syntax_error'] = ($return_var !== 0);

echo json_encode($result, JSON_PRETTY_PRINT | JSON_UNESCAPED_UNICODE);
?>
