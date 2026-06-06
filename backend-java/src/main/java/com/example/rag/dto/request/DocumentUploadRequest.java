package com.example.rag.dto.request;

import jakarta.validation.constraints.NotNull;
import lombok.Data;
import org.springframework.web.multipart.MultipartFile;

/**
 * 文档上传请求 DTO
 *
 * <p>通过 multipart/form-data 上传，字段说明：
 * <ul>
 *   <li>file: 上传的文件（必填）</li>
 *   <li>kbId: 目标知识库 ID（必填）</li>
 *   <li>visibility: 可见范围 PRIVATE/PUBLIC/ORG（默认继承知识库可见性）</li>
 *   <li>orgId: 组织 ID（ORG 可见时必填）</li>
 * </ul>
 *
 * @author knowledge-rag-team
 */
@Data
public class DocumentUploadRequest {

    /** 上传文件（必填） */
    @NotNull(message = "上传文件不能为空")
    private MultipartFile file;

    /** 目标知识库 ID（必填） */
    @NotNull(message = "知识库 ID 不能为空")
    private Long kbId;

    /** 可见范围：PRIVATE / PUBLIC / ORG（可选，默认继承知识库） */
    private String visibility;

    /** 组织 ID（ORG 可见时必填） */
    private Long orgId;
}
