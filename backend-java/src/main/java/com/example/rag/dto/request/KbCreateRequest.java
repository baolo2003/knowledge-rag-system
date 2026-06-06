package com.example.rag.dto.request;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;
import lombok.Data;

/**
 * 知识库创建请求 DTO
 *
 * @author knowledge-rag-team
 */
@Data
public class KbCreateRequest {

    @NotBlank(message = "知识库名称不能为空")
    @Size(max = 200, message = "知识库名称长度不能超过 200")
    private String name;

    @Size(max = 1000, message = "知识库描述长度不能超过 1000")
    private String description;

    /**
     * 可见范围：PRIVATE / PUBLIC / ORG
     * <p>默认 PRIVATE：仅 owner 可见</p>
     */
    @NotBlank(message = "可见范围不能为空")
    private String visibility;

    /** 所属组织 ID（visibility = ORG 时必填） */
    private Long orgId;
}
