package com.example.rag.common;

import lombok.Getter;

/**
 * 业务异常类
 *
 * <p>在 Service 层遇到业务逻辑错误时抛出此异常，
 * 由 {@link GlobalExceptionHandler} 统一捕获并转为 Result 响应。</p>
 *
 * <pre>
 * 使用示例：
 *   throw new BusinessException("用户名已存在");
 *   throw new BusinessException(403, "无权访问该知识库");
 *   throw new BusinessException(404, "文档不存在");
 * </pre>
 *
 * @author knowledge-rag-team
 */
@Getter
public class BusinessException extends RuntimeException {

    /** 业务状态码（500 为默认，可用 4xx 系列） */
    private final int code;

    /**
     * 默认构造：code = 500
     *
     * @param message 错误描述
     */
    public BusinessException(String message) {
        super(message);
        this.code = 500;
    }

    /**
     * 自定义 code
     *
     * @param code    业务状态码（如 400 / 403 / 404）
     * @param message 错误描述
     */
    public BusinessException(int code, String message) {
        super(message);
        this.code = code;
    }

    /**
     * 带 cause 的异常
     *
     * @param code    业务状态码
     * @param message 错误描述
     * @param cause   原始异常
     */
    public BusinessException(int code, String message, Throwable cause) {
        super(message, cause);
        this.code = code;
    }
}
