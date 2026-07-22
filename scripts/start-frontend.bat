@echo off
chcp 65001 >nul
cd /d "%~dp0..\frontend-vue"
if not exist node_modules (
  echo [FORGE-HV] 首次运行，安装前端依赖...
  call npm install
)
echo [FORGE-HV] 启动 Vue 前端 (端口 5173)...
call npm run dev
pause
