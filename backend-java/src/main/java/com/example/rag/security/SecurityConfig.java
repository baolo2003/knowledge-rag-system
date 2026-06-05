package com.example.rag.security;

import lombok.RequiredArgsConstructor;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.http.HttpMethod;
import org.springframework.security.authentication.AuthenticationManager;
import org.springframework.security.config.annotation.authentication.configuration.AuthenticationConfiguration;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.config.annotation.web.configuration.EnableWebSecurity;
import org.springframework.security.config.annotation.web.configurers.AbstractHttpConfigurer;
import org.springframework.security.config.http.SessionCreationPolicy;
import org.springframework.security.crypto.bcrypt.BCryptPasswordEncoder;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.security.web.SecurityFilterChain;
import org.springframework.security.web.authentication.UsernamePasswordAuthenticationFilter;

/**
 * Spring Security 配置
 *
 * <p>策略：无状态 Session + JWT Token 鉴权。</p>
 * <ul>
 *   <li>/api/auth/** 放行（注册 / 登录）</li>
 *   <li>其余 /api/** 需认证</li>
 *   <li>禁用 CSRF、无状态 Session</li>
 * </ul>
 *
 * @author knowledge-rag-team
 */
@Configuration
@EnableWebSecurity
@RequiredArgsConstructor
public class SecurityConfig {

    private final JwtAuthenticationFilter jwtAuthenticationFilter;

    @Bean
    public SecurityFilterChain securityFilterChain(HttpSecurity http) throws Exception {
        http
                // 禁用 CSRF（API 无状态 + JWT 天然防 CSRF）
                .csrf(AbstractHttpConfigurer::disable)

                // 无状态 Session
                .sessionManagement(session ->
                        session.sessionCreationPolicy(SessionCreationPolicy.STATELESS))

                // 权限配置
                .authorizeHttpRequests(auth -> auth
                        // 放行注册 / 登录
                        .requestMatchers("/api/auth/register", "/api/auth/login").permitAll()
                        // 放行 OPTIONS 预检请求（跨域用）
                        .requestMatchers(HttpMethod.OPTIONS, "/**").permitAll()
                        // 其余 /api/** 需要认证
                        .requestMatchers("/api/**").authenticated()
                        // 其他请求放行（如静态资源、Swagger）
                        .anyRequest().permitAll()
                )

                // 注册 JWT 过滤器（在 UsernamePasswordAuthenticationFilter 之前）
                .addFilterBefore(jwtAuthenticationFilter, UsernamePasswordAuthenticationFilter.class);

        return http.build();
    }

    @Bean
    public PasswordEncoder passwordEncoder() {
        return new BCryptPasswordEncoder();
    }

    @Bean
    public AuthenticationManager authenticationManager(AuthenticationConfiguration config)
            throws Exception {
        return config.getAuthenticationManager();
    }
}
