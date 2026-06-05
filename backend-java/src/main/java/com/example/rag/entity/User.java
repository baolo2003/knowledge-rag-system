package com.example.rag.entity;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

import java.time.LocalDateTime;

/**
 * 用户表实体
 *
 * @author knowledge-rag-team
 */
@Data
@TableName("`user`")
public class User {

    @TableId(value = "id", type = IdType.AUTO)
    private Long id;

    /** 用户名（登录用） */
    private String username;

    /** BCrypt 加密密码 */
    private String password;

    /** 邮箱 */
    private String email;

    /** 角色：USER / ADMIN */
    private String role;

    /** 所属组织 ID */
    private Long orgId;

    /** 状态：1启用 0禁用 */
    private Integer status;

    /** 创建时间 */
    private LocalDateTime createTime;

    /** 更新时间 */
    private LocalDateTime updateTime;
}
