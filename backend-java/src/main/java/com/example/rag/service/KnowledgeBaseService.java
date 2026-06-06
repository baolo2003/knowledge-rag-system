package com.example.rag.service;

import com.example.rag.dto.request.KbCreateRequest;
import com.example.rag.dto.request.KbUpdateRequest;
import com.example.rag.dto.response.KbResponse;

import java.util.List;

/**
 * 知识库服务接口
 *
 * @author knowledge-rag-team
 */
public interface KnowledgeBaseService {

    /** 创建知识库（自动设置 owner_id 为当前用户） */
    KbResponse create(KbCreateRequest request);

    /**
     * 列出当前用户可见的知识库
     * <p>权限过滤：owner_id = 当前用户 OR visibility = 'PUBLIC'
     * OR (visibility = 'ORG' AND org_id = 当前用户 org_id)</p>
     * <p>ADMIN 角色可查看所有未删除的知识库</p>
     */
    List<KbResponse> listByUser();

    /** 根据 ID 获取知识库（需通过权限过滤） */
    KbResponse getById(Long kbId);

    /** 更新知识库（仅 owner 或 admin 可操作） */
    KbResponse update(Long kbId, KbUpdateRequest request);

    /** 软删除知识库（仅 owner 或 admin 可操作） */
    void delete(Long kbId);
}
