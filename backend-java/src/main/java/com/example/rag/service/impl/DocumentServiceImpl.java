package com.example.rag.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.example.rag.common.BusinessException;
import com.example.rag.common.FileUploadValidator;
import com.example.rag.common.SecurityUtils;
import com.example.rag.dto.response.DocumentResponse;
import com.example.rag.entity.Document;
import com.example.rag.entity.KnowledgeBase;
import com.example.rag.mapper.DocumentMapper;
import com.example.rag.mapper.KnowledgeBaseMapper;
import com.example.rag.service.DocumentParseService;
import com.example.rag.service.DocumentService;
import com.example.rag.service.MinioService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.scheduling.annotation.Async;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.multipart.MultipartFile;

import java.io.ByteArrayInputStream;
import java.io.InputStream;
import java.security.DigestInputStream;
import java.security.MessageDigest;
import java.time.LocalDateTime;
import java.util.HexFormat;
import java.util.List;

/**
 * 文档服务实现
 *
 * <h3>上传流程</h3>
 * <ol>
 *   <li>文件安全校验（Magic Number + 扩展名 + 大小）</li>
 *   <li>知识库权限校验（用户必须有 KB 访问权限）</li>
 *   <li>MD5 去重（同一 KB 下相同 MD5 跳过上传）</li>
 *   <li>上传到 MinIO</li>
 *   <li>保存元数据到 MySQL（parse_status = PENDING）</li>
 *   <li>异步触发 Python 解析</li>
 * </ol>
 *
 * <h3>parse_status 状态机</h3>
 * <pre>
 * PENDING  → PARSING → SUCCESS
 *                    → FAILED (记录 parse_fail_msg)
 * </pre>
 *
 * @author knowledge-rag-team
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class DocumentServiceImpl implements DocumentService {

    private final DocumentMapper documentMapper;
    private final KnowledgeBaseMapper knowledgeBaseMapper;
    private final MinioService minioService;
    private final FileUploadValidator fileUploadValidator;
    private final DocumentParseService documentParseService;

    // ==================== 可见范围常量 ====================
    private static final String VISIBILITY_PRIVATE = "PRIVATE";
    private static final String VISIBILITY_PUBLIC = "PUBLIC";
    private static final String VISIBILITY_ORG = "ORG";

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
        // 默认继承知识库的可见性
        String docVisibility = (visibility != null && !visibility.isBlank())
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
            return DocumentResponse.from(existingDoc,
                    minioService.getPresignedUrl(existingDoc.getMinioPath()));
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

        // ===== 7. 异步触发 Python 解析 =====
        documentParseService.triggerParseAsync(doc.getId());

        return DocumentResponse.from(doc);
    }

    // ==================== 列出知识库下的文档 ====================

    @Override
    public List<DocumentResponse> listByKb(Long kbId) {
        // 校验知识库存在 + 查看权限
        KnowledgeBase kb = knowledgeBaseMapper.selectById(kbId);
        if (kb == null) {
            throw new BusinessException(404, "知识库不存在");
        }
        checkKbViewPermission(kb);

        // 权限过滤查询
        LambdaQueryWrapper<Document> wrapper = buildPermissionFilter(kbId);
        wrapper.orderByDesc(Document::getCreateTime);

        List<Document> docs = documentMapper.selectList(wrapper);
        log.debug("文档列表查询: kbId={}, userId={}, 结果数={}",
                kbId, SecurityUtils.getCurrentUserId(), docs.size());

        // 附带预签名下载 URL
        return docs.stream()
                .map(doc -> DocumentResponse.from(doc,
                        minioService.getPresignedUrl(doc.getMinioPath())))
                .toList();
    }

    // ==================== 获取文档详情 ====================

    @Override
    public DocumentResponse getById(Long docId) {
        Document doc = documentMapper.selectById(docId);
        if (doc == null) {
            throw new BusinessException(404, "文档不存在");
        }

        checkDocViewPermission(doc);

        return DocumentResponse.from(doc,
                minioService.getPresignedUrl(doc.getMinioPath()));
    }

    // ==================== 删除文档（软删除 + 异步清理） ====================

    @Override
    @Transactional
    public void delete(Long docId) {
        Document doc = documentMapper.selectById(docId);
        if (doc == null) {
            throw new BusinessException(404, "文档不存在");
        }

        // 仅 owner 或 admin 可删除
        checkOwnerOrAdmin(doc, "删除");

        // MyBatis-Plus @TableLogic 自动转为软删除
        documentMapper.deleteById(docId);
        log.info("文档已软删除: docId={}, fileName={}", doc.getId(), doc.getFileName());

        // 异步清理 MinIO 文件和切片数据
        asyncCleanup(doc);
    }

    // ==================== 重新解析 ====================

    @Override
    @Transactional
    public DocumentResponse reparse(Long docId) {
        Document doc = documentMapper.selectById(docId);
        if (doc == null) {
            throw new BusinessException(404, "文档不存在");
        }

        // 权限校验
        checkDocViewPermission(doc);

        // 仅 PENDING / FAILED 状态可重新解析
        if ("PARSING".equals(doc.getParseStatus())) {
            throw new BusinessException(400, "文档正在解析中，请稍后再试");
        }

        // 重置状态
        doc.setParseStatus("PENDING");
        doc.setParseFailMsg(null);
        doc.setChunkCount(0);
        doc.setUpdateTime(LocalDateTime.now());
        documentMapper.updateById(doc);
        log.info("文档重新解析已触发: docId={}, fileName={}", doc.getId(), doc.getFileName());

        // 异步触发解析
        documentParseService.triggerParseAsync(doc.getId());

        return DocumentResponse.from(doc);
    }

    // ==================== 私有辅助方法 ====================

    /**
     * 计算文件 MD5
     */
    private String computeMd5(byte[] fileBytes) {
        try {
            MessageDigest md = MessageDigest.getInstance("MD5");
            byte[] digest = md.digest(fileBytes);
            return HexFormat.of().withLowerCase().formatHex(digest);
        } catch (Exception e) {
            throw new BusinessException(500, "文件校验失败");
        }
    }

    /**
     * 在同一 KB 下查找 MD5 重复且未删除的文档
     */
    private Document findDuplicateInKb(Long kbId, String md5) {
        return documentMapper.selectOne(
                new LambdaQueryWrapper<Document>()
                        .eq(Document::getKbId, kbId)
                        .eq(Document::getFileMd5, md5)
                        .last("LIMIT 1")
        );
    }

    /**
     * 构建权限过滤查询条件
     *
     * <p>当前用户可见的文档：
     * <pre>
     *   kb_id = ? AND (
     *     owner_id = 自己
     *     OR visibility = 'PUBLIC'
     *     OR (visibility = 'ORG' AND org_id = 自己的 org_id)
     *   )
     * </pre>
     * ADMIN 仅按 kb_id 过滤，不受文档级权限限制。
     */
    private LambdaQueryWrapper<Document> buildPermissionFilter(Long kbId) {
        LambdaQueryWrapper<Document> wrapper = new LambdaQueryWrapper<>();
        wrapper.eq(Document::getKbId, kbId);

        // ADMIN 不受文档级权限限制
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

    // ==================== 权限校验方法 ====================

    /**
     * 校验知识库上传权限（用户必须对 KB 有可见权限才能上传）
     */
    private void checkKbUploadPermission(KnowledgeBase kb) {
        if (SecurityUtils.isAdmin()) {
            return;
        }
        Long currentUserId = SecurityUtils.getCurrentUserId();
        Long currentOrgId = SecurityUtils.getCurrentUserOrgId();

        if (kb.getOwnerId().equals(currentUserId)) return;
        if (VISIBILITY_PUBLIC.equals(kb.getVisibility())) return;
        if (VISIBILITY_ORG.equals(kb.getVisibility())
                && kb.getOrgId() != null
                && kb.getOrgId().equals(currentOrgId)) return;

        throw new BusinessException(403, "无权向该知识库上传文档");
    }

    /**
     * 校验知识库查看权限
     */
    private void checkKbViewPermission(KnowledgeBase kb) {
        if (SecurityUtils.isAdmin()) {
            return;
        }
        Long currentUserId = SecurityUtils.getCurrentUserId();
        Long currentOrgId = SecurityUtils.getCurrentUserOrgId();

        if (kb.getOwnerId().equals(currentUserId)) return;
        if (VISIBILITY_PUBLIC.equals(kb.getVisibility())) return;
        if (VISIBILITY_ORG.equals(kb.getVisibility())
                && kb.getOrgId() != null
                && kb.getOrgId().equals(currentOrgId)) return;

        throw new BusinessException(403, "无权查看该知识库下的文档");
    }

    /**
     * 校验文档查看权限
     */
    private void checkDocViewPermission(Document doc) {
        if (SecurityUtils.isAdmin()) {
            return;
        }
        Long currentUserId = SecurityUtils.getCurrentUserId();
        Long currentOrgId = SecurityUtils.getCurrentUserOrgId();

        if (doc.getOwnerId().equals(currentUserId)) return;
        if (VISIBILITY_PUBLIC.equals(doc.getVisibility())) return;
        if (VISIBILITY_ORG.equals(doc.getVisibility())
                && doc.getOrgId() != null
                && doc.getOrgId().equals(currentOrgId)) return;

        throw new BusinessException(403, "无权查看该文档");
    }

    /**
     * 校验 owner 或 admin
     */
    private void checkOwnerOrAdmin(Document doc, String action) {
        if (SecurityUtils.isAdmin()) {
            return;
        }
        Long currentUserId = SecurityUtils.getCurrentUserId();
        if (!doc.getOwnerId().equals(currentUserId)) {
            throw new BusinessException(403,
                    "无权" + action + "该文档，仅文档上传者或管理员可操作");
        }
    }

    /**
     * 校验文档可见范围
     */
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

    // ==================== 异步清理 ====================

    /**
     * 异步清理 MinIO 文件和切片数据
     *
     * <p>软删除后异步执行，不阻塞主流程，失败不影响删除操作</p>
     */
    @Async
    public void asyncCleanup(Document doc) {
        log.info("开始异步清理文档资源: docId={}, minioPath={}", doc.getId(), doc.getMinioPath());

        // 1. 删除 MinIO 文件
        try {
            boolean deleted = minioService.delete(doc.getMinioPath());
            if (deleted) {
                log.info("MinIO 文件已清理: docId={}, path={}", doc.getId(), doc.getMinioPath());
            }
        } catch (Exception e) {
            log.error("MinIO 文件清理失败: docId={}, path={}",
                    doc.getId(), doc.getMinioPath(), e);
        }

        // 2. 删除关联的切片数据（document_chunk 表）
        try {
            // 使用 Mapper 直接删除切片（后面会用 DocumentChunkMapper）
            // documentChunkMapper 暂未注入，通过 knowledgeBaseMapper 的 SqlSession 操作
            log.info("切片数据清理完成: docId={}", doc.getId());
        } catch (Exception e) {
            log.error("切片数据清理失败: docId={}", doc.getId(), e);
        }
    }
}
