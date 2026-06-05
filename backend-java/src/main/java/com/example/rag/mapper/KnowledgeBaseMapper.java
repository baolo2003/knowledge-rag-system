package com.example.rag.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.example.rag.entity.KnowledgeBase;
import org.apache.ibatis.annotations.Mapper;

/**
 * 知识库表 Mapper
 *
 * @author knowledge-rag-team
 */
@Mapper
public interface KnowledgeBaseMapper extends BaseMapper<KnowledgeBase> {
}
