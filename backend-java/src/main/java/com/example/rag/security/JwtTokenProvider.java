package com.example.rag.security;

import io.jsonwebtoken.Claims;
import io.jsonwebtoken.JwtException;
import io.jsonwebtoken.Jwts;
import io.jsonwebtoken.security.Keys;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

import javax.crypto.SecretKey;
import java.nio.charset.StandardCharsets;
import java.util.Date;

/**
 * JWT Token 工具类 —— 生成 & 校验
 *
 * <p>Token Payload 结构：
 * <pre>
 * {
 *   "sub": "1",           // user_id
 *   "username": "zhangsan",
 *   "role": "USER",
 *   "org_id": 10,
 *   "iat": 1717580000,    // 签发时间
 *   "exp": 1717587200     // 过期时间
 * }
 * </pre>
 *
 * @author knowledge-rag-team
 */
@Component
public class JwtTokenProvider {

    @Value("${jwt.secret}")
    private String secret;

    @Value("${jwt.access-token-expire}")
    private long accessTokenExpire;       // 秒

    @Value("${jwt.refresh-token-expire}")
    private long refreshTokenExpire;      // 秒

    // ==================== 生成 Token ====================

    /**
     * 生成 Access Token（有效期 2 小时）
     */
    public String createAccessToken(Long userId, String username, String role, Long orgId) {
        return buildToken(userId, username, role, orgId, accessTokenExpire);
    }

    /**
     * 生成 Refresh Token（有效期 7 天）
     */
    public String createRefreshToken(Long userId, String username, String role, Long orgId) {
        return buildToken(userId, username, role, orgId, refreshTokenExpire);
    }

    private String buildToken(Long userId, String username, String role, Long orgId, long expireSeconds) {
        Date now = new Date();
        Date expiry = new Date(now.getTime() + expireSeconds * 1000);

        return Jwts.builder()
                .subject(String.valueOf(userId))
                .claim("username", username)
                .claim("role", role)
                .claim("org_id", orgId)
                .issuedAt(now)
                .expiration(expiry)
                .signWith(getSigningKey())
                .compact();
    }

    // ==================== 解析 Token ====================

    /** 从 Token 中提取 userId */
    public Long getUserId(String token) {
        return Long.parseLong(getClaims(token).getSubject());
    }

    /** 从 Token 中提取 username */
    public String getUsername(String token) {
        return getClaims(token).get("username", String.class);
    }

    /** 从 Token 中提取 role */
    public String getRole(String token) {
        return getClaims(token).get("role", String.class);
    }

    /** 从 Token 中提取 orgId */
    public Long getOrgId(String token) {
        Object orgId = getClaims(token).get("org_id");
        if (orgId instanceof Integer) {
            return ((Integer) orgId).longValue();
        }
        return (Long) orgId;
    }

    // ==================== 校验 Token ====================

    /** 校验 Token 是否合法（签名正确 + 未过期） */
    public boolean validateToken(String token) {
        try {
            Jwts.parser()
                    .verifyWith(getSigningKey())
                    .build()
                    .parseSignedClaims(token);
            return true;
        } catch (JwtException | IllegalArgumentException e) {
            return false;
        }
    }

    // ==================== 内部方法 ====================

    private Claims getClaims(String token) {
        return Jwts.parser()
                .verifyWith(getSigningKey())
                .build()
                .parseSignedClaims(token)
                .getPayload();
    }

    private SecretKey getSigningKey() {
        return Keys.hmacShaKeyFor(secret.getBytes(StandardCharsets.UTF_8));
    }
}
