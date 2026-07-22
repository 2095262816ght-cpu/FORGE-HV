package com.forge.hv.controller;

import com.forge.hv.security.AuthUser;
import com.forge.hv.service.SettingsService;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.*;

import java.util.Map;

@RestController
@RequestMapping("/api/settings")
public class SettingsController {

    private final SettingsService settingsService;

    public SettingsController(SettingsService settingsService) {
        this.settingsService = settingsService;
    }

    @GetMapping
    public Map<String, Object> get() {
        return Map.of("settings", settingsService.getAll());
    }

    @PutMapping
    public ResponseEntity<?> update(@AuthenticationPrincipal AuthUser user,
                                    @RequestBody Map<String, Object> body) {
        @SuppressWarnings("unchecked")
        Map<String, String> settings = (Map<String, String>) body.get("settings");
        if (settings == null) {
            return ResponseEntity.badRequest().body(Map.of("error", "settings 必须是对象"));
        }
        String updatedBy = user == null ? "system" : user.username();
        return ResponseEntity.ok(Map.of("settings", settingsService.update(settings, updatedBy)));
    }
}
