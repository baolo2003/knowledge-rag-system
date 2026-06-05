package com.example.rag.entity;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableLogic;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

import java.time.LocalDateTime;

/**
 * 会话表实体
 *
 * @author knowledge-rag-team
 */
@Data
@TableName("conversation")
public class Conversation {

    @TableId(value = "id", type = IdType.AUTO)
    private Long id;

    /** 用户 ID */
    private Long userId;

    /** 关联知识库 ID（可选） */
    private Long kbId;

    /** 会话标题 */
    private String title;

    /** 软删除 */
    @TableLogic
    private Integer isDeleted;

    /** 创建时间 */
    private LocalDateTime createTime;

    /** 更新时间 */
    private LocalDateTime updateTime;
}
