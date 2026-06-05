package com.example.rag.dto.response;

import com.example.rag.entity.User;
import lombok.Builder;
import lombok.Data;

import java.time.LocalDateTime;

/**
 * 用户信息响应 DTO
 *
 * @author knowledge-rag-team
 */
@Data
@Builder
public class UserResponse {

    private Long id;
    private String username;
    private String email;
    private String role;
    private Long orgId;
    private Integer status;
    private LocalDateTime createTime;

    /** 从 Entity 转换 */
    public static UserResponse from(User user) {
        return UserResponse.builder()
                .id(user.getId())
                .username(user.getUsername())
                .email(user.getEmail())
                .role(user.getRole())
                .orgId(user.getOrgId())
                .status(user.getStatus())
                .createTime(user.getCreateTime())
                .build();
    }
}
