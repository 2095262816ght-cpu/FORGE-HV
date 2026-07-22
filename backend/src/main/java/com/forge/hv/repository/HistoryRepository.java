package com.forge.hv.repository;

import com.forge.hv.entity.History;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.JpaSpecificationExecutor;

public interface HistoryRepository extends JpaRepository<History, Long>, JpaSpecificationExecutor<History> {
}
