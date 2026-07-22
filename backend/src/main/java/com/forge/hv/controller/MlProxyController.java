package com.forge.hv.controller;

import com.forge.hv.security.AuthUser;
import com.forge.hv.service.HistoryService;
import com.forge.hv.service.MlProxyService;
import org.springframework.core.io.Resource;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.multipart.MultipartFile;

import java.util.HashMap;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

@RestController
@RequestMapping("/api")
public class MlProxyController {

    private final MlProxyService mlProxyService;
    private final HistoryService historyService;
    private final ConcurrentHashMap<String, Boolean> recordedDdpgTasks = new ConcurrentHashMap<>();

    public MlProxyController(MlProxyService mlProxyService, HistoryService historyService) {
        this.mlProxyService = mlProxyService;
        this.historyService = historyService;
    }

    @GetMapping("/health")
    public Map<String, Object> health() {
        try {
            Map<?, ?> ml = mlProxyService.get("/api/health");
            Map<String, Object> resp = new HashMap<>();
            resp.put("status", "ok");
            resp.put("backend", "spring-boot");
            resp.put("ml_service", ml);
            return resp;
        } catch (Exception e) {
            Map<String, Object> resp = new HashMap<>();
            resp.put("status", "degraded");
            resp.put("backend", "spring-boot");
            resp.put("ml_error", e.getMessage());
            return resp;
        }
    }

    @GetMapping("/data/source_stats")
    public Map<?, ?> sourceStats() { return mlProxyService.get("/api/data/source_stats"); }

    @GetMapping("/data/columns")
    public Map<?, ?> columns() { return mlProxyService.get("/api/data/columns"); }

    @GetMapping("/data/preview")
    public Map<?, ?> preview(@RequestParam(defaultValue = "20") int limit) {
        return mlProxyService.get("/api/data/preview?limit=" + limit);
    }

    @GetMapping("/data/stats")
    public Map<?, ?> stats() { return mlProxyService.get("/api/data/stats"); }

    @PostMapping("/data/upload")
    public Map<?, ?> upload(@RequestParam("file") MultipartFile file) throws Exception {
        return mlProxyService.upload("/api/data/upload", file);
    }

    @PostMapping("/data/reset")
    public Map<?, ?> reset() { return mlProxyService.post("/api/data/reset", Map.of()); }

    @GetMapping("/data/rows")
    public Map<?, ?> rows(@RequestParam Map<String, String> params) {
        String query = params.entrySet().stream()
                .map(e -> e.getKey() + "=" + e.getValue())
                .reduce((a, b) -> a + "&" + b).orElse("");
        return mlProxyService.get("/api/data/rows?" + query);
    }

    @PostMapping("/data/rows")
    public Map<?, ?> addRow(@RequestBody Map<String, Object> body) {
        return mlProxyService.post("/api/data/rows", body);
    }

    @PutMapping("/data/rows/{id}")
    public Map<?, ?> updateRow(@PathVariable int id, @RequestBody Map<String, Object> body) {
        return mlProxyService.put("/api/data/rows/" + id, body);
    }

    @DeleteMapping("/data/rows/{id}")
    public ResponseEntity<?> deleteRow(@PathVariable int id) {
        mlProxyService.delete("/api/data/rows/" + id);
        return ResponseEntity.ok(Map.of("status", "ok"));
    }

    @PostMapping("/data/batch_import")
    public Map<?, ?> batchImport(@AuthenticationPrincipal AuthUser user,
                                 @RequestParam("file") MultipartFile file) throws Exception {
        Map<?, ?> result = mlProxyService.upload("/api/data/batch_import", file);
        if (result != null && !result.containsKey("error")) {
            Map<String, Object> params = new HashMap<>();
            params.put("filename", file.getOriginalFilename() == null ? "" : file.getOriginalFilename());
            Integer appended = result.get("appended") instanceof Number n ? n.intValue() : null;
            safeRecord(user, "batch_import", "data_import",
                    mapStr(result, "path", "upload"),
                    new HashMap<>(), params, appended, 0.0, "done");
        }
        return result;
    }

    @GetMapping("/data/export")
    public ResponseEntity<Resource> exportData(@RequestParam(defaultValue = "xlsx") String format) {
        return mlProxyService.getFile("/api/data/export?format=" + format);
    }

    @GetMapping("/data/analysis")
    public Map<?, ?> analysis() { return mlProxyService.get("/api/data/analysis"); }

    @PostMapping("/train/traditional")
    public Map<?, ?> trainTraditional(@AuthenticationPrincipal AuthUser user,
                                      @RequestBody Map<String, Object> body) {
        long t0 = System.currentTimeMillis();
        Map<?, ?> result = mlProxyService.post("/api/train/traditional", body);
        if (result != null && !result.containsKey("error")) {
            String model = mapStr(result, "model", String.valueOf(body.getOrDefault("model", "unknown")));
            String dataSource = mapStr(result, "data_source", String.valueOf(body.getOrDefault("data_source", "real")));
            Map<String, Object> metrics = new HashMap<>();
            if (result.get("train_metrics") != null) metrics.put("train", result.get("train_metrics"));
            if (result.get("test_metrics") != null) metrics.put("test", result.get("test_metrics"));
            int nTrain = result.get("n_train") instanceof Number n ? n.intValue() : 0;
            int nTest = result.get("n_test") instanceof Number n ? n.intValue() : 0;
            safeRecord(user, "train_traditional", model, dataSource, metrics, new HashMap<>(body),
                    nTrain + nTest, (System.currentTimeMillis() - t0) / 1000.0, "done");
        }
        return result;
    }

    @PostMapping("/train/compare")
    public Map<?, ?> trainCompare(@AuthenticationPrincipal AuthUser user,
                                  @RequestBody Map<String, Object> body) {
        long t0 = System.currentTimeMillis();
        Map<?, ?> result = mlProxyService.post("/api/train/compare", body);
        if (result != null && !result.containsKey("error")) {
            String dataSource = mapStr(result, "data_source", String.valueOf(body.getOrDefault("data_source", "real")));
            String best = mapStr(result, "best", "compare");
            Map<String, Object> metrics = new HashMap<>();
            metrics.put("best", best);
            metrics.put("models", result.get("models"));
            int nTrain = result.get("n_train") instanceof Number n ? n.intValue() : 0;
            int nTest = result.get("n_test") instanceof Number n ? n.intValue() : 0;
            safeRecord(user, "train_compare", best, dataSource, metrics, new HashMap<>(body),
                    nTrain + nTest, (System.currentTimeMillis() - t0) / 1000.0, "done");
        }
        return result;
    }

    @GetMapping("/train/export_csv")
    public ResponseEntity<Resource> exportCsv() {
        return mlProxyService.getFile("/api/train/export_csv");
    }

    @GetMapping("/train/export_model")
    public ResponseEntity<Resource> exportModel() {
        return mlProxyService.getFile("/api/train/export_model");
    }

    @PostMapping("/outliers/detect")
    public Map<?, ?> outliers(@RequestBody Map<String, Object> body) {
        return mlProxyService.post("/api/outliers/detect", body);
    }

    @GetMapping("/correlation/matrix")
    public Map<?, ?> correlation(@RequestParam(defaultValue = "pearson") String method) {
        return mlProxyService.get("/api/correlation/matrix?method=" + method);
    }

    @PostMapping("/database/query")
    public Map<?, ?> dbQuery(@RequestBody Map<String, Object> body) {
        return mlProxyService.post("/api/database/query", body);
    }

    @GetMapping("/database/schema")
    public Map<?, ?> dbSchema() { return mlProxyService.get("/api/database/schema"); }

    @PostMapping("/ddpg/train")
    public Map<?, ?> ddpgTrain(@AuthenticationPrincipal AuthUser user,
                               @RequestBody Map<String, Object> body) {
        Map<?, ?> result = mlProxyService.post("/api/ddpg/train", body);
        if (result != null && result.get("task_id") != null) {
            String taskId = String.valueOf(result.get("task_id"));
            String dataSource = String.valueOf(body.getOrDefault("data_source", "real"));
            Map<String, Object> metrics = new HashMap<>();
            metrics.put("task_id", taskId);
            safeRecord(user, "ddpg_train", "DDPG", dataSource, metrics, new HashMap<>(body),
                    null, null, "pending");
        }
        return result;
    }

    @GetMapping("/ddpg/status/{taskId}")
    public Map<?, ?> ddpgStatus(@AuthenticationPrincipal AuthUser user, @PathVariable String taskId) {
        Map<?, ?> result = mlProxyService.get("/api/ddpg/status/" + taskId);
        if (result != null && !result.containsKey("error")) {
            String status = mapStr(result, "status", "");
            if (("done".equals(status) || "completed".equals(status) || "finished".equals(status))
                    && recordedDdpgTasks.putIfAbsent(taskId, Boolean.TRUE) == null) {
                Map<String, Object> metrics = new HashMap<>();
                metrics.put("task_id", taskId);
                metrics.put("val_r2", result.get("val_r2"));
                metrics.put("progress", result.get("progress"));
                metrics.put("epoch", result.get("epoch"));
                if (result.get("metrics") instanceof Map<?, ?> detail) {
                    metrics.put("detail", detail);
                    // 展平 test/train/val，方便历史页直接读取
                    if (detail.get("test") != null) metrics.put("test", detail.get("test"));
                    if (detail.get("train") != null) metrics.put("train", detail.get("train"));
                    if (detail.get("val") != null) metrics.put("val", detail.get("val"));
                }
                String dataSource = mapStr(result, "data_source", "real");
                Double duration = null;
                if (result.get("created_at") instanceof Number created) {
                    duration = (System.currentTimeMillis() / 1000.0) - created.doubleValue();
                }
                Map<String, Object> params = new HashMap<>();
                params.put("task_id", taskId);
                safeRecord(user, "ddpg_train", "DDPG", dataSource, metrics, params, null, duration, "done");
            }
        }
        return result;
    }

    @GetMapping("/ddpg/tasks")
    public Map<?, ?> ddpgTasks() { return mlProxyService.get("/api/ddpg/tasks"); }

    private static String mapStr(Map<?, ?> map, String key, String defaultValue) {
        Object v = map == null ? null : map.get(key);
        return v == null ? defaultValue : String.valueOf(v);
    }

    private void safeRecord(AuthUser user, String taskType, String algorithm, String dataSource,
                            Map<String, Object> metrics, Map<String, Object> params,
                            Integer nSamples, Double durationSec, String status) {
        try {
            Long uid = user == null || user.userId() == 0L ? null : user.userId();
            String uname = user == null ? "system" : user.username();
            historyService.record(uid, uname, taskType, algorithm, dataSource,
                    metrics == null ? Map.of() : metrics,
                    params == null ? Map.of() : params,
                    nSamples, durationSec, status);
        } catch (Exception ignored) {
            // history must not break ML responses
        }
    }
}
