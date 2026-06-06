package com.example.rag.controller;

import com.example.rag.common.Result;
import com.example.rag.dto.request.KbCreateRequest;
import com.example.rag.dto.request.KbUpdateRequest;
import com.example.rag.dto.response.KbResponse;
import com.example.rag.service.KnowledgeBaseService;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.Parameter;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;

import java.util.List;

/**
 * 知识库管理接口
 *
 * <p>提供知识库的 CRUD 操作，包括权限过滤查询。
 * 权限规则：用户仅能看到自己创建 / 公开 / 同组织可见的知识库。</p>
 *
 * @author knowledge-rag-team
 */
@Tag(name = "知识库管理", description = "知识库 CRUD + 权限过滤")
@RestController
@RequestMapping("/api/kb")
@RequiredArgsConstructor
public class KnowledgeBaseController {

    private final KnowledgeBaseService knowledgeBaseService;

    @Operation(summary = "创建知识库", description = "创建新知识库，owner_id 自动设置为当前登录用户")
    @PostMapping
    public Result<KbResponse> create(@Valid @RequestBody KbCreateRequest request) {
        KbResponse kb = knowledgeBaseService.create(request);
        return Result.success(kb);
    }

    @Operation(summary = "列出可见知识库", description = "根据权限过滤：owner=自己 / PUBLIC / ORG同组织")
    @GetMapping
    public Result<List<KbResponse>> list() {
        List<KbResponse> list = knowledgeBaseService.listByUser();
        return Result.success(list);
    }

    @Operation(summary = "获取知识库详情", description = "根据 ID 查看知识库详情，需通过权限校验")
    @GetMapping("/{id}")
    public Result<KbResponse> getById(
            @Parameter(description = "知识库 ID", required = true) @PathVariable Long id) {
        KbResponse kb = knowledgeBaseService.getById(id);
        return Result.success(kb);
    }

    @Operation(summary = "更新知识库", description = "更新知识库信息，仅 owner 或 admin 可操作")
    @PutMapping("/{id}")
    public Result<KbResponse> update(
            @Parameter(description = "知识库 ID", required = true) @PathVariable Long id,
            @Valid @RequestBody KbUpdateRequest request) {
        KbResponse kb = knowledgeBaseService.update(id, request);
        return Result.success(kb);
    }

    @Operation(summary = "删除知识库（软删除）", description = "软删除知识库，仅 owner 或 admin 可操作")
    @DeleteMapping("/{id}")
    public Result<Void> delete(
            @Parameter(description = "知识库 ID", required = true) @PathVariable Long id) {
        knowledgeBaseService.delete(id);
        return Result.success();
    }
}
