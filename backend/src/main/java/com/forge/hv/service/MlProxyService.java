package com.forge.hv.service;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.core.io.ByteArrayResource;
import org.springframework.core.io.Resource;
import org.springframework.http.*;
import org.springframework.http.client.SimpleClientHttpRequestFactory;
import org.springframework.stereotype.Service;
import org.springframework.util.LinkedMultiValueMap;
import org.springframework.util.MultiValueMap;
import org.springframework.web.client.RestClient;
import org.springframework.web.multipart.MultipartFile;

import java.util.Map;

@Service
public class MlProxyService {

    private final RestClient restClient;

    public MlProxyService(
            @Value("${forge.ml-service.base-url}") String baseUrl,
            @Value("${forge.ml-service.connect-timeout-ms:5000}") int connectTimeoutMs,
            @Value("${forge.ml-service.read-timeout-ms:600000}") int readTimeoutMs) {
        SimpleClientHttpRequestFactory factory = new SimpleClientHttpRequestFactory();
        factory.setConnectTimeout(connectTimeoutMs);
        factory.setReadTimeout(readTimeoutMs);
        this.restClient = RestClient.builder()
                .baseUrl(baseUrl)
                .requestFactory(factory)
                .build();
    }

    public Map<?, ?> get(String path) {
        return restClient.get().uri(path).retrieve().body(Map.class);
    }

    public Map<?, ?> post(String path, Object body) {
        return restClient.post().uri(path).body(body).retrieve().body(Map.class);
    }

    public Map<?, ?> put(String path, Object body) {
        return restClient.put().uri(path).body(body).retrieve().body(Map.class);
    }

    public void delete(String path) {
        restClient.delete().uri(path).retrieve().toBodilessEntity();
    }

    public ResponseEntity<Resource> getFile(String path) {
        byte[] bytes = restClient.get().uri(path).retrieve().body(byte[].class);
        return ResponseEntity.ok()
                .contentType(MediaType.APPLICATION_OCTET_STREAM)
                .body(new ByteArrayResource(bytes == null ? new byte[0] : bytes));
    }

    public Map<?, ?> upload(String path, MultipartFile file) throws Exception {
        MultiValueMap<String, Object> body = new LinkedMultiValueMap<>();
        body.add("file", new ByteArrayResource(file.getBytes()) {
            @Override
            public String getFilename() {
                return file.getOriginalFilename();
            }
        });
        return restClient.post()
                .uri(path)
                .contentType(MediaType.MULTIPART_FORM_DATA)
                .body(body)
                .retrieve()
                .body(Map.class);
    }
}
