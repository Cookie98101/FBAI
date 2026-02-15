<?php
/**
 * 用户认证API
 */

require_once __DIR__ . '/../config/config.php';

header('Content-Type: application/json; charset=utf-8');
header('Access-Control-Allow-Origin: *');
header('Access-Control-Allow-Methods: GET, POST, OPTIONS');
header('Access-Control-Allow-Headers: Content-Type');

if ($_SERVER['REQUEST_METHOD'] === 'OPTIONS') {
    exit(0);
}

$action = $_GET['action'] ?? $_POST['action'] ?? '';

switch ($action) {
    case 'login':
        handleLogin();
        break;
    case 'verify':
        handleVerify();
        break;
    case 'heartbeat':
        handleHeartbeat();
        break;
    case 'logout':
        handleLogout();
        break;
    default:
        echo json_encode(['status' => 'error', 'message' => '无效的操作']);
}

function handleLogin() {
    $username = $_POST['username'] ?? '';
    $password = $_POST['password'] ?? '';
    $device_id = $_POST['device_id'] ?? '';
    
    if (empty($username) || empty($password) || empty($device_id)) {
        echo json_encode(['status' => 'error', 'message' => '用户名、密码和设备ID不能为空']);
        return;
    }
    
    // 读取用户数据
    $users = readJsonFile(USERS_FILE);
    $licenses = readJsonFile(LICENSES_FILE);
    
    // 查找用户
    $user = null;
    foreach ($users as $u) {
        if ($u['username'] === $username) {
            $user = $u;
            break;
        }
    }
    
    if (!$user || !password_verify($password, $user['password_hash'])) {
        logAction('login_failed', null, ['username' => $username, 'device_id' => $device_id]);
        echo json_encode(['status' => 'error', 'message' => '用户名或密码错误']);
        return;
    }
    
    if ($user['status'] !== 'active') {
        logAction('login_blocked', $user['id'], ['reason' => 'user_inactive']);
        echo json_encode(['status' => 'error', 'message' => '账户已被禁用']);
        return;
    }
    
    // ========== 设备绑定检查 ==========
    // 如果用户已绑定设备，检查是否匹配
    $boundDeviceId = $user['bound_device_id'] ?? null;
    
    if ($boundDeviceId && $boundDeviceId !== $device_id) {
        // 设备不匹配，拒绝登录
        logAction('login_device_mismatch', $user['id'], [
            'bound_device' => substr($boundDeviceId, 0, 16) . '...',
            'attempted_device' => substr($device_id, 0, 16) . '...'
        ]);
        echo json_encode([
            'status' => 'error',
            'message' => '此账号已绑定其他设备，无法在当前设备登录',
            'error_code' => 'DEVICE_BOUND',
            'data' => [
                'bound_device_id' => substr($boundDeviceId, 0, 16) . '...',
                'current_device_id' => substr($device_id, 0, 16) . '...'
            ]
        ]);
        return;
    }
    
    // 如果用户尚未绑定设备，首次登录时自动绑定
    $needBindDevice = false;
    if (!$boundDeviceId) {
        $needBindDevice = true;
        // 更新用户信息，绑定当前设备
        $users = array_map(function($u) use ($user, $device_id) {
            if ($u['id'] === $user['id']) {
                $u['bound_device_id'] = $device_id;
                $u['device_bound_at'] = date('Y-m-d H:i:s');
            }
            return $u;
        }, $users);
        writeJsonFile(USERS_FILE, $users);
        logAction('device_bound', $user['id'], ['device_id' => substr($device_id, 0, 16) . '...']);
    }
    // =========================================
    
    // 查找用户授权
    $license = null;
    foreach ($licenses as $l) {
        if ($l['user_id'] === $user['id'] && $l['status'] === 'active') {
            $license = $l;
            break;
        }
    }
    
    if (!$license) {
        logAction('login_no_license', $user['id']);
        echo json_encode(['status' => 'error', 'message' => '没有有效的授权']);
        return;
    }
    
    // 检查授权是否过期
    if (strtotime($license['expire_date']) < time()) {
        logAction('login_expired', $user['id']);
        echo json_encode(['status' => 'error', 'message' => '授权已过期']);
        return;
    }
    
    // 检查设备数量限制和清理旧会话
    $sessions = readJsonFile(SESSIONS_FILE);
    $currentTime = time();
    $cleanedSessions = [];
    $activeDevices = 0;
    $deviceExists = false;
    $existingSessionIndex = -1;
    
    // 遍历所有会话，清理过期会话和检查设备数量
    foreach ($sessions as $index => $session) {
        $isActive = ($currentTime - strtotime($session['last_heartbeat'])) < HEARTBEAT_TIMEOUT;
        
        // 如果是当前用户的会话
        if ($session['user_id'] === $user['id']) {
            // 检查是否是当前设备
            if ($session['device_id'] === $device_id) {
                if ($isActive) {
                    // 当前设备已有活跃会话，标记为存在
                    $deviceExists = true;
                    $existingSessionIndex = count($cleanedSessions);
                    $cleanedSessions[] = $session;  // 保留该会话，稍后更新
                }
                // 如果是过期的同设备会话，不添加到cleanedSessions（删除）
            } else {
                // 其他设备的会话
                if ($isActive) {
                    $activeDevices++;  // 统计其他活跃设备
                    $cleanedSessions[] = $session;
                }
                // 过期会话不添加（清理）
            }
        } else {
            // 其他用户的会话，只保留活跃的
            if ($isActive) {
                $cleanedSessions[] = $session;
            }
        }
    }
    
    // 检查设备数量限制（不包括当前设备）
    if (!$deviceExists && $activeDevices >= $license['max_simulators']) {
        logAction('login_device_limit', $user['id'], ['active_devices' => $activeDevices]);
        echo json_encode(['status' => 'error', 'message' => '设备数量已达上限']);
        return;
    }
    
    // 创建或更新会话
    $sessionToken = generateRandomString(64);
    $newSession = [
        'token' => $sessionToken,
        'user_id' => $user['id'],
        'username' => $user['username'],
        'real_name' => '未设置',  // 初始值，将在第一次心跳时更新
        'device_id' => $device_id,
        'login_time' => date('Y-m-d H:i:s'),
        'last_heartbeat' => date('Y-m-d H:i:s'),
        'daily_usage' => 0
    ];
    
    if ($deviceExists) {
        // 更新现有设备的会话
        $cleanedSessions[$existingSessionIndex] = $newSession;
        logAction('login_device_reauth', $user['id'], ['device_id' => $device_id]);
    } else {
        // 添加新设备会话
        $cleanedSessions[] = $newSession;
        logAction('login_success', $user['id'], ['device_id' => $device_id]);
    }
    
    writeJsonFile(SESSIONS_FILE, $cleanedSessions);
    
    echo json_encode([
        'status' => 'success',
        'message' => $needBindDevice ? '登录成功（设备已绑定）' : '登录成功',
        'data' => [
            'token' => $sessionToken,
            'user_id' => $user['id'],
            'username' => $user['username'],
            'expire_date' => $license['expire_date'],
            'max_windows' => $license['max_windows'] ?? 1,
            'max_simulators' => $license['max_simulators'],
            'max_daily_hours' => $license['max_daily_hours'],
            'device_bound' => true,
            'device_id' => substr($device_id, 0, 16) . '...'
        ]
    ]);
}

function handleVerify() {
    $token = $_POST['token'] ?? $_GET['token'] ?? '';
    
    if (empty($token)) {
        echo json_encode(['status' => 'error', 'message' => 'Token不能为空']);
        return;
    }
    
    $sessions = readJsonFile(SESSIONS_FILE);
    $session = null;
    
    foreach ($sessions as $s) {
        if ($s['token'] === $token) {
            $session = $s;
            break;
        }
    }
    
    if (!$session) {
        echo json_encode(['status' => 'error', 'message' => '无效的Token']);
        return;
    }
    
    // 检查会话是否超时
    if ((time() - strtotime($session['last_heartbeat'])) > SESSION_TIMEOUT) {
        echo json_encode(['status' => 'error', 'message' => '会话已超时']);
        return;
    }
    
    // 检查用户授权状态
    $licenses = readJsonFile(LICENSES_FILE);
    $license = null;
    
    foreach ($licenses as $l) {
        if ($l['user_id'] === $session['user_id'] && $l['status'] === 'active') {
            $license = $l;
            break;
        }
    }
    
    if (!$license || strtotime($license['expire_date']) < time()) {
        echo json_encode(['status' => 'error', 'message' => '授权已过期']);
        return;
    }
    
    echo json_encode([
        'status' => 'success',
        'message' => '验证通过',
        'data' => [
            'user_id' => $session['user_id'],
            'username' => $session['username'],
            'expire_date' => $license['expire_date'],
            'max_windows' => $license['max_windows'] ?? 1,
            'max_simulators' => $license['max_simulators'],
            'daily_usage' => $session['daily_usage'],
            'max_daily_hours' => $license['max_daily_hours']
        ]
    ]);
}

function handleHeartbeat() {
    $token = $_POST['token'] ?? '';
    $real_name = $_POST['real_name'] ?? '未设置';
    
    if (empty($token)) {
        echo json_encode(['status' => 'error', 'message' => 'Token不能为空']);
        return;
    }
    
    $sessions = readJsonFile(SESSIONS_FILE);
    $updated = false;
    
    foreach ($sessions as &$session) {
        if ($session['token'] === $token) {
            $session['last_heartbeat'] = date('Y-m-d H:i:s');
            $session['daily_usage'] += 5; // 每次心跳增加5分钟（心跳间隔为5分钟）
            $session['real_name'] = $real_name; // 更新真实姓名
            $updated = true;
            break;
        }
    }
    
    if ($updated) {
        writeJsonFile(SESSIONS_FILE, $sessions);
        echo json_encode(['status' => 'success', 'message' => '心跳更新成功']);
    } else {
        echo json_encode(['status' => 'error', 'message' => '无效的Token']);
    }
}

function handleLogout() {
    $token = $_POST['token'] ?? '';
    
    if (empty($token)) {
        echo json_encode(['status' => 'error', 'message' => 'Token不能为空']);
        return;
    }
    
    $sessions = readJsonFile(SESSIONS_FILE);
    $newSessions = [];
    $found = false;
    
    foreach ($sessions as $session) {
        if ($session['token'] !== $token) {
            $newSessions[] = $session;
        } else {
            $found = true;
            logAction('logout', $session['user_id']);
        }
    }
    
    if ($found) {
        writeJsonFile(SESSIONS_FILE, $newSessions);
        echo json_encode(['status' => 'success', 'message' => '退出成功']);
    } else {
        echo json_encode(['status' => 'error', 'message' => '无效的Token']);
    }
}
?>
