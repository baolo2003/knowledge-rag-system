-- =============================================
-- Knowledge RAG System - Database Initialization
-- Chapter 5: Database Design (7 tables)
-- Engine: InnoDB, Charset: utf8mb4
-- =============================================

CREATE DATABASE IF NOT EXISTS `knowledge_rag`
  DEFAULT CHARACTER SET utf8mb4
  DEFAULT COLLATE utf8mb4_unicode_ci;

USE `knowledge_rag`;

-- ----------------------------
-- 1. organization (组织表)
-- ----------------------------
DROP TABLE IF EXISTS `organization`;
CREATE TABLE `organization` (
    `id`            BIGINT       NOT NULL AUTO_INCREMENT  COMMENT '主键',
    `name`          VARCHAR(100) NOT NULL                 COMMENT '组织名称',
    `parent_id`     BIGINT       DEFAULT NULL             COMMENT '父级组织 ID（树形结构）',
    `description`   VARCHAR(500) DEFAULT NULL             COMMENT '组织描述',
    `create_time`   DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `update_time`   DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    PRIMARY KEY (`id`),
    KEY `idx_parent_id` (`parent_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='组织表';

-- ----------------------------
-- 2. user (用户表)
-- ----------------------------
DROP TABLE IF EXISTS `user`;
CREATE TABLE `user` (
    `id`            BIGINT       NOT NULL AUTO_INCREMENT  COMMENT '主键',
    `username`      VARCHAR(50)  NOT NULL                 COMMENT '用户名（登录用）',
    `password`      VARCHAR(255) NOT NULL                 COMMENT 'BCrypt 加密密码',
    `email`         VARCHAR(100) DEFAULT NULL             COMMENT '邮箱',
    `role`          VARCHAR(20)  NOT NULL DEFAULT 'USER'  COMMENT '角色：USER / ADMIN',
    `org_id`        BIGINT       DEFAULT NULL             COMMENT '所属组织 ID',
    `status`        TINYINT      NOT NULL DEFAULT 1       COMMENT '状态：1启用 0禁用',
    `create_time`   DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `update_time`   DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_username` (`username`),
    KEY `idx_org_id` (`org_id`),
    KEY `idx_create_time` (`create_time`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户表';

-- ----------------------------
-- 3. knowledge_base (知识库表)
-- ----------------------------
DROP TABLE IF EXISTS `knowledge_base`;
CREATE TABLE `knowledge_base` (
    `id`            BIGINT       NOT NULL AUTO_INCREMENT  COMMENT '主键',
    `name`          VARCHAR(200) NOT NULL                 COMMENT '知识库名称',
    `description`   VARCHAR(1000) DEFAULT NULL            COMMENT '知识库描述',
    `owner_id`      BIGINT       NOT NULL                 COMMENT '创建人用户 ID',
    `visibility`    VARCHAR(20)  NOT NULL DEFAULT 'PRIVATE' COMMENT '可见范围：PRIVATE / PUBLIC / ORG',
    `org_id`        BIGINT       DEFAULT NULL             COMMENT '所属组织 ID（ORG 可见时必填）',
    `is_deleted`    TINYINT      NOT NULL DEFAULT 0       COMMENT '软删除：0正常 1已删除',
    `create_time`   DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `update_time`   DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    PRIMARY KEY (`id`),
    KEY `idx_owner_id` (`owner_id`),
    KEY `idx_org_id` (`org_id`),
    KEY `idx_visibility` (`visibility`),
    KEY `idx_is_deleted` (`is_deleted`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='知识库表';

-- ----------------------------
-- 4. document (文档表)
-- ----------------------------
DROP TABLE IF EXISTS `document`;
CREATE TABLE `document` (
    `id`            BIGINT       NOT NULL AUTO_INCREMENT  COMMENT '主键',
    `kb_id`         BIGINT       NOT NULL                 COMMENT '所属知识库 ID',
    `file_md5`      VARCHAR(64)  NOT NULL                 COMMENT '文件 MD5（用于去重）',
    `file_name`     VARCHAR(500) NOT NULL                 COMMENT '原始文件名',
    `file_type`     VARCHAR(20)  NOT NULL                 COMMENT '文件类型：pdf / docx / xlsx / md / txt',
    `file_size`     BIGINT       NOT NULL                 COMMENT '文件大小（字节）',
    `minio_path`    VARCHAR(500) NOT NULL                 COMMENT 'MinIO 存储路径',
    `parse_status`  VARCHAR(20)  NOT NULL DEFAULT 'PENDING' COMMENT '解析状态：PENDING / PARSING / SUCCESS / FAILED',
    `parse_fail_msg` VARCHAR(500) DEFAULT NULL            COMMENT '解析失败原因',
    `owner_id`      BIGINT       NOT NULL                 COMMENT '上传用户 ID',
    `visibility`    VARCHAR(20)  NOT NULL DEFAULT 'PRIVATE' COMMENT '权限范围：PRIVATE / PUBLIC / ORG',
    `org_id`        BIGINT       DEFAULT NULL             COMMENT '组织 ID（ORG 可见时必填）',
    `is_deleted`    TINYINT      NOT NULL DEFAULT 0       COMMENT '软删除：0正常 1已删除',
    `chunk_count`   INT          DEFAULT 0                COMMENT '切片数量',
    `create_time`   DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `update_time`   DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    PRIMARY KEY (`id`),
    KEY `idx_kb_id` (`kb_id`),
    KEY `idx_file_md5` (`file_md5`),
    KEY `idx_owner_id` (`owner_id`),
    KEY `idx_org_id` (`org_id`),
    KEY `idx_parse_status` (`parse_status`),
    KEY `idx_is_deleted` (`is_deleted`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='文档表';

-- ----------------------------
-- 5. document_chunk (文档切片表)
-- ----------------------------
DROP TABLE IF EXISTS `document_chunk`;
CREATE TABLE `document_chunk` (
    `id`            BIGINT       NOT NULL AUTO_INCREMENT  COMMENT '主键',
    `document_id`   BIGINT       NOT NULL                 COMMENT '所属文档 ID',
    `kb_id`         BIGINT       NOT NULL                 COMMENT '所属知识库 ID（冗余，加速查询）',
    `chunk_index`   INT          NOT NULL                 COMMENT '切片序号（从 0 开始）',
    `content`       MEDIUMTEXT   NOT NULL                 COMMENT '切片文本内容',
    `token_count`   INT          DEFAULT 0                COMMENT '估算 token 数',
    `vector_id`     VARCHAR(100) DEFAULT NULL             COMMENT '向量库中的唯一 ID',
    `owner_id`      BIGINT       NOT NULL                 COMMENT '文档上传用户 ID（冗余，权限过滤用）',
    `visibility`    VARCHAR(20)  NOT NULL                 COMMENT '权限范围（冗余，权限过滤用）',
    `org_id`        BIGINT       DEFAULT NULL             COMMENT '组织 ID（冗余，权限过滤用）',
    `create_time`   DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    PRIMARY KEY (`id`),
    KEY `idx_document_id` (`document_id`),
    KEY `idx_kb_id` (`kb_id`),
    KEY `idx_vector_id` (`vector_id`),
    KEY `idx_owner_id` (`owner_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='文档切片表';

-- ----------------------------
-- 6. conversation (会话表)
-- ----------------------------
DROP TABLE IF EXISTS `conversation`;
CREATE TABLE `conversation` (
    `id`            BIGINT       NOT NULL AUTO_INCREMENT  COMMENT '主键',
    `user_id`       BIGINT       NOT NULL                 COMMENT '用户 ID',
    `kb_id`         BIGINT       DEFAULT NULL             COMMENT '关联知识库 ID（可选）',
    `title`         VARCHAR(200) DEFAULT '新对话'          COMMENT '会话标题',
    `is_deleted`    TINYINT      NOT NULL DEFAULT 0       COMMENT '软删除',
    `create_time`   DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `update_time`   DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    PRIMARY KEY (`id`),
    KEY `idx_user_id` (`user_id`),
    KEY `idx_update_time` (`update_time`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='会话表';

-- ----------------------------
-- 7. message (消息表)
-- ----------------------------
DROP TABLE IF EXISTS `message`;
CREATE TABLE `message` (
    `id`              BIGINT     NOT NULL AUTO_INCREMENT  COMMENT '主键',
    `conversation_id` BIGINT     NOT NULL                 COMMENT '会话 ID',
    `role`            VARCHAR(20) NOT NULL                COMMENT '角色：user / assistant',
    `content`         MEDIUMTEXT NOT NULL                 COMMENT '消息内容',
    `references_json` TEXT       DEFAULT NULL             COMMENT '引用来源 JSON',
    `token_usage`     INT        DEFAULT 0                COMMENT '本次消耗 token 数',
    `create_time`     DATETIME   NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    PRIMARY KEY (`id`),
    KEY `idx_conversation_id` (`conversation_id`),
    KEY `idx_create_time` (`create_time`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='消息表';

-- ----------------------------
-- Seed: default admin (password: admin123)
-- ----------------------------
INSERT IGNORE INTO `user` (`username`, `password`, `email`, `role`, `status`)
VALUES ('admin', '$2a$10$N.zmdr9k7uOCQb376NoUnuTJ8iAt6Z5EHsM8lE9lBOsl7iKdS5eH8q',
        'admin@example.com', 'ADMIN', 1);
