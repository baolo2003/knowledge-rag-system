package com.example.rag.config;

import io.minio.MinioClient;
import lombok.Data;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

/**
 * MinIO 客户端配置
 *
 * <p>从 application.yml 读取 minio.* 配置，创建 MinioClient Bean。
 * 支持文件分片上传、预签名 URL 等高级特性。</p>
 *
 * @author knowledge-rag-team
 */
@Data
@Configuration
@ConfigurationProperties(prefix = "minio")
public class MinioConfig {

    /** MinIO 服务地址，如 http://localhost:9000 */
    private String endpoint;

    /** Access Key */
    private String accessKey;

    /** Secret Key */
    private String secretKey;

    /** 默认 Bucket 名称 */
    private String bucketName;

    /**
     * 创建 MinioClient Bean
     */
    @Bean
    public MinioClient minioClient() {
        return MinioClient.builder()
                .endpoint(endpoint)
                .credentials(accessKey, secretKey)
                .build();
    }
}
