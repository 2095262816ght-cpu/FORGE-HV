package com.forge.hv.controller;

import com.forge.hv.entity.User;
import com.forge.hv.repository.UserRepository;
import com.forge.hv.service.PasswordService;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.time.LocalDateTime;
import java.util.List;
import java.util.Map;
import java.util.Set;

@RestController
@RequestMapping("/api/users")
public class UserController {

    private static final Set<String> ALLOWED_ROLES = Set.of("user", "admin", "guest");

    private final UserRepository userRepository;
    private final PasswordService passwordService;

    public UserController(UserRepository userRepository, PasswordService passwordService) {
        this.userRepository = userRepository;
        this.passwordService = passwordService;
    }

    @GetMapping
    public Map<String, Object> list(@RequestParam(defaultValue = "1") int page,
                                    @RequestParam(defaultValue = "50") int size,
                                    @RequestParam(required = false) String keyword) {
        List<Map<String, Object>> all = userRepository.findAll().stream()
                .filter(u -> keyword == null || keyword.isBlank()
                        || u.getUsername().toLowerCase().contains(keyword.toLowerCase())
                        || (u.getDisplayName() != null && u.getDisplayName().toLowerCase().contains(keyword.toLowerCase())))
                .map(this::toDto)
                .toList();
        int from = Math.max(0, (page - 1) * size);
        int to = Math.min(all.size(), from + size);
        List<Map<String, Object>> slice = from >= all.size() ? List.of() : all.subList(from, to);
        return Map.of("items", slice, "total", all.size(), "page", page, "size", size);
    }

    @PostMapping
    public ResponseEntity<?> create(@RequestBody Map<String, String> body) {
        String username = body.get("username");
        String password = body.get("password");
        if (username == null || username.isBlank()) {
            return ResponseEntity.badRequest().body(Map.of("error", "用户名不能为空"));
        }
        if (password == null || password.length() < 6) {
            return ResponseEntity.badRequest().body(Map.of("error", "密码至少 6 位"));
        }
        if (userRepository.existsByUsernameIgnoreCase(username)) {
            return ResponseEntity.status(409).body(Map.of("error", "用户名已存在"));
        }
        String role = body.getOrDefault("role", "user");
        if (!ALLOWED_ROLES.contains(role)) {
            role = "user";
        }
        User user = new User();
        user.setUsername(username.trim());
        passwordService.setPassword(user, password);
        user.setRole(role);
        user.setDisplayName(body.get("display_name"));
        user.setEmail(body.get("email"));
        userRepository.save(user);
        return ResponseEntity.ok(toDto(user));
    }

    @PutMapping("/{id}")
    public ResponseEntity<?> update(@PathVariable Long id, @RequestBody Map<String, String> body) {
        User user = userRepository.findById(id).orElseThrow();
        if (body.containsKey("role")) {
            String role = body.get("role");
            if (ALLOWED_ROLES.contains(role)) user.setRole(role);
        }
        if (body.containsKey("display_name")) user.setDisplayName(body.get("display_name"));
        if (body.containsKey("email")) user.setEmail(body.get("email"));
        if (body.containsKey("password") && body.get("password") != null && !body.get("password").isBlank()) {
            if (body.get("password").length() < 6) {
                return ResponseEntity.badRequest().body(Map.of("error", "密码至少 6 位"));
            }
            passwordService.setPassword(user, body.get("password"));
        }
        userRepository.save(user);
        return ResponseEntity.ok(toDto(user));
    }

    @DeleteMapping("/{id}")
    public ResponseEntity<?> delete(@PathVariable Long id) {
        userRepository.deleteById(id);
        return ResponseEntity.ok(Map.of("status", "ok"));
    }

    private Map<String, Object> toDto(User u) {
        return Map.of(
                "id", u.getId(),
                "username", u.getUsername(),
                "role", u.getRole(),
                "display_name", u.getDisplayName() == null ? u.getUsername() : u.getDisplayName(),
                "email", u.getEmail() == null ? "" : u.getEmail(),
                "created_at", u.getCreatedAt() == null ? LocalDateTime.now().toString() : u.getCreatedAt().toString(),
                "last_login", u.getLastLogin() == null ? "" : u.getLastLogin().toString()
        );
    }
}
