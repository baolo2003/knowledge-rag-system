package com.example.rag.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.example.rag.common.BusinessException;
import com.example.rag.dto.request.LoginRequest;
import com.example.rag.dto.request.RegisterRequest;
import com.example.rag.dto.response.LoginResponse;
import com.example.rag.dto.response.UserResponse;
import com.example.rag.entity.User;
import com.example.rag.mapper.UserMapper;
import com.example.rag.security.JwtTokenProvider;
import com.example.rag.service.UserService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;

/**
 * 用户服务实现
 *
 * @author knowledge-rag-team
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class UserServiceImpl implements UserService {

    private final UserMapper userMapper;
    private final PasswordEncoder passwordEncoder;
    private final JwtTokenProvider jwtTokenProvider;

    @Value("${jwt.access-token-expire}")
    private long accessTokenExpire;

    @Override
    @Transactional
    public UserResponse register(RegisterRequest request) {
        // 1. 校验用户名是否已存在
        Long count = userMapper.selectCount(
                new LambdaQueryWrapper<User>()
                        .eq(User::getUsername, request.getUsername())
        );
        if (count > 0) {
            throw new BusinessException("用户名已存在");
        }

        // 2. 创建用户
        User user = new User();
        user.setUsername(request.getUsername());
        user.setPassword(passwordEncoder.encode(request.getPassword()));
        user.setEmail(request.getEmail());
        user.setRole("USER");
        user.setStatus(1);
        user.setCreateTime(LocalDateTime.now());
        user.setUpdateTime(LocalDateTime.now());

        userMapper.insert(user);
        log.info("用户注册成功: username={}, id={}", user.getUsername(), user.getId());

        return UserResponse.from(user);
    }

    @Override
    public LoginResponse login(LoginRequest request) {
        // 1. 查询用户
        User user = userMapper.selectOne(
                new LambdaQueryWrapper<User>()
                        .eq(User::getUsername, request.getUsername())
                        .last("LIMIT 1")
        );
        if (user == null) {
            throw new BusinessException("用户名或密码错误");
        }

        // 2. 校验状态
        if (user.getStatus() == 0) {
            throw new BusinessException(403, "账号已被禁用，请联系管理员");
        }

        // 3. 校验密码
        if (!passwordEncoder.matches(request.getPassword(), user.getPassword())) {
            throw new BusinessException("用户名或密码错误");
        }

        // 4. 生成 Token
        String accessToken = jwtTokenProvider.createAccessToken(
                user.getId(), user.getUsername(), user.getRole(), user.getOrgId());
        String refreshToken = jwtTokenProvider.createRefreshToken(
                user.getId(), user.getUsername(), user.getRole(), user.getOrgId());

        log.info("用户登录成功: username={}, id={}", user.getUsername(), user.getId());

        return LoginResponse.of(accessToken, refreshToken,
                accessTokenExpire, UserResponse.from(user));
    }

    @Override
    public UserResponse getProfile(Long userId) {
        User user = userMapper.selectById(userId);
        if (user == null) {
            throw new BusinessException(404, "用户不存在");
        }
        return UserResponse.from(user);
    }
}
