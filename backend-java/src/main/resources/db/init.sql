-- =============================================
-- Knowledge RAG System - Database Initialization
-- =============================================

CREATE DATABASE IF NOT EXISTS `knowledge_rag`
  DEFAULT CHARACTER SET utf8mb4
  DEFAULT COLLATE utf8mb4_unicode_ci;

USE `knowledge_rag`;

-- ----------------------------
-- User table
-- ----------------------------
CREATE TABLE IF NOT EXISTS `sys_user` (
    `id`            BIGINT       NOT NULL AUTO_INCREMENT COMMENT 'Primary key',
    `username`      VARCHAR(64)  NOT NULL COMMENT 'Username',
    `password`      VARCHAR(256) NOT NULL COMMENT 'Encrypted password',
    `nickname`      VARCHAR(64)  DEFAULT NULL COMMENT 'Nickname',
    `email`         VARCHAR(128) DEFAULT NULL COMMENT 'Email',
    `phone`         VARCHAR(20)  DEFAULT NULL COMMENT 'Phone number',
    `avatar`        VARCHAR(512) DEFAULT NULL COMMENT 'Avatar URL',
    `status`        TINYINT      NOT NULL DEFAULT 1 COMMENT 'Status: 0=disabled, 1=enabled',
    `role`          VARCHAR(32)  NOT NULL DEFAULT 'USER' COMMENT 'Role: USER, ADMIN',
    `created_at`    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT 'Created time',
    `updated_at`    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT 'Updated time',
    `deleted`       TINYINT      NOT NULL DEFAULT 0 COMMENT 'Logical delete: 0=normal, 1=deleted',
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_username` (`username`),
    KEY `idx_status` (`status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='System user table';

-- ----------------------------
-- Knowledge base table
-- ----------------------------
CREATE TABLE IF NOT EXISTS `kb_document` (
    `id`            BIGINT       NOT NULL AUTO_INCREMENT COMMENT 'Primary key',
    `title`         VARCHAR(256) NOT NULL COMMENT 'Document title',
    `file_name`     VARCHAR(256) NOT NULL COMMENT 'Original file name',
    `file_type`     VARCHAR(32)  NOT NULL COMMENT 'File type: pdf, docx, xlsx, txt, md',
    `file_size`     BIGINT       NOT NULL DEFAULT 0 COMMENT 'File size (bytes)',
    `file_path`     VARCHAR(512) NOT NULL COMMENT 'MinIO object path',
    `file_hash`     VARCHAR(128) DEFAULT NULL COMMENT 'File SHA-256 hash',
    `status`        VARCHAR(32)  NOT NULL DEFAULT 'UPLOADED' COMMENT 'Status: UPLOADED, PARSING, PARSED, FAILED',
    `chunk_count`   INT          NOT NULL DEFAULT 0 COMMENT 'Number of chunks',
    `uploader_id`   BIGINT       DEFAULT NULL COMMENT 'Uploader user ID',
    `uploader_name` VARCHAR(64)  DEFAULT NULL COMMENT 'Uploader username',
    `created_at`    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT 'Created time',
    `updated_at`    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT 'Updated time',
    `deleted`       TINYINT      NOT NULL DEFAULT 0 COMMENT 'Logical delete',
    PRIMARY KEY (`id`),
    KEY `idx_status` (`status`),
    KEY `idx_uploader_id` (`uploader_id`),
    KEY `idx_created_at` (`created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Knowledge base document table';

-- ----------------------------
-- Q&A conversation table
-- ----------------------------
CREATE TABLE IF NOT EXISTS `qa_conversation` (
    `id`            BIGINT       NOT NULL AUTO_INCREMENT COMMENT 'Primary key',
    `user_id`       BIGINT       NOT NULL COMMENT 'User ID',
    `title`         VARCHAR(256) DEFAULT NULL COMMENT 'Conversation title',
    `status`        TINYINT      NOT NULL DEFAULT 1 COMMENT 'Status: 0=archived, 1=active',
    `message_count` INT          NOT NULL DEFAULT 0 COMMENT 'Total messages in this conversation',
    `created_at`    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT 'Created time',
    `updated_at`    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT 'Updated time',
    `deleted`       TINYINT      NOT NULL DEFAULT 0 COMMENT 'Logical delete',
    PRIMARY KEY (`id`),
    KEY `idx_user_id` (`user_id`),
    KEY `idx_created_at` (`created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Q&A conversation table';

-- ----------------------------
-- Q&A message table
-- ----------------------------
CREATE TABLE IF NOT EXISTS `qa_message` (
    `id`              BIGINT        NOT NULL AUTO_INCREMENT COMMENT 'Primary key',
    `conversation_id` BIGINT        NOT NULL COMMENT 'Conversation ID',
    `role`            VARCHAR(16)   NOT NULL COMMENT 'Role: user, assistant',
    `content`         TEXT          NOT NULL COMMENT 'Message content',
    `sources`         JSON          DEFAULT NULL COMMENT 'Referenced document sources (JSON array)',
    `rating`          TINYINT       DEFAULT NULL COMMENT 'User rating: 0=thumbs-down, 1=thumbs-up',
    `created_at`      DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT 'Created time',
    PRIMARY KEY (`id`),
    KEY `idx_conversation_id` (`conversation_id`),
    KEY `idx_created_at` (`created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Q&A message table';

-- ----------------------------
-- Insert default admin user (password: admin123)
-- BCrypt encoded: $2a$10$N.zmdr9k7uOCQb376NoUnuTJ8iAt6Z5EHsM8lE9lBOsl7iAt6Z5Eh
-- ----------------------------
INSERT IGNORE INTO `sys_user` (`username`, `password`, `nickname`, `role`, `status`)
VALUES ('admin', '$2a$10$N.zmdr9k7uOCQb376NoUnuTJ8iAt6Z5EHsM8lE9lBOsl7iKdS5eH8q',
        'System Admin', 'ADMIN', 1);
