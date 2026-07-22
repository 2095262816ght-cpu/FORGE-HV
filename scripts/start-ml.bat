@echo off
chcp 65001 >nul
cd /d "%~dp0.."
echo [FORGE-HV] 启动 Python ML 微服务 (端口 5001)...
echo 复用算法栈: DDPG / GAN / LinearRegression / PolynomialRegression / SVR
python ml-service\main.py
pause
