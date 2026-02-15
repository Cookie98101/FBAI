<?php
/**
 * 管理员API - 用于后台管理用户
 */

require_once __DIR__ . '/../config/config.php';

// 定义常量
define('USER_ACCOUNTS_DIR', __DIR__ . '/../data/user_accounts/');
define('NOTIFICATION_FILE', __DIR__ . '/../data/notification.json');

header('Content-Type: application/json; charset=utf-8');
header('Access-Control-Allow-Origin: *');
header('Access-Control-Allow-Methods: GET, POST, OPTIONS');
header('Access-Control-Allow-Headers: Content-Type');

if ($_SERVER['REQUEST_METHOD'] === 'OPTIONS') {
    exit(0);
}

$action = $_GET['action'] ?? $_POST['action'] ?? '';
$adminKey = $_GET['admin_key'] ?? $_POST['admin_key'] ?? '';

// get_notification 不需要管理员密钥（供客户端调用）
if ($action !== 'get_notification' && $action !== 'get_user_accounts') {
    // 验证管理员密钥
    if ($adminKey !== ADMIN_KEY) {
        echo json_encode(['status' => 'error', 'message' => '无效的管理员密钥']);
        exit;
    }
}

switch ($action) {
    case 'create_user':
        handleCreateUser();
        break;
    case 'update_license':
        handleUpdateLicense();
        break;
    case 'list_users':
        handleListUsers();
        break;
    case 'list_sessions':
        handleListSessions();
        break;
    case 'kick_user':
        handleKickUser();
        break;
    case 'extend_time':
        handleExtendTime();
        break;
    case 'delete_user':
        handleDeleteUser();
        break;
    case 'reset_password':
        handleResetPassword();
        break;
    case 'update_quota':
        handleUpdateQuota();
        break;
    case 'clean_sessions':
        handleCleanSessions();
        break;
    case 'unbind_device':
        handleUnbindDevice();
        break;
    // 账号管理相关
    case 'set_user_accounts':
        handleSetUserAccounts();
        break;
    case 'get_user_accounts':
        handleGetUserAccounts();
        break;
    case 'get_user_accounts_text':
        handleGetUserAccountsText();
        break;
    // 通知管理相关
    case 'set_notification':
        handleSetNotification();
        break;
    case 'get_notification':
        handleGetNotification();
        break;
    default:
        echo json_encode(['status' => 'error', 'message' => '无效的操作']);
}

// 自动清理过期会话（每次请求时）
autoCleanExpiredSessions();

function handleCreateUser() {
    $username = $_POST['username'] ?? '';
    $password = $_POST['password'] ?? '';
    $email = $_POST['email'] ?? '';
    $expire_days = intval($_POST['expire_days'] ?? 30);
    $max_windows = intval($_POST['max_windows'] ?? 4);
    $max_simulators = intval($_POST['max_simulators'] ?? DEFAULT_MAX_SIMULATORS);
    $max_daily_hours = intval($_POST['max_daily_hours'] ?? DEFAULT_DAILY_HOURS);
    
    if (empty($username) || empty($password)) {
        echo json_encode(['status' => 'error', 'message' => '用户名和密码不能为空']);
        return;
    }
    
    $users = readJsonFile(USERS_FILE);
    $licenses = readJsonFile(LICENSES_FILE);
    
    // 检查用户名是否已存在
    foreach ($users as $user) {
        if ($user['username'] === $username) {
            echo json_encode(['status' => 'error', 'message' => '用户名已存在']);
            return;
        }
    }
    
    // 创建用户
    $userId = count($users) + 1;
    $newUser = [
        'id' => $userId,
        'username' => $username,
        'password_hash' => password_hash($password, PASSWORD_DEFAULT),
        'email' => $email,
        'status' => 'active',
        'created_at' => date('Y-m-d H:i:s')
    ];
    
    $users[] = $newUser;
    
    // 创建授权
    $licenseKey = generateRandomString(32);
    $expireDate = date('Y-m-d H:i:s', strtotime("+{$expire_days} days"));
    
    $newLicense = [
        'id' => count($licenses) + 1,
        'user_id' => $userId,
        'license_key' => $licenseKey,
        'expire_date' => $expireDate,
        'max_windows' => $max_windows,
        'max_simulators' => $max_simulators,
        'max_daily_hours' => $max_daily_hours,
        'status' => 'active',
        'created_at' => date('Y-m-d H:i:s')
    ];
    
    $licenses[] = $newLicense;
    
    writeJsonFile(USERS_FILE, $users);
    writeJsonFile(LICENSES_FILE, $licenses);
    
    logAction('create_user', $userId, ['username' => $username, 'expire_days' => $expire_days]);
    
    echo json_encode([
        'status' => 'success',
        'message' => '用户创建成功',
        'data' => [
            'user_id' => $userId,
            'username' => $username,
            'license_key' => $licenseKey,
            'expire_date' => $expireDate
        ]
    ]);
}

function handleUpdateLicense() {
    $userId = intval($_POST['user_id'] ?? 0);
    $expireDays = intval($_POST['expire_days'] ?? 0);
    $maxSimulators = intval($_POST['max_simulators'] ?? 0);
    $maxDailyHours = intval($_POST['max_daily_hours'] ?? 0);
    
    if ($userId <= 0) {
        echo json_encode(['status' => 'error', 'message' => '无效的用户ID']);
        return;
    }
    
    $licenses = readJsonFile(LICENSES_FILE);
    $updated = false;
    
    foreach ($licenses as &$license) {
        if ($license['user_id'] === $userId && $license['status'] === 'active') {
            if ($expireDays > 0) {
                $license['expire_date'] = date('Y-m-d H:i:s', strtotime("+{$expireDays} days"));
            }
            if ($maxSimulators > 0) {
                $license['max_simulators'] = $maxSimulators;
            }
            if ($maxDailyHours > 0) {
                $license['max_daily_hours'] = $maxDailyHours;
            }
            $license['updated_at'] = date('Y-m-d H:i:s');
            $updated = true;
            break;
        }
    }
    
    if ($updated) {
        writeJsonFile(LICENSES_FILE, $licenses);
        logAction('update_license', $userId, [
            'expire_days' => $expireDays,
            'max_simulators' => $maxSimulators,
            'max_daily_hours' => $maxDailyHours
        ]);
        echo json_encode(['status' => 'success', 'message' => '授权更新成功']);
    } else {
        echo json_encode(['status' => 'error', 'message' => '未找到有效的授权']);
    }
}

function handleExtendTime() {
    $userId = intval($_POST['user_id'] ?? 0);
    $extendDays = intval($_POST['extend_days'] ?? 0);
    
    if ($userId <= 0 || $extendDays <= 0) {
        echo json_encode(['status' => 'error', 'message' => '无效的参数']);
        return;
    }
    
    $licenses = readJsonFile(LICENSES_FILE);
    $updated = false;
    
    foreach ($licenses as &$license) {
        if ($license['user_id'] === $userId && $license['status'] === 'active') {
            // 在当前到期时间基础上延长
            $currentExpire = strtotime($license['expire_date']);
            $newExpire = $currentExpire + ($extendDays * 24 * 3600);
            $license['expire_date'] = date('Y-m-d H:i:s', $newExpire);
            $license['updated_at'] = date('Y-m-d H:i:s');
            $updated = true;
            break;
        }
    }
    
    if ($updated) {
        writeJsonFile(LICENSES_FILE, $licenses);
        logAction('extend_time', $userId, ['extend_days' => $extendDays]);
        echo json_encode([
            'status' => 'success', 
            'message' => "成功延长 {$extendDays} 天",
            'data' => ['new_expire_date' => $license['expire_date']]
        ]);
    } else {
        echo json_encode(['status' => 'error', 'message' => '未找到有效的授权']);
    }
}

function handleListUsers() {
    $users = readJsonFile(USERS_FILE);
    $licenses = readJsonFile(LICENSES_FILE);
    $sessions = readJsonFile(SESSIONS_FILE);
    
    $result = [];
    
    foreach ($users as $user) {
        // 查找用户授权
        $userLicense = null;
        foreach ($licenses as $license) {
            if ($license['user_id'] === $user['id'] && $license['status'] === 'active') {
                $userLicense = $license;
                break;
            }
        }
        
        // 统计在线设备
        $onlineDevices = 0;
        $currentTime = time();
        foreach ($sessions as $session) {
            if ($session['user_id'] === $user['id'] && 
                ($currentTime - strtotime($session['last_heartbeat'])) < HEARTBEAT_TIMEOUT) {
                $onlineDevices++;
            }
        }
        
        $result[] = [
            'id' => $user['id'],
            'username' => $user['username'],
            'email' => $user['email'],
            'status' => $user['status'],
            'created_at' => $user['created_at'],
            'license' => $userLicense,
            'online_devices' => $onlineDevices,
            'bound_device_id' => isset($user['bound_device_id']) ? substr($user['bound_device_id'], 0, 16) . '...' : null,
            'device_bound_at' => $user['device_bound_at'] ?? null,
            'device_bound' => isset($user['bound_device_id']) && !empty($user['bound_device_id'])
        ];
    }
    
    echo json_encode(['status' => 'success', 'data' => $result]);
}

function handleListSessions() {
    $sessions = readJsonFile(SESSIONS_FILE);
    $users = readJsonFile(USERS_FILE);
    
    $result = [];
    $currentTime = time();
    
    foreach ($sessions as $session) {
        $isOnline = ($currentTime - strtotime($session['last_heartbeat'])) < HEARTBEAT_TIMEOUT;
        
        if ($isOnline) {
            $result[] = [
                'user_id' => $session['user_id'],
                'username' => $session['username'],
                'real_name' => $session['real_name'] ?? '未设置',
                'device_id' => $session['device_id'],
                'login_time' => $session['login_time'],
                'last_heartbeat' => $session['last_heartbeat'],
                'daily_usage' => $session['daily_usage']
            ];
        }
    }
    
    echo json_encode(['status' => 'success', 'data' => $result]);
}

function handleKickUser() {
    $userId = intval($_POST['user_id'] ?? 0);
    
    if ($userId <= 0) {
        echo json_encode(['status' => 'error', 'message' => '无效的用户ID']);
        return;
    }
    
    $sessions = readJsonFile(SESSIONS_FILE);
    $newSessions = [];
    $kickedCount = 0;
    
    foreach ($sessions as $session) {
        if ($session['user_id'] !== $userId) {
            $newSessions[] = $session;
        } else {
            $kickedCount++;
        }
    }
    
    writeJsonFile(SESSIONS_FILE, $newSessions);
    logAction('kick_user', $userId, ['kicked_sessions' => $kickedCount]);
    
    echo json_encode([
        'status' => 'success', 
        'message' => "成功踢出用户，共 {$kickedCount} 个会话"
    ]);
}

function handleDeleteUser() {
    $userId = intval($_POST['user_id'] ?? 0);
    
    if ($userId <= 0) {
        echo json_encode(['status' => 'error', 'message' => '无效的用户ID']);
        return;
    }
    
    // 读取所有数据文件
    $users = readJsonFile(USERS_FILE);
    $licenses = readJsonFile(LICENSES_FILE);
    $sessions = readJsonFile(SESSIONS_FILE);
    
    // 检查用户是否存在
    $userExists = false;
    $username = '';
    foreach ($users as $user) {
        if ($user['id'] === $userId) {
            $userExists = true;
            $username = $user['username'];
            break;
        }
    }
    
    if (!$userExists) {
        echo json_encode(['status' => 'error', 'message' => '用户不存在']);
        return;
    }
    
    // 删除用户
    $newUsers = [];
    foreach ($users as $user) {
        if ($user['id'] !== $userId) {
            $newUsers[] = $user;
        }
    }
    
    // 删除用户的授权
    $newLicenses = [];
    foreach ($licenses as $license) {
        if ($license['user_id'] !== $userId) {
            $newLicenses[] = $license;
        }
    }
    
    // 删除用户的会话
    $newSessions = [];
    $deletedSessions = 0;
    foreach ($sessions as $session) {
        if ($session['user_id'] !== $userId) {
            $newSessions[] = $session;
        } else {
            $deletedSessions++;
        }
    }
    
    // 保存更新后的数据
    writeJsonFile(USERS_FILE, $newUsers);
    writeJsonFile(LICENSES_FILE, $newLicenses);
    writeJsonFile(SESSIONS_FILE, $newSessions);
    
    // 记录日志
    logAction('delete_user', $userId, [
        'username' => $username,
        'deleted_sessions' => $deletedSessions
    ]);
    
    echo json_encode([
        'status' => 'success',
        'message' => "成功删除用户 {$username}"
    ]);
}

function handleResetPassword() {
    $userId = intval($_POST['user_id'] ?? 0);
    $newPassword = $_POST['new_password'] ?? '';
    
    if ($userId <= 0) {
        echo json_encode(['status' => 'error', 'message' => '无效的用户ID']);
        return;
    }
    
    if (empty($newPassword)) {
        echo json_encode(['status' => 'error', 'message' => '新密码不能为空']);
        return;
    }
    
    if (strlen($newPassword) < 6) {
        echo json_encode(['status' => 'error', 'message' => '密码长度至少为6位']);
        return;
    }
    
    // 读取用户数据
    $users = readJsonFile(USERS_FILE);
    $updated = false;
    $username = '';
    
    foreach ($users as &$user) {
        if ($user['id'] === $userId) {
            $username = $user['username'];
            $user['password_hash'] = password_hash($newPassword, PASSWORD_DEFAULT);
            $user['updated_at'] = date('Y-m-d H:i:s');
            $updated = true;
            break;
        }
    }
    
    if ($updated) {
        writeJsonFile(USERS_FILE, $users);
        logAction('reset_password', $userId, ['username' => $username]);
        echo json_encode([
            'status' => 'success',
            'message' => "用户 {$username} 的密码已重置"
        ]);
    } else {
        echo json_encode(['status' => 'error', 'message' => '用户不存在']);
    }
}

function handleUpdateQuota() {
    $userId = intval($_POST['user_id'] ?? 0);
    $maxWindows = intval($_POST['max_windows'] ?? 4);
    $maxSimulators = intval($_POST['max_simulators'] ?? 5);
    
    if ($userId <= 0) {
        echo json_encode(['status' => 'error', 'message' => '无效的用户ID']);
        return;
    }
    
    // 验证范围
    if ($maxWindows < 1 || $maxWindows > 20) {
        echo json_encode(['status' => 'error', 'message' => '窗口数量必须在 1-20 之间']);
        return;
    }
    
    if ($maxSimulators < 1 || $maxSimulators > 100) {
        echo json_encode(['status' => 'error', 'message' => '浏览器数量必须在 1-100 之间']);
        return;
    }
    
    // 读取用户和授权数据
    $users = readJsonFile(USERS_FILE);
    $licenses = readJsonFile(LICENSES_FILE);
    
    $userExists = false;
    $username = '';
    
    // 检查用户是否存在
    foreach ($users as $user) {
        if ($user['id'] === $userId) {
            $userExists = true;
            $username = $user['username'];
            break;
        }
    }
    
    if (!$userExists) {
        echo json_encode(['status' => 'error', 'message' => '用户不存在']);
        return;
    }
    
    // 更新授权信息
    $updated = false;
    foreach ($licenses as &$license) {
        if ($license['user_id'] === $userId) {
            $license['max_windows'] = $maxWindows;
            $license['max_simulators'] = $maxSimulators;
            $license['updated_at'] = date('Y-m-d H:i:s');
            $updated = true;
            break;
        }
    }
    
    if ($updated) {
        writeJsonFile(LICENSES_FILE, $licenses);
        logAction('update_quota', $userId, [
            'username' => $username,
            'max_windows' => $maxWindows,
            'max_simulators' => $maxSimulators
        ]);
        
        echo json_encode([
            'status' => 'success',
            'message' => "用户 {$username} 的配额已更新\n窗口数量: {$maxWindows}\n浏览器数量: {$maxSimulators}"
        ]);
    } else {
        echo json_encode(['status' => 'error', 'message' => '该用户没有授权信息']);
    }
}

function handleCleanSessions() {
    $sessions = readJsonFile(SESSIONS_FILE);
    $currentTime = time();
    $cleanedSessions = [];
    $removedCount = 0;
    
    foreach ($sessions as $session) {
        $isActive = ($currentTime - strtotime($session['last_heartbeat'])) < HEARTBEAT_TIMEOUT;
        if ($isActive) {
            $cleanedSessions[] = $session;
        } else {
            $removedCount++;
        }
    }
    
    writeJsonFile(SESSIONS_FILE, $cleanedSessions);
    logAction('clean_sessions', null, ['removed_count' => $removedCount]);
    
    echo json_encode([
        'status' => 'success',
        'message' => "已清理 {$removedCount} 个过期会话",
        'data' => [
            'removed' => $removedCount,
            'remaining' => count($cleanedSessions)
        ]
    ]);
}

function handleUnbindDevice() {
    $userId = intval($_POST['user_id'] ?? 0);
    
    if (empty($userId)) {
        echo json_encode(['status' => 'error', 'message' => '用户ID不能为空']);
        return;
    }
    
    $users = readJsonFile(USERS_FILE);
    $userFound = false;
    $oldDeviceId = null;
    
    // 查找并解绑设备
    $users = array_map(function($u) use ($userId, &$userFound, &$oldDeviceId) {
        if ($u['id'] === $userId) {
            $userFound = true;
            $oldDeviceId = $u['bound_device_id'] ?? null;
            $u['bound_device_id'] = null;
            $u['device_unbound_at'] = date('Y-m-d H:i:s');
        }
        return $u;
    }, $users);
    
    if (!$userFound) {
        echo json_encode(['status' => 'error', 'message' => '用户不存在']);
        return;
    }
    
    writeJsonFile(USERS_FILE, $users);
    
    // 踢出该用户的所有会话（强制重新登录绑定）
    $sessions = readJsonFile(SESSIONS_FILE);
    $sessions = array_filter($sessions, function($s) use ($userId) {
        return $s['user_id'] !== $userId;
    });
    writeJsonFile(SESSIONS_FILE, array_values($sessions));
    
    logAction('device_unbound', $userId, [
        'old_device_id' => $oldDeviceId ? substr($oldDeviceId, 0, 16) . '...' : 'none',
        'admin_action' => true
    ]);
    
    echo json_encode([
        'status' => 'success',
        'message' => '设备解绑成功，用户需要重新登录',
        'data' => [
            'user_id' => $userId,
            'old_device_id' => $oldDeviceId ? substr($oldDeviceId, 0, 16) . '...' : null
        ]
    ]);
}

function autoCleanExpiredSessions() {
    // 自动清理过期会话，每次API调用时执行
    $sessions = readJsonFile(SESSIONS_FILE);
    $currentTime = time();
    $cleanedSessions = [];
    $removedCount = 0;
    
    foreach ($sessions as $session) {
        $isActive = ($currentTime - strtotime($session['last_heartbeat'])) < HEARTBEAT_TIMEOUT;
        if ($isActive) {
            $cleanedSessions[] = $session;
        } else {
            $removedCount++;
        }
    }
    
    // 只有在清理了会话时才写入
    if ($removedCount > 0) {
        writeJsonFile(SESSIONS_FILE, $cleanedSessions);
    }
}

// ==================== 账号管理功能 ====================

function handleSetUserAccounts() {
    // 为用户设置账号列表
    $username = $_POST['username'] ?? '';
    $accountsText = $_POST['accounts'] ?? '';
    
    if (empty($username)) {
        echo json_encode(['status' => 'error', 'message' => '用户名不能为空']);
        return;
    }
    
    // 检查用户是否存在
    $users = readJsonFile(USERS_FILE);
    $userExists = false;
    $userId = null;
    
    foreach ($users as $user) {
        if ($user['username'] === $username) {
            $userExists = true;
            $userId = $user['id'];
            break;
        }
    }
    
    if (!$userExists) {
        echo json_encode(['status' => 'error', 'message' => '用户不存在']);
        return;
    }
    
    // 解析账号列表（每行一个）
    $lines = explode("\n", $accountsText);
    $accounts = [];
    
    foreach ($lines as $line) {
        $line = trim($line);
        if (empty($line) || strpos($line, '#') === 0) {
            continue; // 跳过空行和注释
        }
        $accounts[] = $line;
    }
    
    // 保存到用户账号文件
    if (!is_dir(USER_ACCOUNTS_DIR)) {
        mkdir(USER_ACCOUNTS_DIR, 0777, true);
    }
    
    $userAccountFile = USER_ACCOUNTS_DIR . $username . '.txt';
    file_put_contents($userAccountFile, implode("\n", $accounts));
    
    logAction('set_user_accounts', $userId, [
        'username' => $username,
        'account_count' => count($accounts)
    ]);
    
    echo json_encode([
        'status' => 'success',
        'message' => "成功为用户 {$username} 设置 " . count($accounts) . " 个账号"
    ]);
}

function handleGetUserAccounts() {
    // 此API不需要admin_key，供客户端调用
    // 通过用户名获取分配的账号
    $username = $_POST['username'] ?? $_GET['username'] ?? '';
    
    if (empty($username)) {
        echo json_encode(['status' => 'error', 'message' => '用户名不能为空']);
        return;
    }
    
    // 检查用户是否存在
    $users = readJsonFile(USERS_FILE);
    $userExists = false;
    
    foreach ($users as $user) {
        if ($user['username'] === $username) {
            $userExists = true;
            break;
        }
    }
    
    if (!$userExists) {
        echo json_encode(['status' => 'error', 'message' => '用户不存在']);
        return;
    }
    
    // 读取用户账号文件
    $userAccountFile = USER_ACCOUNTS_DIR . $username . '.txt';
    
    if (!file_exists($userAccountFile)) {
        echo json_encode([
            'status' => 'success',
            'data' => []
        ]);
        return;
    }
    
    $content = file_get_contents($userAccountFile);
    $lines = explode("\n", $content);
    $accounts = [];
    
    foreach ($lines as $line) {
        $line = trim($line);
        if (empty($line) || strpos($line, '#') === 0) {
            continue; // 跳过空行和注释
        }
        
        // 解析账号行（使用 ---- 分隔）
        $parts = explode('----', $line);
        if (count($parts) >= 1 && !empty($parts[0])) {
            $accounts[] = [
                'c_user' => $parts[0],
                'account_line' => $line
            ];
        }
    }
    
    echo json_encode([
        'status' => 'success',
        'data' => $accounts
    ]);
}

function handleGetUserAccountsText() {
    // 获取用户账号的原始文本（用于编辑）
    $username = $_POST['username'] ?? $_GET['username'] ?? '';
    
    if (empty($username)) {
        echo json_encode(['status' => 'error', 'message' => '用户名不能为空']);
        return;
    }
    
    // 读取用户账号文件
    $userAccountFile = USER_ACCOUNTS_DIR . $username . '.txt';
    
    if (!file_exists($userAccountFile)) {
        echo json_encode([
            'status' => 'success',
            'data' => ''
        ]);
        return;
    }
    
    $content = file_get_contents($userAccountFile);
    
    echo json_encode([
        'status' => 'success',
        'data' => $content
    ]);
}

// ==================== 通知管理功能 ====================

function handleSetNotification() {
    // 设置系统通知
    $notification = $_POST['notification'] ?? '';
    
    // 保存通知到文件
    $data = [
        'notification' => $notification,
        'updated_at' => date('Y-m-d H:i:s')
    ];
    
    try {
        // 确保目录存在
        $dir = dirname(NOTIFICATION_FILE);
        if (!is_dir($dir)) {
            mkdir($dir, 0777, true);
        }
        
        file_put_contents(NOTIFICATION_FILE, json_encode($data, JSON_UNESCAPED_UNICODE | JSON_PRETTY_PRINT));
        
        logAction('set_notification', null, ['notification' => $notification]);
        
        echo json_encode([
            'status' => 'success',
            'message' => '通知设置成功'
        ]);
    } catch (Exception $e) {
        echo json_encode([
            'status' => 'error',
            'message' => '保存通知失败: ' . $e->getMessage()
        ]);
    }
}

function handleGetNotification() {
    // 获取系统通知（不需要admin_key，供客户端调用）
    
    if (!file_exists(NOTIFICATION_FILE)) {
        // 返回默认通知
        echo json_encode([
            'status' => 'success',
            'data' => [
                'notification' => '就绪 - Facebook数据展示程序正在运行 - 当前版本支持实时数据刷新功能 - 程序每30秒自动刷新一次数据',
                'updated_at' => null
            ]
        ]);
        return;
    }
    
    try {
        $content = file_get_contents(NOTIFICATION_FILE);
        $data = json_decode($content, true);
        
        echo json_encode([
            'status' => 'success',
            'data' => $data
        ]);
    } catch (Exception $e) {
        echo json_encode([
            'status' => 'error',
            'message' => '读取通知失败: ' . $e->getMessage()
        ]);
    }
}
?>