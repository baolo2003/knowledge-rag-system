package com.example.rag.entity;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableLogic;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

import java.time.LocalDateTime;

/**
 * 知识库表实体
 *
 * @author knowledge-rag-team
 */
@Data
@TableName("knowledge_base")
public class KnowledgeBase {

    @TableId(value = "id", type = IdType.AUTO)
    private Long id;

    /** 知识库名称 */
    private String name;

    /** 知识库描述 */
    private String description;

    /** 创建人用户 ID */
    private Long ownerId;

    /** 可见范围：PRIVATE / PUBLIC / ORG */
    private String visibility;

    /** 所属组织 ID（ORG 可见时必填） */
    private Long orgId;

    /** 软删除：0正常 1已删除 */
    @TableLogic
    private Integer isDeleted;

    /** 创建时间 */
    private LocalDateTime createTime;

    /** 更新时间 */
    private LocalDateTime updateTime;
}
