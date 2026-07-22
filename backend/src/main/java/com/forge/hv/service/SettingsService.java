package com.forge.hv.service;

import com.forge.hv.entity.SettingEntity;
import com.forge.hv.repository.SettingRepository;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;
import java.util.LinkedHashMap;
import java.util.Map;

@Service
public class SettingsService {

    private static final Map<String, String> DEFAULTS = Map.of(
            "site_title", "FORGE 高温合金机器学习实验台",
            "default_data_source", "real",
            "allow_guest_browse", "true",
            "allow_register", "true",
            "default_register_role", "user",
            "max_upload_size_mb", "50",
            "history_retention_days", "365"
    );

    private final SettingRepository settingRepository;

    public SettingsService(SettingRepository settingRepository) {
        this.settingRepository = settingRepository;
    }

    public Map<String, String> getAll() {
        Map<String, String> merged = new LinkedHashMap<>(DEFAULTS);
        settingRepository.findAll().forEach(s -> merged.put(s.getKey(), s.getValue()));
        return merged;
    }

    public boolean isGuestEnabled() {
        return "true".equalsIgnoreCase(getAll().get("allow_guest_browse"));
    }

    public boolean isRegisterEnabled() {
        return "true".equalsIgnoreCase(getAll().get("allow_register"));
    }

    public String getDefaultRegisterRole() {
        String role = getAll().get("default_register_role");
        return "guest".equals(role) ? "guest" : "user";
    }

    @Transactional
    public Map<String, String> update(Map<String, String> updates, String updatedBy) {
        updates.forEach((key, value) -> {
            SettingEntity entity = settingRepository.findById(key).orElseGet(SettingEntity::new);
            entity.setKey(key);
            entity.setValue(value);
            entity.setUpdatedBy(updatedBy);
            entity.setUpdatedAt(LocalDateTime.now());
            settingRepository.save(entity);
        });
        return getAll();
    }
}
