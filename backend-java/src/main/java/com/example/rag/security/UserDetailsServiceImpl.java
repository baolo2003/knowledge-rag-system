package com.example.rag.security;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.example.rag.entity.User;
import com.example.rag.mapper.UserMapper;
import lombok.RequiredArgsConstructor;
import org.springframework.security.core.userdetails.UserDetails;
import org.springframework.security.core.userdetails.UserDetailsService;
import org.springframework.security.core.userdetails.UsernameNotFoundException;
import org.springframework.stereotype.Service;

import java.util.List;

/**
 * Spring Security 用户加载服务
 *
 * <p>从数据库加载用户信息，用于 Spring Security 的认证流程。</p>
 *
 * @author knowledge-rag-team
 */
@Service
@RequiredArgsConstructor
public class UserDetailsServiceImpl implements UserDetailsService {

    private final UserMapper userMapper;

    @Override
    public UserDetails loadUserByUsername(String username) throws UsernameNotFoundException {
        User user = userMapper.selectOne(
                new LambdaQueryWrapper<User>()
                        .eq(User::getUsername, username)
                        .last("LIMIT 1")
        );

        if (user == null) {
            throw new UsernameNotFoundException("用户不存在: " + username);
        }

        if (user.getStatus() != null && user.getStatus() == 0) {
            throw new UsernameNotFoundException("用户已被禁用: " + username);
        }

        return new org.springframework.security.core.userdetails.User(
                String.valueOf(user.getId()),          // principal = userId 字符串
                user.getPassword(),                    // BCrypt 密文
                true,                                  // enabled
                true,                                  // accountNonExpired
                true,                                  // credentialsNonExpired
                true,                                  // accountNonLocked
                List.of(new org.springframework.security.core.authority
                        .SimpleGrantedAuthority("ROLE_" + user.getRole()))
        );
    }
}
