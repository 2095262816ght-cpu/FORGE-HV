package com.forge.hv.service;

import com.forge.hv.entity.User;
import org.springframework.security.crypto.bcrypt.BCryptPasswordEncoder;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.SecureRandom;
import java.util.HexFormat;

/**
 * BCrypt 为主；兼容旧版 SHA-256(salt + password)，登录成功后自动升级。
 */
@Service
public class PasswordService {

    public static final String BCRYPT_SALT_MARKER = "bcrypt";

    private final BCryptPasswordEncoder bcrypt = new BCryptPasswordEncoder();
    private final SecureRandom random = new SecureRandom();

    public PasswordEncoder encoder() {
        return bcrypt;
    }

    public void setPassword(User user, String rawPassword) {
        user.setSalt(BCRYPT_SALT_MARKER);
        user.setPasswordHash(bcrypt.encode(rawPassword));
    }

    public boolean matches(User user, String rawPassword) {
        if (user == null || rawPassword == null) return false;
        String hash = user.getPasswordHash();
        String salt = user.getSalt();
        if (hash == null) return false;
        if (isBcrypt(hash) || BCRYPT_SALT_MARKER.equalsIgnoreCase(salt)) {
            return bcrypt.matches(rawPassword, hash);
        }
        return legacySha256(rawPassword, salt).equalsIgnoreCase(hash);
    }

    /** 若仍是旧哈希，升级为 BCrypt 并返回 true。 */
    public boolean upgradeIfLegacy(User user, String rawPassword) {
        if (user == null) return false;
        String hash = user.getPasswordHash();
        if (isBcrypt(hash) || BCRYPT_SALT_MARKER.equalsIgnoreCase(user.getSalt())) {
            return false;
        }
        if (!matches(user, rawPassword)) return false;
        setPassword(user, rawPassword);
        return true;
    }

    private static boolean isBcrypt(String hash) {
        return hash != null && (hash.startsWith("$2a$") || hash.startsWith("$2b$") || hash.startsWith("$2y$"));
    }

    private static String legacySha256(String password, String salt) {
        try {
            MessageDigest md = MessageDigest.getInstance("SHA-256");
            byte[] digest = md.digest((salt + password).getBytes(StandardCharsets.UTF_8));
            return HexFormat.of().formatHex(digest);
        } catch (Exception e) {
            throw new IllegalStateException("SHA-256 unavailable", e);
        }
    }

    public String randomHex(int bytes) {
        byte[] buf = new byte[bytes];
        random.nextBytes(buf);
        return HexFormat.of().formatHex(buf);
    }
}
