package com.forge.hv.service;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.forge.hv.entity.History;
import com.forge.hv.repository.HistoryRepository;
import org.springframework.data.jpa.domain.Specification;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDate;
import java.time.LocalDateTime;
import java.time.LocalTime;
import java.util.List;
import java.util.Map;

@Service
public class HistoryService {

    private final HistoryRepository historyRepository;
    private final ObjectMapper objectMapper = new ObjectMapper();

    public HistoryService(HistoryRepository historyRepository) {
        this.historyRepository = historyRepository;
    }

    @Transactional
    public History record(Long userId, String username, String taskType, String algorithm,
                          String dataSource, Map<String, ?> metrics, Map<String, ?> params,
                          Integer nSamples, Double durationSec, String status) {
        History h = new History();
        h.setUserId(userId);
        h.setUsername(username);
        h.setTaskType(taskType);
        h.setAlgorithm(algorithm);
        h.setDataSource(dataSource);
        try {
            h.setMetrics(objectMapper.writeValueAsString(metrics));
            h.setParams(objectMapper.writeValueAsString(params));
        } catch (Exception e) {
            h.setMetrics("{}");
            h.setParams("{}");
        }
        h.setNSamples(nSamples);
        h.setDurationSec(durationSec);
        h.setStatus(status);
        return historyRepository.save(h);
    }

    public List<History> list(String algorithm, String dataSource, String dateFrom, String dateTo) {
        return list(algorithm, dataSource, dateFrom, dateTo, null);
    }

    /**
     * @param onlyUserId 非空时仅返回该用户的记录（普通用户隔离）；null 表示不过滤（管理员）
     */
    public List<History> list(String algorithm, String dataSource, String dateFrom, String dateTo, Long onlyUserId) {
        Specification<History> spec = Specification.where(null);
        if (onlyUserId != null) {
            spec = spec.and((root, q, cb) -> cb.equal(root.get("userId"), onlyUserId));
        }
        if (algorithm != null && !algorithm.isBlank()) {
            spec = spec.and((root, q, cb) -> cb.equal(root.get("algorithm"), algorithm));
        }
        if (dataSource != null && !dataSource.isBlank()) {
            spec = spec.and((root, q, cb) -> cb.equal(root.get("dataSource"), dataSource));
        }
        if (dateFrom != null && !dateFrom.isBlank()) {
            LocalDateTime from = LocalDate.parse(dateFrom).atStartOfDay();
            spec = spec.and((root, q, cb) -> cb.greaterThanOrEqualTo(root.get("createdAt"), from));
        }
        if (dateTo != null && !dateTo.isBlank()) {
            LocalDateTime to = LocalDate.parse(dateTo).atTime(LocalTime.MAX);
            spec = spec.and((root, q, cb) -> cb.lessThanOrEqualTo(root.get("createdAt"), to));
        }
        return historyRepository.findAll(spec);
    }

    public History getById(Long id) {
        return historyRepository.findById(id).orElseThrow(() -> new IllegalArgumentException("记录不存在"));
    }

    @Transactional
    public void delete(Long id) {
        historyRepository.deleteById(id);
    }

    public String exportCsv() {
        return exportCsv(null);
    }

    public String exportCsv(Long onlyUserId) {
        StringBuilder sb = new StringBuilder("\uFEFF");
        sb.append("ID,用户,任务类型,算法,数据源,指标,参数,样本数,耗时(s),状态,时间\n");
        List<History> rows = onlyUserId == null
                ? historyRepository.findAll()
                : list(null, null, null, null, onlyUserId);
        for (History h : rows) {
            sb.append(h.getId()).append(',')
                    .append(csv(h.getUsername())).append(',')
                    .append(csv(h.getTaskType())).append(',')
                    .append(csv(h.getAlgorithm())).append(',')
                    .append(csv(h.getDataSource())).append(',')
                    .append(csv(h.getMetrics())).append(',')
                    .append(csv(h.getParams())).append(',')
                    .append(h.getNSamples() == null ? "" : h.getNSamples()).append(',')
                    .append(h.getDurationSec() == null ? "" : h.getDurationSec()).append(',')
                    .append(csv(h.getStatus())).append(',')
                    .append(h.getCreatedAt() == null ? "" : h.getCreatedAt()).append('\n');
        }
        return sb.toString();
    }

    private static String csv(String value) {
        if (value == null) return "";
        String escaped = value.replace("\"", "\"\"");
        return "\"" + escaped + "\"";
    }
}
