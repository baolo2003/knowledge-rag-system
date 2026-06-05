package com.example.rag.service;

import com.example.rag.dto.request.LoginRequest;
import com.example.rag.dto.request.RegisterRequest;
import com.example.rag.dto.response.LoginResponse;
import com.example.rag.dto.response.UserResponse;

/**
 * 用户服务接口
 *
 * @author knowledge-rag-team
 */
public interface UserService {

    /** 用户注册 */
    UserResponse register(RegisterRequest request);

    /** 用户登录 */
    LoginResponse login(LoginRequest request);

    /** 获取当前用户信息 */
    UserResponse getProfile(Long userId);
}
