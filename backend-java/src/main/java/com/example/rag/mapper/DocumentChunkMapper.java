package com.example.rag.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.example.rag.entity.DocumentChunk;
import org.apache.ibatis.annotations.Mapper;

/**
 * 文档切片表 Mapper
 *
 * @author knowledge-rag-team
 */
@Mapper
public interface DocumentChunkMapper extends BaseMapper<DocumentChunk> {
}
