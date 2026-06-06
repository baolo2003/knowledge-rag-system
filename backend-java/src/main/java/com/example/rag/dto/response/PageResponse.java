package com.example.rag.dto.response;

import com.baomidou.mybatisplus.core.metadata.IPage;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.util.List;
import java.util.function.Function;

/**
 * 分页响应 DTO
 *
 * <p>统一分页返回格式，包含分页元数据和数据列表。</p>
 *
 * @param <T> 数据项类型
 * @author knowledge-rag-team
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class PageResponse<T> {

    /** 当前页码（从 1 开始） */
    private long page;

    /** 每页条数 */
    private long size;

    /** 总记录数 */
    private long total;

    /** 总页数 */
    private long pages;

    /** 数据列表 */
    private List<T> records;

    /**
     * 从 MyBatis-Plus IPage 转换
     *
     * @param page    MyBatis-Plus 分页对象
     * @param mapper  实体 → DTO 转换函数
     */
    public static <T, E> PageResponse<T> from(IPage<E> page, Function<E, T> mapper) {
        return PageResponse.<T>builder()
                .page(page.getCurrent())
                .size(page.getSize())
                .total(page.getTotal())
                .pages(page.getPages())
                .records(page.getRecords().stream().map(mapper).toList())
                .build();
    }
}
