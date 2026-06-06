package com.example.rag.dto.response;

import com.example.rag.entity.Document;
import lombok.Builder;
import lombok.Data;

import java.time.LocalDateTime;

/**
 * 文档响应 DTO
 *
 * @author knowledge-rag-team
 */
@Data
@Builder
public class DocumentResponse {

    private Long id;
    private Long kbId;
    private String fileMd5;
    private String fileName;
    private String fileType;
    private Long fileSize;
    private String minioPath;
    private String parseStatus;
    private String parseFailMsg;
    private Long ownerId;
    private String visibility;
    private Long orgId;
    private Integer chunkCount;
    private LocalDateTime createTime;
    private LocalDateTime updateTime;

    /** 预签名下载 URL（临时生成，不持久化） */
    private String downloadUrl;

    /** 从 Entity 转换（不含下载 URL） */
    public static DocumentResponse from(Document doc) {
        return DocumentResponse.builder()
                .id(doc.getId())
                .kbId(doc.getKbId())
                .fileMd5(doc.getFileMd5())
                .fileName(doc.getFileName())
                .fileType(doc.getFileType())
                .fileSize(doc.getFileSize())
                .minioPath(doc.getMinioPath())
                .parseStatus(doc.getParseStatus())
                .parseFailMsg(doc.getParseFailMsg())
                .ownerId(doc.getOwnerId())
                .visibility(doc.getVisibility())
                .orgId(doc.getOrgId())
                .chunkCount(doc.getChunkCount())
                .createTime(doc.getCreateTime())
                .updateTime(doc.getUpdateTime())
                .build();
    }

    /** 从 Entity 转换（含下载 URL） */
    public static DocumentResponse from(Document doc, String downloadUrl) {
        DocumentResponse resp = from(doc);
        resp.setDownloadUrl(downloadUrl);
        return resp;
    }
}
