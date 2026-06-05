package com.example.rag.entity;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableLogic;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

import java.time.LocalDateTime;

/**
 * 文档表实体
 *
 * @author knowledge-rag-team
 */
@Data
@TableName("document")
public class Document {

    @TableId(value = "id", type = IdType.AUTO)
    private Long id;

    /** 所属知识库 ID */
    private Long kbId;

    /** 文件 MD5（用于去重） */
    private String fileMd5;

    /** 原始文件名 */
    private String fileName;

    /** 文件类型：pdf / docx / xlsx / md / txt */
    private String fileType;

    /** 文件大小（字节） */
    private Long fileSize;

    /** MinIO 存储路径 */
    private String minioPath;

    /** 解析状态：PENDING / PARSING / SUCCESS / FAILED */
    private String parseStatus;

    /** 解析失败原因 */
    private String parseFailMsg;

    /** 上传用户 ID */
    private Long ownerId;

    /** 权限范围：PRIVATE / PUBLIC / ORG */
    private String visibility;

    /** 组织 ID（ORG 可见时必填） */
    private Long orgId;

    /** 软删除：0正常 1已删除 */
    @TableLogic
    private Integer isDeleted;

    /** 切片数量 */
    private Integer chunkCount;

    /** 创建时间 */
    private LocalDateTime createTime;

    /** 更新时间 */
    private LocalDateTime updateTime;
}
