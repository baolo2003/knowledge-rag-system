package com.example.rag.dto.response;

import lombok.Builder;
import lombok.Data;

/**
 * 登录响应 DTO
 *
 * @author knowledge-rag-team
 */
@Data
@Builder
public class LoginResponse {

    /** JWT Access Token（有效期 2 小时） */
    private String accessToken;

    /** JWT Refresh Token（有效期 7 天） */
    private String refreshToken;

    /** Token 类型，固定为 Bearer */
    private String tokenType;

    /** Access Token 过期时间（秒） */
    private long expiresIn;

    /** 登录用户信息 */
    private UserResponse user;

    /** 快捷构造 */
    public static LoginResponse of(String accessToken, String refreshToken,
                                   long expiresIn, UserResponse user) {
        return LoginResponse.builder()
                .accessToken(accessToken)
                .refreshToken(refreshToken)
                .tokenType("Bearer")
                .expiresIn(expiresIn)
                .user(user)
                .build();
    }
}
