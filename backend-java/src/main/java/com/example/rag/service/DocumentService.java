package com.example.rag.service;

import com.example.rag.dto.response.DocumentResponse;
import com.example.rag.dto.response.PageResponse;
import org.springframework.web.multipart.MultipartFile;

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
     * 分页列出知识库下的文档（权限过滤 + 文件名搜索）
     *
     * @param kbId    知识库 ID
     * @param page    页码（从 1 开始）
     * @param size    每页条数
     * @param keyword 文件名搜索关键词（可选，模糊匹配）
     * @return 分页结果
     */
    PageResponse<DocumentResponse> listByKb(Long kbId, int page, int size, String keyword);

    /**
     * 获取文档详情（含 chunk_count + 预签名下载 URL）
     */
    DocumentResponse getById(Long docId);

    /**
     * 删除文档（权限校验 + 软删除 + Redis 缓存失效 + 异步清理 MinIO/切片/向量）
     */
    void delete(Long docId);

    /**
     * 重新解析文档
     * <p>重置 parse_status 为 PENDING，重新异步调用 Python 解析接口</p>
     */
    DocumentResponse reparse(Long docId);
}
