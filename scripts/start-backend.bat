@echo off
chcp 65001 >nul
cd /d "%~dp0..\backend"
echo [FORGE-HV] 启动 Spring Boot 后端 (端口 8080)...
echo 请确保 MySQL 已创建数据库 forge_hv（可执行 sql\init.sql）
echo 默认账号密码可通过环境变量 FORGE_DB_USER / FORGE_DB_PASSWORD 覆盖
call mvn spring-boot:run
pause
