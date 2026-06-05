package com.example.rag.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.example.rag.entity.Message;
import org.apache.ibatis.annotations.Mapper;

/**
 * 消息表 Mapper
 *
 * @author knowledge-rag-team
 */
@Mapper
public interface MessageMapper extends BaseMapper<Message> {
}
