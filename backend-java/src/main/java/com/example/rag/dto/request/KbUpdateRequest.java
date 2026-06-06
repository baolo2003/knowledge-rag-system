package com.example.rag.dto.request;

import jakarta.validation.constraints.Size;
import lombok.Data;

/**
 * 知识库更新请求 DTO
 *
 * <p>所有字段均为可选，仅更新非 null 字段。
 * 只有 owner 或 admin 有权更新。</p>
 *
 * @author knowledge-rag-team
 */
@Data
public class KbUpdateRequest {

    @Size(max = 200, message = "知识库名称长度不能超过 200")
    private String name;

    @Size(max = 1000, message = "知识库描述长度不能超过 1000")
    private String description;

    /** 可见范围：PRIVATE / PUBLIC / ORG */
    private String visibility;

    /** 所属组织 ID */
    private Long orgId;
}
