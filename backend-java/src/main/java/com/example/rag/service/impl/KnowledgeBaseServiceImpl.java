package com.example.rag.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.example.rag.common.BusinessException;
import com.example.rag.common.SecurityUtils;
import com.example.rag.dto.request.KbCreateRequest;
import com.example.rag.dto.request.KbUpdateRequest;
import com.example.rag.dto.response.KbResponse;
import com.example.rag.entity.KnowledgeBase;
import com.example.rag.mapper.KnowledgeBaseMapper;
import com.example.rag.service.KnowledgeBaseService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.util.StringUtils;

import java.time.LocalDateTime;
import java.util.List;

/**
 * 知识库服务实现
 *
 * <p>核心权限过滤 SQL 逻辑：
 * <pre>
 * 当前用户能看到的知识库：
 *   owner_id = 自己
 *   OR visibility = 'PUBLIC'
 *   OR (visibility = 'ORG' AND org_id = 自己的 org_id)
 * </pre>
 * ADMIN 角色绕过权限过滤，可查看所有未删除的知识库。
 *
 * @author knowledge-rag-team
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class KnowledgeBaseServiceImpl implements KnowledgeBaseService {

    private final KnowledgeBaseMapper knowledgeBaseMapper;

    // ==================== 可见范围常量 ====================
    private static final String VISIBILITY_PRIVATE = "PRIVATE";
    private static final String VISIBILITY_PUBLIC = "PUBLIC";
    private static final String VISIBILITY_ORG = "ORG";

    // ==================== 创建知识库 ====================

    @Override
    @Transactional
    public KbResponse create(KbCreateRequest request) {
        // 1. 校验可见范围
        validateVisibility(request.getVisibility(), request.getOrgId());

        // 2. 获取当前用户
        Long currentUserId = SecurityUtils.getCurrentUserId();

        // 3. 构建实体
        KnowledgeBase kb = new KnowledgeBase();
        kb.setName(request.getName());
        kb.setDescription(request.getDescription());
        kb.setVisibility(request.getVisibility().toUpperCase());
        kb.setOrgId(request.getOrgId());
        kb.setOwnerId(currentUserId);
        kb.setCreateTime(LocalDateTime.now());
        kb.setUpdateTime(LocalDateTime.now());

        // 4. 插入
        knowledgeBaseMapper.insert(kb);
        log.info("知识库创建成功: id={}, name={}, ownerId={}, visibility={}",
                kb.getId(), kb.getName(), kb.getOwnerId(), kb.getVisibility());

        return KbResponse.from(kb);
    }

    // ==================== 列出当前用户可见的知识库 ====================

    @Override
    public List<KbResponse> listByUser() {
        // ADMIN 可查看所有未删除的知识库
        if (SecurityUtils.isAdmin()) {
            List<KnowledgeBase> list = knowledgeBaseMapper.selectList(
                    new LambdaQueryWrapper<KnowledgeBase>()
                            .orderByDesc(KnowledgeBase::getCreateTime)
            );
            return list.stream().map(KbResponse::from).toList();
        }

        // 普通用户：权限过滤
        Long currentUserId = SecurityUtils.getCurrentUserId();
        Long currentOrgId = SecurityUtils.getCurrentUserOrgId();

        LambdaQueryWrapper<KnowledgeBase> wrapper = new LambdaQueryWrapper<>();
        // owner_id = 自己
        // OR visibility = 'PUBLIC'
        // OR (visibility = 'ORG' AND org_id = 自己的 org_id)
        wrapper.and(w -> w
                .eq(KnowledgeBase::getOwnerId, currentUserId)
                .or()
                .eq(KnowledgeBase::getVisibility, VISIBILITY_PUBLIC)
                .or()
                .and(w2 -> w2
                        .eq(KnowledgeBase::getVisibility, VISIBILITY_ORG)
                        .eq(KnowledgeBase::getOrgId, currentOrgId)
                )
        );
        wrapper.orderByDesc(KnowledgeBase::getCreateTime);

        List<KnowledgeBase> list = knowledgeBaseMapper.selectList(wrapper);
        log.debug("权限过滤查询: userId={}, orgId={}, 结果数={}",
                currentUserId, currentOrgId, list.size());

        return list.stream().map(KbResponse::from).toList();
    }

    // ==================== 获取单个知识库 ====================

    @Override
    public KbResponse getById(Long kbId) {
        KnowledgeBase kb = knowledgeBaseMapper.selectById(kbId);
        if (kb == null) {
            throw new BusinessException(404, "知识库不存在");
        }

        // 权限校验
        checkViewPermission(kb, "查看");

        return KbResponse.from(kb);
    }

    // ==================== 更新知识库 ====================

    @Override
    @Transactional
    public KbResponse update(Long kbId, KbUpdateRequest request) {
        KnowledgeBase kb = knowledgeBaseMapper.selectById(kbId);
        if (kb == null) {
            throw new BusinessException(404, "知识库不存在");
        }

        // 仅 owner 或 admin 可编辑
        checkOwnerOrAdmin(kb, "编辑");

        // 更新非 null 字段
        boolean changed = false;
        if (StringUtils.hasText(request.getName())) {
            kb.setName(request.getName());
            changed = true;
        }
        if (request.getDescription() != null) {
            kb.setDescription(request.getDescription());
            changed = true;
        }
        if (StringUtils.hasText(request.getVisibility())) {
            validateVisibility(request.getVisibility(), request.getOrgId());
            kb.setVisibility(request.getVisibility().toUpperCase());
            changed = true;
        }
        if (request.getOrgId() != null) {
            kb.setOrgId(request.getOrgId());
            changed = true;
        }

        if (changed) {
            kb.setUpdateTime(LocalDateTime.now());
            knowledgeBaseMapper.updateById(kb);
            log.info("知识库更新成功: id={}, name={}", kb.getId(), kb.getName());
        }

        return KbResponse.from(kb);
    }

    // ==================== 软删除知识库 ====================

    @Override
    @Transactional
    public void delete(Long kbId) {
        KnowledgeBase kb = knowledgeBaseMapper.selectById(kbId);
        if (kb == null) {
            throw new BusinessException(404, "知识库不存在");
        }

        // 仅 owner 或 admin 可删除
        checkOwnerOrAdmin(kb, "删除");

        // MyBatis-Plus @TableLogic 自动将 deleteById 转为软删除（UPDATE is_deleted = 1）
        knowledgeBaseMapper.deleteById(kbId);
        log.info("知识库已软删除: id={}, name={}", kb.getId(), kb.getName());
    }

    // ==================== 私有辅助方法 ====================

    /**
     * 校验可见范围合法性
     */
    private void validateVisibility(String visibility, Long orgId) {
        String upper = visibility != null ? visibility.toUpperCase() : "";
        if (!VISIBILITY_PRIVATE.equals(upper)
                && !VISIBILITY_PUBLIC.equals(upper)
                && !VISIBILITY_ORG.equals(upper)) {
            throw new BusinessException(400,
                    "无效的可见范围: " + visibility + "，可选值: PRIVATE / PUBLIC / ORG");
        }
        if (VISIBILITY_ORG.equals(upper) && orgId == null) {
            throw new BusinessException(400, "可见范围为 ORG 时，所属组织 ID 不能为空");
        }
    }

    /**
     * 权限校验：仅 owner 或 admin 可编辑/删除
     */
    private void checkOwnerOrAdmin(KnowledgeBase kb, String action) {
        if (SecurityUtils.isAdmin()) {
            return;
        }
        Long currentUserId = SecurityUtils.getCurrentUserId();
        if (!kb.getOwnerId().equals(currentUserId)) {
            throw new BusinessException(403,
                    "无权" + action + "该知识库，仅知识库创建者或管理员可操作");
        }
    }

    /**
     * 查看权限校验：owner / admin / PUBLIC / ORG成员 可查看
     */
    private void checkViewPermission(KnowledgeBase kb, String action) {
        if (SecurityUtils.isAdmin()) {
            return;
        }
        Long currentUserId = SecurityUtils.getCurrentUserId();
        Long currentOrgId = SecurityUtils.getCurrentUserOrgId();

        // owner 可查看
        if (kb.getOwnerId().equals(currentUserId)) {
            return;
        }
        // PUBLIC 任何人可查看
        if (VISIBILITY_PUBLIC.equals(kb.getVisibility())) {
            return;
        }
        // ORG 同组织成员可查看
        if (VISIBILITY_ORG.equals(kb.getVisibility())
                && kb.getOrgId() != null
                && kb.getOrgId().equals(currentOrgId)) {
            return;
        }

        throw new BusinessException(403, "无权" + action + "该知识库");
    }
}
