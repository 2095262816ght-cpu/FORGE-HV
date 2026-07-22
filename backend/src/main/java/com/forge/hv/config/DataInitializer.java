package com.forge.hv.config;

import com.forge.hv.entity.SettingEntity;
import com.forge.hv.entity.User;
import com.forge.hv.repository.SettingRepository;
import com.forge.hv.repository.UserRepository;
import com.forge.hv.service.PasswordService;
import org.springframework.boot.CommandLineRunner;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

import java.time.LocalDateTime;
import java.util.Map;

@Configuration
public class DataInitializer {

    private static final Map<String, String> DEFAULT_SETTINGS = Map.of(
            "site_title", "FORGE 高温合金机器学习实验台",
            "default_data_source", "real",
            "allow_guest_browse", "true",
            "allow_register", "true",
            "default_register_role", "user",
            "max_upload_size_mb", "50",
            "history_retention_days", "365"
    );

    @Bean
    CommandLineRunner initData(UserRepository userRepository,
                               SettingRepository settingRepository,
                               PasswordService passwordService) {
        return args -> {
            if (userRepository.count() == 0) {
                User admin = new User();
                admin.setUsername("admin");
                passwordService.setPassword(admin, "admin123");
                admin.setRole("admin");
                admin.setDisplayName("管理员");
                admin.setEmail("admin@forge.local");
                userRepository.save(admin);
                System.out.println("[init] 已创建默认管理员账号 admin / admin123（请尽快修改密码）");
            }
            DEFAULT_SETTINGS.forEach((key, value) -> {
                if (settingRepository.findById(key).isEmpty()) {
                    SettingEntity s = new SettingEntity();
                    s.setKey(key);
                    s.setValue(value);
                    s.setUpdatedBy("system");
                    s.setUpdatedAt(LocalDateTime.now());
                    settingRepository.save(s);
                }
            });
        };
    }
}
