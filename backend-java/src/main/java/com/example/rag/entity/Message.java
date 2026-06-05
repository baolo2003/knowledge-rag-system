package com.example.rag.entity;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

import java.time.LocalDateTime;

/**
 * 消息表实体
 *
 * @author knowledge-rag-team
 */
@Data
@TableName("message")
public class Message {

    @TableId(value = "id", type = IdType.AUTO)
    private Long id;

    /** 会话 ID */
    private Long conversationId;

    /** 角色：user / assistant */
    private String role;

    /** 消息内容 */
    private String content;

    /** 引用来源 JSON */
    private String referencesJson;

    /** 本次消耗 token 数 */
    private Integer tokenUsage;

    /** 创建时间 */
    private LocalDateTime createTime;
}
