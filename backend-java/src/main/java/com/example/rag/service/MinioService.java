package com.example.rag.service;

import com.example.rag.common.BusinessException;
import com.example.rag.config.MinioConfig;
import io.minio.*;
import io.minio.http.Method;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;

import java.io.InputStream;
import java.util.UUID;
import java.util.concurrent.TimeUnit;

/**
 * MinIO 文件存储服务
 *
 * <p>封装 MinIO 对象存储的上传、删除、预签名 URL 操作。
 * 文件按 "知识库ID/文档类型/UUID.扩展名" 路径组织。</p>
 *
 * @author knowledge-rag-team
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class MinioService {

    private final MinioClient minioClient;
    private final MinioConfig minioConfig;

    /** 预签名 URL 默认有效期（天） */
    private static final int DEFAULT_PRESIGNED_DAYS = 7;

    // ==================== 上传 ====================

    /**
     * 上传文件到 MinIO
     *
     * @param kbId        知识库 ID
     * @param fileType    文件类型（pdf / docx / ...）
     * @param extension   文件扩展名
     * @param inputStream 文件输入流
     * @param fileSize    文件大小（字节）
     * @param contentType 文件 MIME 类型
     * @return MinIO 存储路径（如 kb/1/pdf/a1b2c3d4.pdf）
     */
    public String upload(Long kbId, String fileType, String extension,
                         InputStream inputStream, long fileSize, String contentType) {
        ensureBucketExists();

        // 生成存储路径: {kbId}/{fileType}/{uuid}.{ext}
        String objectName = String.format("%d/%s/%s.%s",
                kbId, fileType, UUID.randomUUID().toString().replace("-", ""), extension);

        try {
            minioClient.putObject(
                    PutObjectArgs.builder()
                            .bucket(minioConfig.getBucketName())
                            .object(objectName)
                            .stream(inputStream, fileSize, -1)
                            .contentType(contentType)
                            .build()
            );
            log.info("MinIO 上传成功: bucket={}, object={}, size={}",
                    minioConfig.getBucketName(), objectName, fileSize);
        } catch (Exception e) {
            log.error("MinIO 上传失败: object={}", objectName, e);
            throw new BusinessException(500, "文件存储失败，请稍后重试");
        }

        return objectName;
    }

    // ==================== 删除 ====================

    /**
     * 从 MinIO 删除文件
     *
     * @param objectName MinIO 对象路径
     * @return true 删除成功，false 文件不存在
     */
    public boolean delete(String objectName) {
        try {
            minioClient.removeObject(
                    RemoveObjectArgs.builder()
                            .bucket(minioConfig.getBucketName())
                            .object(objectName)
                            .build()
            );
            log.info("MinIO 删除成功: bucket={}, object={}",
                    minioConfig.getBucketName(), objectName);
            return true;
        } catch (Exception e) {
            log.error("MinIO 删除失败: object={}", objectName, e);
            return false;
        }
    }

    // ==================== 预签名 URL ====================

    /**
     * 生成文件预签名下载 URL（有效期 7 天）
     *
     * @param objectName MinIO 对象路径
     * @return 预签名 URL
     */
    public String getPresignedUrl(String objectName) {
        try {
            String url = minioClient.getPresignedObjectUrl(
                    GetPresignedObjectUrlArgs.builder()
                            .bucket(minioConfig.getBucketName())
                            .object(objectName)
                            .method(Method.GET)
                            .expiry(DEFAULT_PRESIGNED_DAYS, TimeUnit.DAYS)
                            .build()
            );
            return url;
        } catch (Exception e) {
            log.error("生成预签名 URL 失败: object={}", objectName, e);
            return null;
        }
    }

    // ==================== 私有方法 ====================

    /**
     * 确保 Bucket 存在，不存在则创建
     */
    private void ensureBucketExists() {
        try {
            String bucket = minioConfig.getBucketName();
            boolean found = minioClient.bucketExists(
                    BucketExistsArgs.builder().bucket(bucket).build());
            if (!found) {
                minioClient.makeBucket(
                        MakeBucketArgs.builder().bucket(bucket).build());
                log.info("MinIO Bucket 已创建: {}", bucket);
            }
        } catch (Exception e) {
            log.error("MinIO Bucket 初始化失败", e);
            throw new BusinessException(500, "存储服务初始化失败，请稍后重试");
        }
    }
}
