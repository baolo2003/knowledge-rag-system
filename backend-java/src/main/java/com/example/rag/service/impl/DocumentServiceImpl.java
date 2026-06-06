package com.example.rag.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.example.rag.common.BusinessException;
import com.example.rag.common.FileUploadValidator;
import com.example.rag.common.SecurityUtils;
import com.example.rag.dto.response.DocumentResponse;
import com.example.rag.dto.response.PageResponse;
import com.example.rag.entity.Document;
import com.example.rag.entity.DocumentChunk;
import com.example.rag.entity.KnowledgeBase;
import com.example.rag.mapper.DocumentChunkMapper;
import com.example.rag.mapper.DocumentMapper;
import com.example.rag.mapper.KnowledgeBaseMapper;
import com.example.rag.service.DocumentParseService;
import com.example.rag.service.DocumentService;
import com.example.rag.service.MinioService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.scheduling.annotation.Async;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.util.StringUtils;
import org.springframework.web.multipart.MultipartFile;

import java.io.ByteArrayInputStream;
import java.io.InputStream;
import java.security.MessageDigest;
import java.time.LocalDateTime;
import java.util.HashMap;
import java.util.HexFormat;
import java.util.Map;
import java.util.Set;
import java.util.concurrent.TimeUnit;

/**
 * 文档服务实现
 *
 * <h3>上传流程（7 步）</h3>
 * <ol>
 *   <li>文件安全校验（Magic Number + 扩展名 + 大小）</li>
 *   <li>知识库权限校验</li>
 *   <li>MD5 去重（同一 KB 下相同 MD5 跳过上传）</li>
 *   <li>上传到 MinIO</li>
 *   <li>保存元数据到 MySQL（parse_status = PENDING）</li>
 *   <li>写入 Redis 缓存</li>
 *   <li>异步触发 Python 解析</li>
 * </ol>
 *
 * <h3>删除流程（4 步）</h3>
 * <ol>
 *   <li>权限校验（owner 或 admin）</li>
 *   <li>软删除 MySQL 记录</li>
 *   <li>Redis 缓存失效</li>
 *   <li>异步清理 MinIO + 切片数据 + 向量库</li>
 * </ol>
 *
 * <h3>Redis 缓存 Key 设计</h3>
 * <pre>
 * doc:{docId}              — 文档详情缓存（Hash）
 * kb:{kbId}:docs:page:*    — 文档列表分页缓存（通配失效）
 * kb:{kbId}:doc:count      — 文档计数缓存
 * </pre>
 *
 * @author knowledge-rag-team
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class DocumentServiceImpl implements DocumentService {

    private final DocumentMapper documentMapper;
    private final DocumentChunkMapper documentChunkMapper;
    private final KnowledgeBaseMapper knowledgeBaseMapper;
    private final MinioService minioService;
    private final FileUploadValidator fileUploadValidator;
    private final DocumentParseService documentParseService;
    private final StringRedisTemplate redisTemplate;

    // ==================== 常量 ====================

    private static final String VISIBILITY_PRIVATE = "PRIVATE";
    private static final String VISIBILITY_PUBLIC = "PUBLIC";
    private static final String VISIBILITY_ORG = "ORG";

    private static final String CACHE_DOC_PREFIX = "doc:";
    private static final String CACHE_KB_DOCS_PREFIX = "kb:";
    private static final String CACHE_DOC_COUNT_SUFFIX = ":doc:count";
    private static final String CACHE_DOCS_PAGE_SUFFIX = ":docs:page:";

    /** 文档详情缓存过期时间（小时） */
    private static final int CACHE_DOC_TTL_HOURS = 24;

    // ==================== 上传文档 ====================

    @Override
    @Transactional
    public DocumentResponse upload(MultipartFile file, Long kbId, String visibility, Long orgId) {
        // ===== 1. 文件安全校验 =====
        String fileType = fileUploadValidator.validate(file);
        String safeFilename = fileUploadValidator.sanitizeFilename(file.getOriginalFilename());

        // ===== 2. 知识库存在性 + 权限校验 =====
        KnowledgeBase kb = knowledgeBaseMapper.selectById(kbId);
        if (kb == null) {
            throw new BusinessException(404, "知识库不存在");
        }
        checkKbUploadPermission(kb);

        // ===== 3. 确定文档可见范围 =====
        String docVisibility = StringUtils.hasText(visibility)
                ? visibility.toUpperCase() : kb.getVisibility();
        Long docOrgId = VISIBILITY_ORG.equals(docVisibility)
                ? (orgId != null ? orgId : kb.getOrgId()) : null;
        validateDocVisibility(docVisibility, docOrgId);

        // ===== 4. 计算 MD5 并去重 =====
        byte[] fileBytes;
        String md5Hex;
        try {
            fileBytes = file.getBytes();
            md5Hex = computeMd5(fileBytes);
        } catch (Exception e) {
            throw new BusinessException(500, "文件读取失败");
        }

        Document existingDoc = findDuplicateInKb(kbId, md5Hex);
        if (existingDoc != null) {
            log.info("MD5 去重命中: kbId={}, md5={}, existingDocId={}, fileName={}",
                    kbId, md5Hex, existingDoc.getId(), existingDoc.getFileName());
            return buildResponse(existingDoc);
        }

        // ===== 5. 上传到 MinIO =====
        long fileSize = file.getSize();
        String contentType = file.getContentType();
        String minioPath;
        try (InputStream uploadStream = new ByteArrayInputStream(fileBytes)) {
            minioPath = minioService.upload(
                    kbId, fileType, fileType, uploadStream, fileSize, contentType);
        } catch (Exception e) {
            log.error("MinIO 上传异常: fileName={}", safeFilename, e);
            throw new BusinessException(500, "文件存储失败，请稍后重试");
        }

        // ===== 6. 保存元数据到 MySQL =====
        Long currentUserId = SecurityUtils.getCurrentUserId();
        Document doc = new Document();
        doc.setKbId(kbId);
        doc.setFileMd5(md5Hex);
        doc.setFileName(safeFilename);
        doc.setFileType(fileType);
        doc.setFileSize(fileSize);
        doc.setMinioPath(minioPath);
        doc.setParseStatus("PENDING");
        doc.setOwnerId(currentUserId);
        doc.setVisibility(docVisibility);
        doc.setOrgId(docOrgId);
        doc.setChunkCount(0);
        doc.setCreateTime(LocalDateTime.now());
        doc.setUpdateTime(LocalDateTime.now());

        documentMapper.insert(doc);
        log.info("文档元数据已保存: docId={}, fileName={}, kbId={}, md5={}, size={}",
                doc.getId(), safeFilename, kbId, md5Hex, fileSize);

        // ===== 7. 写入 Redis 缓存 =====
        cacheDocument(doc);

        // ===== 8. 使知识库文档列表缓存失效 =====
        evictKbDocListCache(kbId);

        // ===== 9. 异步触发 Python 解析 =====
        documentParseService.triggerParseAsync(doc.getId());

        return buildResponse(doc);
    }

    // ==================== 分页列出知识库下的文档 ====================

    @Override
    public PageResponse<DocumentResponse> listByKb(Long kbId, int page, int size, String keyword) {
        // 1. 校验知识库存在 + 查看权限
        KnowledgeBase kb = knowledgeBaseMapper.selectById(kbId);
        if (kb == null) {
            throw new BusinessException(404, "知识库不存在");
        }
        checkKbViewPermission(kb);

        // 2. 构建权限过滤 + 搜索条件
        LambdaQueryWrapper<Document> wrapper = buildPermissionFilter(kbId);

        // 文件名模糊搜索
        if (StringUtils.hasText(keyword)) {
            wrapper.like(Document::getFileName, keyword);
        }

        wrapper.orderByDesc(Document::getCreateTime);

        // 3. MyBatis-Plus 分页查询
        Page<Document> pageObj = new Page<>(page, size);
        IPage<Document> result = documentMapper.selectPage(pageObj, wrapper);

        log.debug("文档分页查询: kbId={}, page={}, size={}, keyword={}, total={}",
                kbId, page, size, keyword, result.getTotal());

        // 4. 转换结果（含预签名 URL）
        return PageResponse.from(result, doc -> buildResponse(doc));
    }

    // ==================== 获取文档详情 ====================

    @Override
    public DocumentResponse getById(Long docId) {
        // 1. 尝试从 Redis 读取
        Document doc = getCachedDocument(docId);
        if (doc != null) {
            log.debug("文档缓存命中: docId={}", docId);
            checkDocViewPermission(doc);
            return buildResponse(doc);
        }

        // 2. 从 MySQL 查询
        doc = documentMapper.selectById(docId);
        if (doc == null) {
            throw new BusinessException(404, "文档不存在");
        }

        // 3. 权限校验
        checkDocViewPermission(doc);

        // 4. 写入缓存
        cacheDocument(doc);

        return buildResponse(doc);
    }

    // ==================== 删除文档（完整实现） ====================

    @Override
    @Transactional
    public void delete(Long docId) {
        // ===== 1. 查询文档 =====
        Document doc = documentMapper.selectById(docId);
        if (doc == null) {
            throw new BusinessException(404, "文档不存在");
        }

        // ===== 2. 权限校验（仅 owner 或 admin 可删除） =====
        checkOwnerOrAdmin(doc, "删除");

        // ===== 3. 软删除（MyBatis-Plus @TableLogic） =====
        documentMapper.deleteById(docId);
        log.info("文档已软删除: docId={}, fileName={}, kbId={}", docId, doc.getFileName(), doc.getKbId());

        // ===== 4. Redis 缓存失效 =====
        evictDocumentCache(docId);
        evictKbDocListCache(doc.getKbId());

        // ===== 5. 异步清理 MinIO + 切片 + 向量库 =====
        asyncCleanup(doc);
    }

    // ==================== 重新解析 ====================

    @Override
    @Transactional
    public DocumentResponse reparse(Long docId) {
        // ===== 1. 查询文档 =====
        Document doc = documentMapper.selectById(docId);
        if (doc == null) {
            throw new BusinessException(404, "文档不存在");
        }

        // ===== 2. 权限校验 =====
        checkDocViewPermission(doc);

        // ===== 3. 状态机校验：仅 PENDING / FAILED / SUCCESS 可重新解析 =====
        if ("PARSING".equals(doc.getParseStatus())) {
            throw new BusinessException(400, "文档正在解析中，请稍等片刻再试");
        }

        // ===== 4. 清理旧切片数据（如果有） =====
        if (doc.getChunkCount() != null && doc.getChunkCount() > 0) {
            // 先清理向量库中的旧向量
            documentParseService.deleteVectorsAsync(doc.getId(), doc.getKbId());
            // 删除旧的切片记录
            documentChunkMapper.delete(
                    new LambdaQueryWrapper<DocumentChunk>()
                            .eq(DocumentChunk::getDocumentId, docId)
            );
            log.info("旧切片数据已清理: docId={}, oldChunkCount={}", docId, doc.getChunkCount());
        }

        // ===== 5. 重置解析状态 =====
        doc.setParseStatus("PENDING");
        doc.setParseFailMsg(null);
        doc.setChunkCount(0);
        doc.setUpdateTime(LocalDateTime.now());
        documentMapper.updateById(doc);
        log.info("文档解析状态已重置: docId={}, fileName={}", docId, doc.getFileName());

        // ===== 6. 更新 Redis 缓存 =====
        cacheDocument(doc);
        evictKbDocListCache(doc.getKbId());

        // ===== 7. 异步触发 Python 解析 =====
        documentParseService.triggerParseAsync(doc.getId());

        return buildResponse(doc);
    }

    // ==================== 私有：MD5 / 去重 ====================

    private String computeMd5(byte[] fileBytes) {
        try {
            MessageDigest md = MessageDigest.getInstance("MD5");
            byte[] digest = md.digest(fileBytes);
            return HexFormat.of().withLowerCase().formatHex(digest);
        } catch (Exception e) {
            throw new BusinessException(500, "文件校验失败");
        }
    }

    private Document findDuplicateInKb(Long kbId, String md5) {
        return documentMapper.selectOne(
                new LambdaQueryWrapper<Document>()
                        .eq(Document::getKbId, kbId)
                        .eq(Document::getFileMd5, md5)
                        .last("LIMIT 1")
        );
    }

    // ==================== 私有：权限过滤查询构建 ====================

    /**
     * 构建权限过滤 + kb_id 查询条件
     *
     * <p>普通用户可见：
     * <pre>
     *   kb_id = ? AND (
     *     owner_id = 自己
     *     OR visibility = 'PUBLIC'
     *     OR (visibility = 'ORG' AND org_id = 自己的 org_id)
     *   )
     * </pre>
     * ADMIN 仅按 kb_id 过滤。
     */
    private LambdaQueryWrapper<Document> buildPermissionFilter(Long kbId) {
        LambdaQueryWrapper<Document> wrapper = new LambdaQueryWrapper<>();
        wrapper.eq(Document::getKbId, kbId);

        if (SecurityUtils.isAdmin()) {
            return wrapper;
        }

        Long currentUserId = SecurityUtils.getCurrentUserId();
        Long currentOrgId = SecurityUtils.getCurrentUserOrgId();

        wrapper.and(w -> w
                .eq(Document::getOwnerId, currentUserId)
                .or()
                .eq(Document::getVisibility, VISIBILITY_PUBLIC)
                .or()
                .and(w2 -> w2
                        .eq(Document::getVisibility, VISIBILITY_ORG)
                        .eq(Document::getOrgId, currentOrgId)
                )
        );

        return wrapper;
    }

    // ==================== 私有：权限校验 ====================

    private void checkKbUploadPermission(KnowledgeBase kb) {
        if (SecurityUtils.isAdmin()) return;
        Long currentUserId = SecurityUtils.getCurrentUserId();
        Long currentOrgId = SecurityUtils.getCurrentUserOrgId();

        if (kb.getOwnerId().equals(currentUserId)) return;
        if (VISIBILITY_PUBLIC.equals(kb.getVisibility())) return;
        if (VISIBILITY_ORG.equals(kb.getVisibility())
                && kb.getOrgId() != null && kb.getOrgId().equals(currentOrgId)) return;

        throw new BusinessException(403, "无权向该知识库上传文档");
    }

    private void checkKbViewPermission(KnowledgeBase kb) {
        if (SecurityUtils.isAdmin()) return;
        Long currentUserId = SecurityUtils.getCurrentUserId();
        Long currentOrgId = SecurityUtils.getCurrentUserOrgId();

        if (kb.getOwnerId().equals(currentUserId)) return;
        if (VISIBILITY_PUBLIC.equals(kb.getVisibility())) return;
        if (VISIBILITY_ORG.equals(kb.getVisibility())
                && kb.getOrgId() != null && kb.getOrgId().equals(currentOrgId)) return;

        throw new BusinessException(403, "无权查看该知识库下的文档");
    }

    private void checkDocViewPermission(Document doc) {
        if (SecurityUtils.isAdmin()) return;
        Long currentUserId = SecurityUtils.getCurrentUserId();
        Long currentOrgId = SecurityUtils.getCurrentUserOrgId();

        if (doc.getOwnerId().equals(currentUserId)) return;
        if (VISIBILITY_PUBLIC.equals(doc.getVisibility())) return;
        if (VISIBILITY_ORG.equals(doc.getVisibility())
                && doc.getOrgId() != null && doc.getOrgId().equals(currentOrgId)) return;

        throw new BusinessException(403, "无权查看该文档");
    }

    private void checkOwnerOrAdmin(Document doc, String action) {
        if (SecurityUtils.isAdmin()) return;
        Long currentUserId = SecurityUtils.getCurrentUserId();
        if (!doc.getOwnerId().equals(currentUserId)) {
            throw new BusinessException(403,
                    "无权" + action + "该文档，仅文档上传者或管理员可操作");
        }
    }

    private void validateDocVisibility(String visibility, Long orgId) {
        if (!VISIBILITY_PRIVATE.equals(visibility)
                && !VISIBILITY_PUBLIC.equals(visibility)
                && !VISIBILITY_ORG.equals(visibility)) {
            throw new BusinessException(400,
                    "无效的可见范围: " + visibility + "，可选值: PRIVATE / PUBLIC / ORG");
        }
        if (VISIBILITY_ORG.equals(visibility) && orgId == null) {
            throw new BusinessException(400, "可见范围为 ORG 时，组织 ID 不能为空");
        }
    }

    // ==================== 私有：Redis 缓存操作 ====================

    /**
     * 缓存文档详情
     */
    private void cacheDocument(Document doc) {
        try {
            String key = CACHE_DOC_PREFIX + doc.getId();
            Map<String, String> fields = new HashMap<>();
            fields.put("id", String.valueOf(doc.getId()));
            fields.put("kbId", String.valueOf(doc.getKbId()));
            fields.put("fileName", doc.getFileName() != null ? doc.getFileName() : "");
            fields.put("fileType", doc.getFileType() != null ? doc.getFileType() : "");
            fields.put("fileSize", String.valueOf(doc.getFileSize()));
            fields.put("parseStatus", doc.getParseStatus() != null ? doc.getParseStatus() : "PENDING");
            fields.put("chunkCount", String.valueOf(doc.getChunkCount() != null ? doc.getChunkCount() : 0));
            fields.put("minioPath", doc.getMinioPath() != null ? doc.getMinioPath() : "");
            fields.put("ownerId", String.valueOf(doc.getOwnerId()));
            fields.put("visibility", doc.getVisibility() != null ? doc.getVisibility() : "");
            fields.put("orgId", String.valueOf(doc.getOrgId() != null ? doc.getOrgId() : ""));
            fields.put("createTime", doc.getCreateTime() != null ? doc.getCreateTime().toString() : "");
            redisTemplate.opsForHash().putAll(key, fields);
            redisTemplate.expire(key, CACHE_DOC_TTL_HOURS, TimeUnit.HOURS);
        } catch (Exception e) {
            log.warn("文档缓存写入失败: docId={}", doc.getId(), e);
        }
    }

    /**
     * 从缓存获取文档
     */
    private Document getCachedDocument(Long docId) {
        try {
            String key = CACHE_DOC_PREFIX + docId;
            Object fileName = redisTemplate.opsForHash().get(key, "fileName");
            if (fileName == null) return null;

            Document doc = new Document();
            doc.setId(docId);
            doc.setKbId(parseLong(redisTemplate.opsForHash().get(key, "kbId")));
            doc.setFileName(String.valueOf(fileName));
            doc.setFileType(String.valueOf(redisTemplate.opsForHash().get(key, "fileType")));
            doc.setFileSize(parseLong(redisTemplate.opsForHash().get(key, "fileSize")));
            doc.setParseStatus(String.valueOf(redisTemplate.opsForHash().get(key, "parseStatus")));
            doc.setChunkCount(parseInt(redisTemplate.opsForHash().get(key, "chunkCount")));
            doc.setMinioPath(String.valueOf(redisTemplate.opsForHash().get(key, "minioPath")));
            doc.setOwnerId(parseLong(redisTemplate.opsForHash().get(key, "ownerId")));
            doc.setVisibility(String.valueOf(redisTemplate.opsForHash().get(key, "visibility")));
            doc.setOrgId(parseLong(redisTemplate.opsForHash().get(key, "orgId")));

            String createTime = String.valueOf(redisTemplate.opsForHash().get(key, "createTime"));
            if (!"null".equals(createTime) && !createTime.isEmpty()) {
                doc.setCreateTime(LocalDateTime.parse(createTime));
            }
            return doc;
        } catch (Exception e) {
            log.warn("文档缓存读取失败: docId={}", docId, e);
            return null;
        }
    }

    /**
     * 使单个文档缓存失效
     */
    private void evictDocumentCache(Long docId) {
        try {
            String key = CACHE_DOC_PREFIX + docId;
            Boolean deleted = redisTemplate.delete(key);
            log.debug("文档缓存已失效: docId={}, deleted={}", docId, deleted);
        } catch (Exception e) {
            log.warn("文档缓存失效失败: docId={}", docId, e);
        }
    }

    /**
     * 使知识库文档列表相关缓存全部失效（通配删除）
     */
    private void evictKbDocListCache(Long kbId) {
        try {
            // 删除文档计数缓存
            String countKey = CACHE_KB_DOCS_PREFIX + kbId + CACHE_DOC_COUNT_SUFFIX;
            redisTemplate.delete(countKey);

            // 通配删除分页缓存
            String pattern = CACHE_KB_DOCS_PREFIX + kbId + CACHE_DOCS_PAGE_SUFFIX + "*";
            Set<String> keys = redisTemplate.keys(pattern);
            if (keys != null && !keys.isEmpty()) {
                redisTemplate.delete(keys);
                log.debug("文档列表缓存已失效: kbId={}, keys={}", kbId, keys.size());
            }
        } catch (Exception e) {
            log.warn("文档列表缓存失效失败: kbId={}", kbId, e);
        }
    }

    private Long parseLong(Object obj) {
        if (obj == null) return null;
        try { return Long.parseLong(String.valueOf(obj)); } catch (NumberFormatException e) { return null; }
    }

    private Integer parseInt(Object obj) {
        if (obj == null) return 0;
        try { return Integer.parseInt(String.valueOf(obj)); } catch (NumberFormatException e) { return 0; }
    }

    // ==================== 私有：异步清理 ====================

    /**
     * 异步清理：MinIO 文件 + 切片数据 + 向量库
     *
     * <p>软删除后异步执行，不阻塞主流程，失败不影响删除状态</p>
     */
    @Async
    public void asyncCleanup(Document doc) {
        log.info("开始异步清理文档资源: docId={}, fileName={}, minioPath={}",
                doc.getId(), doc.getFileName(), doc.getMinioPath());

        // ---- 1. 清理 MinIO 文件 ----
        try {
            boolean deleted = minioService.delete(doc.getMinioPath());
            if (deleted) {
                log.info("MinIO 文件已清理: docId={}, path={}", doc.getId(), doc.getMinioPath());
            } else {
                log.warn("MinIO 文件不存在或已清理: docId={}, path={}", doc.getId(), doc.getMinioPath());
            }
        } catch (Exception e) {
            log.error("MinIO 文件清理失败: docId={}, path={}", doc.getId(), doc.getMinioPath(), e);
        }

        // ---- 2. 清理切片数据（document_chunk 表） ----
        try {
            int deletedChunks = documentChunkMapper.delete(
                    new LambdaQueryWrapper<DocumentChunk>()
                            .eq(DocumentChunk::getDocumentId, doc.getId())
            );
            log.info("切片数据已清理: docId={}, deletedChunks={}", doc.getId(), deletedChunks);
        } catch (Exception e) {
            log.error("切片数据清理失败: docId={}", doc.getId(), e);
        }

        // ---- 3. 清理向量库 ----
        try {
            documentParseService.deleteVectorsAsync(doc.getId(), doc.getKbId());
        } catch (Exception e) {
            log.error("向量库清理失败: docId={}", doc.getId(), e);
        }

        log.info("异步清理完成: docId={}", doc.getId());
    }

    // ==================== 私有：构建响应 ====================

    /**
     * 构建 DocumentResponse（含预签名下载 URL）
     */
    private DocumentResponse buildResponse(Document doc) {
        return DocumentResponse.from(doc, minioService.getPresignedUrl(doc.getMinioPath()));
    }
}
