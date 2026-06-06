package com.example.rag.service;

import com.example.rag.entity.Document;
import com.example.rag.mapper.DocumentMapper;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.scheduling.annotation.Async;
import org.springframework.stereotype.Service;
import org.springframework.web.client.RestTemplate;

import java.time.LocalDateTime;
import java.util.Map;

/**
 * 文档解析服务（异步）
 *
 * <p>异步调用 Python AI 服务进行文档处理：
 * <ul>
 *   <li>/api/parse — 文档解析（文本提取 → 切片 → 向量化 → 写入向量库 + document_chunk 表）</li>
 *   <li>/api/vectors/delete — 删除指定文档的向量</li>
 * </ul>
 *
 * <h3>parse_status 状态机</h3>
 * <pre>
 * PENDING → PARSING → SUCCESS
 *                   → FAILED (记录 parse_fail_msg)
 * </pre>
 *
 * @author knowledge-rag-team
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class DocumentParseService {

    private final DocumentMapper documentMapper;

    @Value("${ai-service.base-url:http://localhost:8000}")
    private String aiServiceBaseUrl;

    private final RestTemplate restTemplate = new RestTemplate();

    // ==================== 异步解析 ====================

    /**
     * 异步触发文档解析
     *
     * <p>状态流转：PENDING → PARSING → (SUCCESS | FAILED)</p>
     *
     * @param docId 文档 ID
     */
    @Async
    public void triggerParseAsync(Long docId) {
        log.info("开始异步解析文档: docId={}", docId);

        Document doc = documentMapper.selectById(docId);
        if (doc == null || doc.getIsDeleted() == 1) {
            log.warn("异步解析失败：文档不存在或已删除 docId={}", docId);
            return;
        }

        // 1. 更新状态为 PARSING
        doc.setParseStatus("PARSING");
        doc.setParseFailMsg(null);
        doc.setUpdateTime(LocalDateTime.now());
        documentMapper.updateById(doc);

        // 2. 调用 Python AI 解析服务
        try {
            callPythonParser(doc);

            // 3. 解析成功
            doc.setParseStatus("SUCCESS");
            doc.setParseFailMsg(null);
            doc.setUpdateTime(LocalDateTime.now());
            documentMapper.updateById(doc);
            log.info("文档解析成功: docId={}, fileName={}, chunkCount={}",
                    doc.getId(), doc.getFileName(), doc.getChunkCount());
        } catch (Exception e) {
            // 4. 解析失败
            String failMsg = e.getMessage() != null ? e.getMessage() : "未知解析错误";
            if (failMsg.length() > 500) {
                failMsg = failMsg.substring(0, 500);
            }
            doc.setParseStatus("FAILED");
            doc.setParseFailMsg(failMsg);
            doc.setUpdateTime(LocalDateTime.now());
            documentMapper.updateById(doc);
            log.error("文档解析失败: docId={}, fileName={}, error={}",
                    doc.getId(), doc.getFileName(), failMsg);
        }
    }

    // ==================== 异步删除向量 ====================

    /**
     * 异步删除向量库中指定文档的所有向量
     *
     * <p>调用 Python AI 服务 DELETE /api/vectors/delete?doc_id=xxx&kb_id=xxx</p>
     *
     * @param docId 文档 ID
     * @param kbId  知识库 ID
     */
    @Async
    public void deleteVectorsAsync(Long docId, Long kbId) {
        log.info("开始异步删除向量: docId={}, kbId={}", docId, kbId);

        try {
            String url = aiServiceBaseUrl + "/api/vectors/delete";
            Map<String, Object> requestBody = Map.of(
                    "doc_id", docId,
                    "kb_id", kbId
            );

            log.debug("调用向量删除接口: url={}, body={}", url, requestBody);

            @SuppressWarnings("unchecked")
            Map<String, Object> response = restTemplate.postForObject(url, requestBody, Map.class);

            if (response != null) {
                log.info("向量删除成功: docId={}, response={}", docId, response);
            } else {
                log.warn("向量删除接口返回空: docId={}", docId);
            }
        } catch (Exception e) {
            log.error("向量删除失败: docId={}, kbId={}, error={}",
                    docId, kbId, e.getMessage());
            // 向量删除失败不抛异常，避免影响主流程
        }
    }

    // ==================== 私有方法 ====================

    /**
     * 调用 Python AI 解析服务
     *
     * <p>POST {aiServiceBaseUrl}/api/parse
     * Body: { doc_id, minio_path, file_type, kb_id }
     *
     * <p>Python 服务负责：
     * <ol>
     *   <li>从 MinIO 下载文件</li>
     *   <li>文本提取（PDF/DOCX/XLSX/TXT/MD）</li>
     *   <li>文本切片（按段落/句子 + 重叠窗口）</li>
     *   <li>向量化（调用 Embedding 模型）</li>
     *   <li>写入向量库（Milvus / Chroma / Qdrant）</li>
     *   <li>写入 document_chunk 表（MySQL）</li>
     *   <li>回写 chunk_count 到 document 表</li>
     * </ol>
     */
    private void callPythonParser(Document doc) {
        String url = aiServiceBaseUrl + "/api/parse";
        Map<String, Object> requestBody = Map.of(
                "doc_id", doc.getId(),
                "minio_path", doc.getMinioPath(),
                "file_type", doc.getFileType(),
                "kb_id", doc.getKbId()
        );

        log.debug("调用 AI 解析服务: url={}, body={}", url, requestBody);

        try {
            @SuppressWarnings("unchecked")
            Map<String, Object> response = restTemplate.postForObject(url, requestBody, Map.class);
            log.info("AI 解析服务响应: {}", response);

            // Python 服务返回 chunk_count，回写到文档
            if (response != null && response.containsKey("chunk_count")) {
                Object chunkCount = response.get("chunk_count");
                if (chunkCount instanceof Number) {
                    doc.setChunkCount(((Number) chunkCount).intValue());
                    documentMapper.updateById(doc);
                }
            }

            // 检查是否有错误
            if (response != null && response.containsKey("error")) {
                throw new RuntimeException("AI 解析服务返回错误: " + response.get("error"));
            }
        } catch (Exception e) {
            log.error("调用 AI 解析服务失败: url={}, error={}", url, e.getMessage());
            throw new RuntimeException("AI 解析服务调用失败: " + e.getMessage(), e);
        }
    }
}
