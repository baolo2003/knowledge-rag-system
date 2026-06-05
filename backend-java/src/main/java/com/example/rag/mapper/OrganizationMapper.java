package com.example.rag.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.example.rag.entity.Organization;
import org.apache.ibatis.annotations.Mapper;

/**
 * 组织表 Mapper
 *
 * @author knowledge-rag-team
 */
@Mapper
public interface OrganizationMapper extends BaseMapper<Organization> {
}
