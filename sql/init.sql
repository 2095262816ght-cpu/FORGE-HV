-- FORGE-HV MySQL 初始化脚本
-- 用法: mysql -u root -p < sql/init.sql

CREATE DATABASE IF NOT EXISTS forge_hv DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE forge_hv;

-- 用户表
CREATE TABLE IF NOT EXISTS users (
    id          BIGINT AUTO_INCREMENT PRIMARY KEY,
    username    VARCHAR(64)  NOT NULL UNIQUE,
    password_hash VARCHAR(128) NOT NULL,
    salt        VARCHAR(64)  NOT NULL,
    role        VARCHAR(16)  NOT NULL DEFAULT 'user',
    display_name VARCHAR(64),
    email       VARCHAR(128),
    created_at  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_login  DATETIME     NULL,
    INDEX idx_users_username (username)
) ENGINE=InnoDB;

-- 训练历史记录表
CREATE TABLE IF NOT EXISTS history (
    id           BIGINT AUTO_INCREMENT PRIMARY KEY,
    user_id      BIGINT       NULL,
    username     VARCHAR(64)  NULL,
    task_type    VARCHAR(64)  NULL,
    algorithm    VARCHAR(64)  NULL,
    data_source  VARCHAR(64)  NULL,
    metrics      JSON         NULL,
    params       JSON         NULL,
    n_samples    INT          NULL,
    duration_sec DOUBLE       NULL,
    status       VARCHAR(32)  NULL,
    created_at   DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_history_user (user_id),
    INDEX idx_history_created (created_at),
    CONSTRAINT fk_history_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
) ENGINE=InnoDB;

-- 系统设置表 (key-value)
CREATE TABLE IF NOT EXISTS settings (
    setting_key VARCHAR(64) PRIMARY KEY,
    setting_value TEXT,
    updated_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    updated_by  VARCHAR(64) NULL
) ENGINE=InnoDB;

-- 默认管理员由 Spring Boot DataInitializer 以 BCrypt 创建（admin / admin123）
-- 若仅执行本 SQL、未启动后端，可临时用旧哈希；首次登录后会自动升级为 BCrypt
INSERT INTO users (username, password_hash, salt, role, display_name, email)
SELECT 'admin',
       SHA2(CONCAT('forge2026salt0001', 'admin123'), 256),
       'forge2026salt0001',
       'admin', 'Admin', 'admin@forge.local'
WHERE NOT EXISTS (SELECT 1 FROM users WHERE username = 'admin');

-- 默认系统设置
INSERT INTO settings (setting_key, setting_value, updated_by) VALUES
('site_title', 'FORGE 高温合金机器学习实验台', 'system'),
('default_data_source', 'real', 'system'),
('allow_guest_browse', 'false', 'system'),
('allow_register', 'true', 'system'),
('default_register_role', 'user', 'system'),
('max_upload_size_mb', '50', 'system'),
('history_retention_days', '365', 'system')
ON DUPLICATE KEY UPDATE setting_value = VALUES(setting_value);
