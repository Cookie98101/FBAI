<?php
/**
 * 数据库配置文件
 */

class Database {
    private $host = "localhost";
    private $db_name = "facebook_auth";
    private $username = "root";
    private $password = "";
    private $conn;

    public function getConnection() {
        $this->conn = null;
        
        try {
            $this->conn = new PDO(
                "mysql:host=" . $this->host . ";dbname=" . $this->db_name . ";charset=utf8",
                $this->username,
                $this->password
            );
            $this->conn->setAttribute(PDO::ATTR_ERRMODE, PDO::ERRMODE_EXCEPTION);
        } catch(PDOException $exception) {
            echo "连接失败: " . $exception->getMessage();
        }
        
        return $this->conn;
    }
}
?>
