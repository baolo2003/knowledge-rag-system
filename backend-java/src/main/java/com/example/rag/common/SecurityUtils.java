package com.example.rag.common;

import org.springframework.security.core.Authentication;
import org.springframework.security.core.GrantedAuthority;
import org.springframework.security.core.context.SecurityContextHolder;

import java.util.List;
import java.util.Optional;

/**
 * Security 工具类
 *
 * <p>从 {@link SecurityContextHolder} 中获取当前登录用户信息。
 * 前提：JwtAuthenticationFilter 已将用户信息写入 SecurityContext。</p>
 *
 * <p>典型 JWT Payload 结构：
 * <pre>
 * {
 *   "sub": "1",           // user_id
 *   "username": "zhangsan",
 *   "role": "USER",
 *   "org_id": 10
 * }
 * </pre>
 *
 * @author knowledge-rag-team
 */
public final class SecurityUtils {

    private SecurityUtils() {
        // 工具类禁止实例化
    }

    /** 获取当前登录用户 ID */
    public static Long getCurrentUserId() {
        return getAuthentication()
                .map(auth -> Long.parseLong(auth.getName()))
                .orElse(null);
    }

    /** 获取当前登录用户名 */
    public static String getCurrentUsername() {
        return getAuthentication()
                .map(auth -> (String) auth.getDetails())
                .orElse(null);
    }

    /** 获取当前用户角色（不含 ROLE_ 前缀） */
    public static String getCurrentUserRole() {
        return getAuthentication()
                .map(auth -> {
                    List<String> roles = auth.getAuthorities().stream()
                            .map(GrantedAuthority::getAuthority)
                            .toList();
                    // authority 格式为 "ROLE_ADMIN"，去掉前缀
                    return roles.stream()
                            .filter(r -> r.startsWith("ROLE_"))
                            .map(r -> r.substring(5))   // "ROLE_ADMIN" → "ADMIN"
                            .findFirst()
                            .orElse("USER");
                })
                .orElse(null);
    }

    /** 获取当前用户所属组织 ID */
    public static Long getCurrentUserOrgId() {
        return getAuthentication()
                .map(auth -> {
                    // org_id 存储在 credentials 中（JWT Filter 写入）
                    Object credentials = auth.getCredentials();
                    if (credentials instanceof Long) {
                        return (Long) credentials;
                    }
                    return null;
                })
                .orElse(null);
    }

    /** 判断当前用户是否为 ADMIN */
    public static boolean isAdmin() {
        return "ADMIN".equals(getCurrentUserRole());
    }

    /** 判断当前用户是否已登录 */
    public static boolean isAuthenticated() {
        Authentication auth = SecurityContextHolder.getContext().getAuthentication();
        return auth != null && auth.isAuthenticated()
                && !"anonymousUser".equals(auth.getPrincipal());
    }

    // ==================== 私有方法 ====================

    private static Optional<Authentication> getAuthentication() {
        return Optional.ofNullable(SecurityContextHolder.getContext().getAuthentication());
    }
}
