package com.example.rag.common;

import org.springframework.context.annotation.Configuration;
import org.springframework.web.servlet.config.annotation.CorsRegistry;
import org.springframework.web.servlet.config.annotation.WebMvcConfigurer;

/**
 * 跨域配置
 *
 * <p>开发阶段允许所有来源访问，生产环境应收紧 allowedOrigins。</p>
 *
 * @author knowledge-rag-team
 */
@Configuration
public class WebConfig implements WebMvcConfigurer {

    @Override
    public void addCorsMappings(CorsRegistry registry) {
        registry.addMapping("/**")                          // 所有接口
                .allowedOriginPatterns("*")                 // 允许所有来源（开发用）
                .allowedMethods("GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH")
                .allowedHeaders("*")                        // 允许所有请求头
                .exposedHeaders("Authorization")            // 前端可读取 Authorization 头
                .allowCredentials(true)                     // 允许携带 Cookie
                .maxAge(3600);                              // 预检请求缓存 1 小时
    }
}
