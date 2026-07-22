package com.forge.hv.service;

import com.forge.hv.entity.User;
import com.forge.hv.repository.UserRepository;
import com.forge.hv.security.JwtUtil;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;
import java.util.HashMap;
import java.util.Map;
import java.util.Set;

@Service
public class AuthService {

    private static final Set<String> RESERVED = Set.of(
            "admin", "root", "guest", "system", "administrator", "superuser"
    );

    private final UserRepository userRepository;
    private final JwtUtil jwtUtil;
    private final SettingsService settingsService;
    private final PasswordService passwordService;

    public AuthService(UserRepository userRepository, JwtUtil jwtUtil,
                       SettingsService settingsService, PasswordService passwordService) {
        this.userRepository = userRepository;
        this.jwtUtil = jwtUtil;
        this.settingsService = settingsService;
        this.passwordService = passwordService;
    }

    @Transactional
    public Map<String, Object> login(String username, String password) {
        if (username == null || username.isBlank() || password == null) {
            throw new IllegalArgumentException("用户名或密码错误");
        }
        User user = userRepository.findByUsernameIgnoreCase(username.trim())
                .orElseThrow(() -> new IllegalArgumentException("用户名或密码错误"));
        if (!passwordService.matches(user, password)) {
            throw new IllegalArgumentException("用户名或密码错误");
        }
        if (passwordService.upgradeIfLegacy(user, password)) {
            // 已写入新哈希，随 last_login 一并保存
        }
        user.setLastLogin(LocalDateTime.now());
        userRepository.save(user);
        return buildAuthResponse(user);
    }

    public Map<String, Object> guestLogin() {
        if (!settingsService.isGuestEnabled()) {
            throw new IllegalStateException("管理员未开放游客浏览，请登录");
        }
        String token = jwtUtil.generateToken(0L, "guest", "guest");
        return Map.of(
                "token", token,
                "user", Map.of(
                        "id", 0,
                        "username", "guest",
                        "role", "guest",
                        "display_name", "游客",
                        "email", ""
                )
        );
    }

    @Transactional
    public Map<String, Object> register(String username, String password, String displayName, String email) {
        if (!settingsService.isRegisterEnabled()) {
            throw new IllegalStateException("管理员已关闭注册功能");
        }
        if (username == null || password == null) {
            throw new IllegalArgumentException("用户名和密码不能为空");
        }
        username = username.trim();
        validateUsername(username);
        validatePassword(password);
        if (userRepository.existsByUsernameIgnoreCase(username)) {
            throw new IllegalArgumentException("用户名已存在");
        }
        String role = settingsService.getDefaultRegisterRole();
        if (!"user".equals(role) && !"guest".equals(role)) {
            role = "user";
        }
        User user = new User();
        user.setUsername(username);
        passwordService.setPassword(user, password);
        user.setRole(role);
        user.setDisplayName(displayName == null || displayName.isBlank() ? username : displayName.trim());
        user.setEmail(email == null || email.isBlank() ? null : email.trim());
        userRepository.save(user);
        Map<String, Object> resp = new HashMap<>(buildAuthResponse(user));
        resp.put("message", "注册成功");
        return resp;
    }

    @Transactional
    public void changePassword(User user, String oldPassword, String newPassword) {
        if (oldPassword == null || !passwordService.matches(user, oldPassword)) {
            throw new IllegalArgumentException("原密码错误");
        }
        validatePassword(newPassword);
        passwordService.setPassword(user, newPassword);
        userRepository.save(user);
    }

    private Map<String, Object> buildAuthResponse(User user) {
        String token = jwtUtil.generateToken(user.getId(), user.getUsername(), user.getRole());
        return Map.of(
                "token", token,
                "user", Map.of(
                        "id", user.getId(),
                        "username", user.getUsername(),
                        "role", user.getRole(),
                        "display_name", user.getDisplayName() == null ? user.getUsername() : user.getDisplayName(),
                        "email", user.getEmail() == null ? "" : user.getEmail()
                )
        );
    }

    private void validateUsername(String username) {
        if (username.length() < 3 || username.length() > 20) {
            throw new IllegalArgumentException("用户名长度需 3-20 个字符");
        }
        if (!username.chars().allMatch(c -> Character.isLetterOrDigit(c) || c == '_')) {
            throw new IllegalArgumentException("用户名只能含字母、数字、下划线");
        }
        if (RESERVED.contains(username.toLowerCase())) {
            throw new IllegalArgumentException("该用户名为系统保留名");
        }
    }

    private void validatePassword(String password) {
        if (password == null || password.length() < 6 || password.length() > 64) {
            throw new IllegalArgumentException("密码长度需 6-64 个字符");
        }
    }
}
