package com.example.rag.controller;

import com.example.rag.common.Result;
import com.example.rag.common.SecurityUtils;
import com.example.rag.dto.request.LoginRequest;
import com.example.rag.dto.request.RegisterRequest;
import com.example.rag.dto.response.LoginResponse;
import com.example.rag.dto.response.UserResponse;
import com.example.rag.service.UserService;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;

/**
 * 认证接口
 *
 * @author knowledge-rag-team
 */
@Tag(name = "认证管理", description = "用户注册 / 登录 / 个人信息")
@RestController
@RequestMapping("/api/auth")
@RequiredArgsConstructor
public class AuthController {

    private final UserService userService;

    @Operation(summary = "用户注册")
    @PostMapping("/register")
    public Result<UserResponse> register(@Valid @RequestBody RegisterRequest request) {
        UserResponse user = userService.register(request);
        return Result.success(user);
    }

    @Operation(summary = "用户登录")
    @PostMapping("/login")
    public Result<LoginResponse> login(@Valid @RequestBody LoginRequest request) {
        LoginResponse resp = userService.login(request);
        return Result.success(resp);
    }

    @Operation(summary = "获取当前登录用户信息")
    @GetMapping("/profile")
    public Result<UserResponse> profile() {
        Long userId = SecurityUtils.getCurrentUserId();
        UserResponse user = userService.getProfile(userId);
        return Result.success(user);
    }
}
