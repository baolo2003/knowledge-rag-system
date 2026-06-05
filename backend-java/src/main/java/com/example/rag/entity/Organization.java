package com.example.rag.entity;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

import java.time.LocalDateTime;

/**
 * 组织表实体
 *
 * @author knowledge-rag-team
 */
@Data
@TableName("organization")
public class Organization {

    @TableId(value = "id", type = IdType.AUTO)
    private Long id;

    /** 组织名称 */
    private String name;

    /** 父级组织 ID（树形结构） */
    private Long parentId;

    /** 组织描述 */
    private String description;

    /** 创建时间 */
    private LocalDateTime createTime;

    /** 更新时间 */
    private LocalDateTime updateTime;
}
