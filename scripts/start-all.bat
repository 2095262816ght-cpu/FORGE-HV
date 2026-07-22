@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ========================================
echo  FORGE-HV 四栈融合启动
echo  Python ML + Spring Boot + MySQL + Vue
echo ========================================
echo.
echo 将分别打开 3 个窗口：
echo   1) Python ML  :5001
echo   2) Spring Boot :8080
echo   3) Vue 前端    :5173
echo.
start "FORGE-HV ML" cmd /k "%~dp0start-ml.bat"
timeout /t 2 /nobreak >nul
start "FORGE-HV Backend" cmd /k "%~dp0start-backend.bat"
timeout /t 3 /nobreak >nul
start "FORGE-HV Frontend" cmd /k "%~dp0start-frontend.bat"
echo.
echo 启动命令已发出。浏览器访问: http://127.0.0.1:5173
echo 默认管理员: admin / admin123
pause
