package com.forge.hv.controller;

import com.forge.hv.entity.User;
import com.forge.hv.repository.UserRepository;
import com.forge.hv.security.AuthUser;
import com.forge.hv.service.AuthService;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.*;

import java.util.Map;

@RestController
@RequestMapping("/api/auth")
public class AuthController {

    private final AuthService authService;
    private final UserRepository userRepository;

    public AuthController(AuthService authService, UserRepository userRepository) {
        this.authService = authService;
        this.userRepository = userRepository;
    }

    @PostMapping("/login")
    public ResponseEntity<?> login(@RequestBody(required = false) Map<String, String> body) {
        if (body == null) {
            return ResponseEntity.status(401).body(Map.of("error", "用户名或密码错误"));
        }
        try {
            return ResponseEntity.ok(authService.login(body.get("username"), body.get("password")));
        } catch (IllegalArgumentException e) {
            return ResponseEntity.status(401).body(Map.of("error", e.getMessage()));
        }
    }

    @PostMapping("/guest")
    public ResponseEntity<?> guest() {
        try {
            return ResponseEntity.ok(authService.guestLogin());
        } catch (IllegalStateException e) {
            return ResponseEntity.status(403).body(Map.of("error", e.getMessage()));
        }
    }

    @PostMapping("/register")
    public ResponseEntity<?> register(@RequestBody(required = false) Map<String, String> body) {
        if (body == null) {
            return ResponseEntity.badRequest().body(Map.of("error", "请求体不能为空"));
        }
        try {
            return ResponseEntity.ok(authService.register(
                    body.get("username"), body.get("password"),
                    body.get("display_name"), body.get("email")));
        } catch (IllegalStateException | IllegalArgumentException e) {
            int code = e.getMessage() != null && e.getMessage().contains("已存在") ? 409 : 400;
            return ResponseEntity.status(code).body(Map.of("error", e.getMessage()));
        }
    }

    @GetMapping("/me")
    public ResponseEntity<?> me(@AuthenticationPrincipal AuthUser user) {
        if (user == null) {
            return ResponseEntity.status(401).body(Map.of("error", "未登录"));
        }
        if (user.userId() == 0L) {
            return ResponseEntity.ok(Map.of("user", Map.of(
                    "id", 0,
                    "user_id", 0,
                    "username", "guest",
                    "role", "guest",
                    "display_name", "游客"
            )));
        }
        User db = userRepository.findById(user.userId()).orElse(null);
        String display = db != null && db.getDisplayName() != null && !db.getDisplayName().isBlank()
                ? db.getDisplayName()
                : user.username();
        return ResponseEntity.ok(Map.of("user", Map.of(
                "id", user.userId(),
                "user_id", user.userId(),
                "username", user.username(),
                "role", user.role(),
                "display_name", display
        )));
    }

    @PostMapping("/change_password")
    public ResponseEntity<?> changePassword(@AuthenticationPrincipal AuthUser authUser,
                                            @RequestBody(required = false) Map<String, String> body) {
        if (authUser == null || authUser.userId() == 0L) {
            return ResponseEntity.status(403).body(Map.of("error", "游客无法修改密码"));
        }
        if (body == null) {
            return ResponseEntity.badRequest().body(Map.of("error", "请求体不能为空"));
        }
        User user = userRepository.findById(authUser.userId())
                .orElseThrow(() -> new IllegalArgumentException("用户不存在"));
        try {
            authService.changePassword(user, body.get("old_password"), body.get("new_password"));
            return ResponseEntity.ok(Map.of("status", "ok"));
        } catch (IllegalArgumentException e) {
            return ResponseEntity.status(401).body(Map.of("error", e.getMessage()));
        }
    }
}
