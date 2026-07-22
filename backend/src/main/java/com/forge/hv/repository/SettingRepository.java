package com.forge.hv.repository;

import com.forge.hv.entity.SettingEntity;
import org.springframework.data.jpa.repository.JpaRepository;

public interface SettingRepository extends JpaRepository<SettingEntity, String> {
}
