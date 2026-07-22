package com.forge.hv.entity;

import com.fasterxml.jackson.annotation.JsonProperty;
import jakarta.persistence.*;

import java.time.LocalDateTime;

@Entity
@Table(name = "history")
public class History {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @JsonProperty("user_id")
    @Column(name = "user_id")
    private Long userId;

    @Column(length = 64)
    private String username;

    @JsonProperty("task_type")
    @Column(name = "task_type", length = 64)
    private String taskType;

    @Column(length = 64)
    private String algorithm;

    @JsonProperty("data_source")
    @Column(name = "data_source", length = 64)
    private String dataSource;

    @Column(columnDefinition = "JSON")
    private String metrics;

    @Column(columnDefinition = "JSON")
    private String params;

    @JsonProperty("n_samples")
    @Column(name = "n_samples")
    private Integer nSamples;

    @JsonProperty("duration_sec")
    @Column(name = "duration_sec")
    private Double durationSec;

    @Column(length = 32)
    private String status;

    @JsonProperty("created_at")
    @Column(name = "created_at", nullable = false)
    private LocalDateTime createdAt = LocalDateTime.now();

    public Long getId() { return id; }
    public void setId(Long id) { this.id = id; }
    public Long getUserId() { return userId; }
    public void setUserId(Long userId) { this.userId = userId; }
    public String getUsername() { return username; }
    public void setUsername(String username) { this.username = username; }
    public String getTaskType() { return taskType; }
    public void setTaskType(String taskType) { this.taskType = taskType; }
    public String getAlgorithm() { return algorithm; }
    public void setAlgorithm(String algorithm) { this.algorithm = algorithm; }
    public String getDataSource() { return dataSource; }
    public void setDataSource(String dataSource) { this.dataSource = dataSource; }
    public String getMetrics() { return metrics; }
    public void setMetrics(String metrics) { this.metrics = metrics; }
    public String getParams() { return params; }
    public void setParams(String params) { this.params = params; }
    public Integer getNSamples() { return nSamples; }
    public void setNSamples(Integer nSamples) { this.nSamples = nSamples; }
    public Double getDurationSec() { return durationSec; }
    public void setDurationSec(Double durationSec) { this.durationSec = durationSec; }
    public String getStatus() { return status; }
    public void setStatus(String status) { this.status = status; }
    public LocalDateTime getCreatedAt() { return createdAt; }
    public void setCreatedAt(LocalDateTime createdAt) { this.createdAt = createdAt; }
}
