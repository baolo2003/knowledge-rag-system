package com.example.rag.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.example.rag.entity.Document;
import org.apache.ibatis.annotations.Mapper;

/**
 * 文档表 Mapper
 *
 * @author knowledge-rag-team
 */
@Mapper
public interface DocumentMapper extends BaseMapper<Document> {
}
