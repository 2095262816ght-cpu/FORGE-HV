package com.forge.hv.controller;

import com.forge.hv.entity.History;
import com.forge.hv.security.AuthUser;
import com.forge.hv.service.HistoryService;
import org.springframework.core.io.ByteArrayResource;
import org.springframework.core.io.Resource;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.*;

import java.nio.charset.StandardCharsets;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

@RestController
@RequestMapping("/api/history")
public class HistoryController {

    private final HistoryService historyService;

    public HistoryController(HistoryService historyService) {
        this.historyService = historyService;
    }

    @GetMapping
    public Map<String, Object> list(@AuthenticationPrincipal AuthUser user,
                                    @RequestParam(required = false) String algorithm,
                                    @RequestParam(required = false) String data_source,
                                    @RequestParam(required = false) String date_from,
                                    @RequestParam(required = false) String date_to,
                                    @RequestParam(defaultValue = "1") int page,
                                    @RequestParam(defaultValue = "20") int size) {
        Long onlyUserId = isAdmin(user) ? null : (user == null ? -1L : user.userId());
        List<History> all = historyService.list(algorithm, data_source, date_from, date_to, onlyUserId);
        int from = Math.max(0, (page - 1) * size);
        int to = Math.min(all.size(), from + size);
        List<History> slice = from >= all.size() ? List.of() : all.subList(from, to);
        Map<String, Object> resp = new HashMap<>();
        resp.put("items", slice);
        resp.put("total", all.size());
        resp.put("page", page);
        resp.put("size", size);
        return resp;
    }

    @GetMapping("/{id}")
    public ResponseEntity<?> detail(@AuthenticationPrincipal AuthUser user, @PathVariable Long id) {
        History h = historyService.getById(id);
        if (!canAccess(user, h)) {
            return ResponseEntity.status(403).body(Map.of("error", "无权查看该记录"));
        }
        return ResponseEntity.ok(h);
    }

    @DeleteMapping("/{id}")
    public ResponseEntity<?> delete(@PathVariable Long id) {
        historyService.delete(id);
        return ResponseEntity.ok(Map.of("status", "ok"));
    }

    @GetMapping("/export")
    public ResponseEntity<Resource> export(@AuthenticationPrincipal AuthUser user) {
        Long onlyUserId = isAdmin(user) ? null : (user == null ? -1L : user.userId());
        String csv = historyService.exportCsv(onlyUserId);
        byte[] bytes = csv.getBytes(StandardCharsets.UTF_8);
        return ResponseEntity.ok()
                .header(HttpHeaders.CONTENT_DISPOSITION, "attachment; filename=history.csv")
                .contentType(new MediaType("text", "csv", StandardCharsets.UTF_8))
                .body(new ByteArrayResource(bytes));
    }

    @PostMapping
    public ResponseEntity<?> create(@AuthenticationPrincipal AuthUser user, @RequestBody Map<String, Object> body) {
        if (user == null || "guest".equalsIgnoreCase(user.role())) {
            return ResponseEntity.status(403).body(Map.of("error", "游客无法写入历史记录"));
        }
        History h = historyService.record(
                user.userId(),
                user.username(),
                String.valueOf(body.get("task_type")),
                String.valueOf(body.get("algorithm")),
                String.valueOf(body.get("data_source")),
                (Map<String, ?>) body.getOrDefault("metrics", Map.of()),
                (Map<String, ?>) body.getOrDefault("params", Map.of()),
                body.get("n_samples") == null ? null : ((Number) body.get("n_samples")).intValue(),
                body.get("duration_sec") == null ? null : ((Number) body.get("duration_sec")).doubleValue(),
                String.valueOf(body.getOrDefault("status", "done"))
        );
        return ResponseEntity.ok(h);
    }

    private static boolean isAdmin(AuthUser user) {
        return user != null && "admin".equalsIgnoreCase(user.role());
    }

    private static boolean canAccess(AuthUser user, History h) {
        if (isAdmin(user)) return true;
        if (user == null || h.getUserId() == null) return false;
        return h.getUserId().equals(user.userId());
    }
}
