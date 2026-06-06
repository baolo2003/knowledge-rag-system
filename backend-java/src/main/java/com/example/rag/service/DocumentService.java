package com.example.rag.service;

import com.example.rag.dto.response.DocumentResponse;
import org.springframework.web.multipart.MultipartFile;

import java.util.List;

/**
 * 文档服务接口
 *
 * @author knowledge-rag-team
 */
public interface DocumentService {

    /**
     * 上传文档
     * <p>流程：校验 → MD5 去重 → MinIO 上传 → MySQL 保存 → 异步触发解析</p>
     */
    DocumentResponse upload(MultipartFile file, Long kbId, String visibility, Long orgId);

    /**
     * 列出知识库下的文档（权限过滤）
     */
    List<DocumentResponse> listByKb(Long kbId);

    /**
     * 获取文档详情
     */
    DocumentResponse getById(Long docId);

    /**
     * 删除文档（软删除 + 异步清理 MinIO 和切片）
     */
    void delete(Long docId);

    /**
     * 重新解析文档
     * <p>将 parse_status 重置为 PENDING，重新触发异步解析</p>
     */
    DocumentResponse reparse(Long docId);
}
