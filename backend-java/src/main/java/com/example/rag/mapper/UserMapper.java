package com.example.rag.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.example.rag.entity.User;
import org.apache.ibatis.annotations.Mapper;

/**
 * 用户表 Mapper
 *
 * @author knowledge-rag-team
 */
@Mapper
public interface UserMapper extends BaseMapper<User> {
}
