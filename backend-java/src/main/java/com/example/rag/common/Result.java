package com.example.rag.common;

import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;

/**
 * 统一响应格式
 *
 * <pre>
 * 实际返回示例：
 * {
 *   "code": 200,
 *   "message": "success",
 *   "data": { "id": 1, "username": "zhangsan" },
 *   "timestamp": 1717584000000
 * }
 * </pre>
 *
 * @author knowledge-rag-team
 */
@Data
@NoArgsConstructor
@AllArgsConstructor
public class Result<T> {

    /** 状态码（200 成功，4xx 客户端错误，5xx 服务端错误） */
    private int code;

    /** 提示信息 */
    private String message;

    /** 响应数据 */
    private T data;

    /** 时间戳（毫秒） */
    private long timestamp;

    // ==================== 成功响应 ====================

    /** 成功 + 数据 */
    public static <T> Result<T> success(T data) {
        return new Result<>(200, "success", data, System.currentTimeMillis());
    }

    /** 成功 + 自定义消息 + 数据 */
    public static <T> Result<T> success(String message, T data) {
        return new Result<>(200, message, data, System.currentTimeMillis());
    }

    /** 成功（无数据） */
    public static <T> Result<T> success() {
        return success(null);
    }

    // ==================== 失败响应 ====================

    /** 失败：自定义 code + message */
    public static <T> Result<T> error(int code, String message) {
        return new Result<>(code, message, null, System.currentTimeMillis());
    }

    /** 失败：默认 500 + message */
    public static <T> Result<T> error(String message) {
        return error(500, message);
    }

    /** 失败：业务异常（直接传入 BusinessException） */
    public static <T> Result<T> error(BusinessException e) {
        return error(e.getCode(), e.getMessage());
    }
}
