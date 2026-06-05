package com.example.rag.common;

import lombok.extern.slf4j.Slf4j;
import org.springframework.web.bind.MethodArgumentNotValidException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;

import java.util.stream.Collectors;

/**
 * 全局异常处理器
 *
 * <p>统一拦截 Controller 层抛出的异常，转为 {@link Result} 格式返回，
 * 避免异常信息直接暴露给前端。</p>
 *
 * @author knowledge-rag-team
 */
@Slf4j
@RestControllerAdvice
public class GlobalExceptionHandler {

    /**
     * 业务异常
     * <p>直接使用异常中携带的 code 和 message 构造响应</p>
     */
    @ExceptionHandler(BusinessException.class)
    public Result<?> handleBusinessException(BusinessException e) {
        log.warn("业务异常: code={}, message={}", e.getCode(), e.getMessage());
        return Result.error(e);
    }

    /**
     * 参数校验异常（@Valid 触发）
     * <p>拼装所有字段校验失败信息，返回 400</p>
     */
    @ExceptionHandler(MethodArgumentNotValidException.class)
    public Result<?> handleValidationException(MethodArgumentNotValidException e) {
        String msg = e.getBindingResult().getFieldErrors().stream()
                .map(f -> f.getField() + ": " + f.getDefaultMessage())
                .collect(Collectors.joining("; "));
        log.warn("参数校验失败: {}", msg);
        return Result.error(400, msg);
    }

    /**
     * 兜底异常
     * <p>捕获所有未被上述处理器拦截的异常，返回 500，隐藏内部细节</p>
     */
    @ExceptionHandler(Exception.class)
    public Result<?> handleException(Exception e) {
        log.error("未知异常", e);
        return Result.error(500, "服务器内部错误，请稍后重试");
    }
}
