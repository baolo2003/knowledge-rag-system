package com.example.rag.dto.response;

import com.example.rag.entity.KnowledgeBase;
import lombok.Builder;
import lombok.Data;

import java.time.LocalDateTime;

/**
 * 知识库响应 DTO
 *
 * @author knowledge-rag-team
 */
@Data
@Builder
public class KbResponse {

    private Long id;
    private String name;
    private String description;
    private Long ownerId;
    private String visibility;
    private Long orgId;
    private LocalDateTime createTime;
    private LocalDateTime updateTime;

    /** 从 Entity 转换 */
    public static KbResponse from(KnowledgeBase kb) {
        return KbResponse.builder()
                .id(kb.getId())
                .name(kb.getName())
                .description(kb.getDescription())
                .ownerId(kb.getOwnerId())
                .visibility(kb.getVisibility())
                .orgId(kb.getOrgId())
                .createTime(kb.getCreateTime())
                .updateTime(kb.getUpdateTime())
                .build();
    }
}
