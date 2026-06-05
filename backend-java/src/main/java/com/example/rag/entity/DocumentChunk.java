package com.example.rag.entity;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

import java.time.LocalDateTime;

/**
 * 文档切片表实体
 *
 * @author knowledge-rag-team
 */
@Data
@TableName("document_chunk")
public class DocumentChunk {

    @TableId(value = "id", type = IdType.AUTO)
    private Long id;

    /** 所属文档 ID */
    private Long documentId;

    /** 所属知识库 ID（冗余，加速查询） */
    private Long kbId;

    /** 切片序号（从 0 开始） */
    private Integer chunkIndex;

    /** 切片文本内容 */
    private String content;

    /** 估算 token 数 */
    private Integer tokenCount;

    /** 向量库中的唯一 ID */
    private String vectorId;

    /** 文档上传用户 ID（冗余，权限过滤用） */
    private Long ownerId;

    /** 权限范围（冗余，权限过滤用） */
    private String visibility;

    /** 组织 ID（冗余，权限过滤用） */
    private Long orgId;

    /** 创建时间 */
    private LocalDateTime createTime;
}
