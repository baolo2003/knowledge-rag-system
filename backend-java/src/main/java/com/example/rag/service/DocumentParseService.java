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
 * <p>异步调用 Python AI 服务进行文档解析（切片+向量化）。
 * 解析流程：
 * <ol>
 *   <li>将 parse_status 设置为 PROCESSING</li>
 *   <li>调用 AI 服务 /api/parse 接口</li>
 *   <li>成功 → parse_status = SUCCESS，更新 chunk_count</li>
 *   <li>失败 → parse_status = FAILED，记录失败原因</li>
 * </ol>
 *
 * <p>parse_status 状态机：PENDING → PARSING → SUCCESS / FAILED</p>
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
     * @param docId 文档 ID
     */
    @Async
    public void triggerParseAsync(Long docId) {
        log.info("开始异步解析文档: docId={}", docId);
        Document doc = documentMapper.selectById(docId);
        if (doc == null) {
            log.warn("异步解析失败：文档不存在 docId={}", docId);
            return;
        }

        // 1. 更新状态为 PARSING
        doc.setParseStatus("PARSING");
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
            log.info("文档解析成功: docId={}, fileName={}", doc.getId(), doc.getFileName());
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

    // ==================== 私有方法 ====================

    /**
     * 调用 Python AI 解析服务
     *
     * <p>POST {aiServiceBaseUrl}/api/parse
     * Body: { doc_id, minio_path, file_type, kb_id }
     *
     * <p>Python 服务负责：文本提取 → 切片 → 向量化 → 写入向量库和 document_chunk 表</p>
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

            // Python 服务返回 chunk_count，更新到文档
            if (response != null && response.containsKey("chunk_count")) {
                Object chunkCount = response.get("chunk_count");
                if (chunkCount instanceof Number) {
                    doc.setChunkCount(((Number) chunkCount).intValue());
                    documentMapper.updateById(doc);
                }
            }
        } catch (Exception e) {
            log.error("调用 AI 解析服务失败: url={}, error={}", url, e.getMessage());
            throw new RuntimeException("AI 解析服务调用失败: " + e.getMessage(), e);
        }
    }
}
