package com.example.rag.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.example.rag.entity.Conversation;
import org.apache.ibatis.annotations.Mapper;

/**
 * 会话表 Mapper
 *
 * @author knowledge-rag-team
 */
@Mapper
public interface ConversationMapper extends BaseMapper<Conversation> {
}
