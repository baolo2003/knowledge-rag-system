package com.example.rag.controller;

import com.example.rag.common.Result;
import com.example.rag.dto.response.DocumentResponse;
import com.example.rag.service.DocumentService;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.Parameter;
import io.swagger.v3.oas.annotations.media.Schema;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.constraints.NotNull;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.multipart.MultipartFile;

import java.util.List;

/**
 * 文档管理接口
 *
 * <p>提供文档上传、查询、删除、重新解析等操作。
 * 上传文件需经过 Magic Number 校验 + MD5 去重。</p>
 *
 * @author knowledge-rag-team
 */
@Tag(name = "文档管理", description = "文档上传 / 查询 / 删除 / 重新解析")
@RestController
@RequestMapping("/api/documents")
@RequiredArgsConstructor
public class DocumentController {

    private final DocumentService documentService;

    @Operation(
            summary = "上传文档",
            description = """
                    上传文档到指定知识库。文件需经过：
                    1. Magic Number 魔数校验（防止扩展名伪造）
                    2. 文件大小限制（≤50MB）
                    3. MD5 去重（同一 KB 下相同文件跳过上传）
                    上传成功后异步触发 Python 解析服务进行切片 + 向量化。

                    支持的文件类型：PDF、DOCX、XLSX、TXT、MD
                    """
    )
    @PostMapping("/upload")
    public Result<DocumentResponse> upload(
            @Parameter(description = "上传文件", required = true)
            @RequestParam("file") @NotNull MultipartFile file,

            @Parameter(description = "目标知识库 ID", required = true)
            @RequestParam("kbId") @NotNull Long kbId,

            @Parameter(description = "可见范围：PRIVATE / PUBLIC / ORG（可选，默认继承知识库）")
            @RequestParam(value = "visibility", required = false) String visibility,

            @Parameter(description = "组织 ID（ORG 可见时必填）")
            @RequestParam(value = "orgId", required = false) Long orgId) {

        DocumentResponse doc = documentService.upload(file, kbId, visibility, orgId);
        return Result.success(doc);
    }

    @Operation(
            summary = "列出知识库下的文档",
            description = "权限过滤：用户仅能看到自己上传 / 公开 / 同组织可见的文档"
    )
    @GetMapping
    public Result<List<DocumentResponse>> list(
            @Parameter(description = "知识库 ID", required = true)
            @RequestParam("kbId") @NotNull Long kbId) {

        List<DocumentResponse> docs = documentService.listByKb(kbId);
        return Result.success(docs);
    }

    @Operation(summary = "获取文档详情", description = "包含预签名下载 URL（7天有效）")
    @GetMapping("/{id}")
    public Result<DocumentResponse> getById(
            @Parameter(description = "文档 ID", required = true)
            @PathVariable Long id) {

        DocumentResponse doc = documentService.getById(id);
        return Result.success(doc);
    }

    @Operation(summary = "删除文档（软删除）", description = "软删除文档，异步清理 MinIO 文件和切片数据")
    @DeleteMapping("/{id}")
    public Result<Void> delete(
            @Parameter(description = "文档 ID", required = true)
            @PathVariable Long id) {

        documentService.delete(id);
        return Result.success();
    }

    @Operation(
            summary = "重新解析文档",
            description = """
                    重新触发文档解析（切片 + 向量化）。
                    仅 PENDING / FAILED 状态可重新解析，PARSING 状态拒绝重复触发。
                    """
    )
    @PostMapping("/{id}/reparse")
    public Result<DocumentResponse> reparse(
            @Parameter(description = "文档 ID", required = true)
            @PathVariable Long id) {

        DocumentResponse doc = documentService.reparse(id);
        return Result.success("重新解析已触发", doc);
    }
}
