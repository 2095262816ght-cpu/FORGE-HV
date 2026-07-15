@echo off
chcp 65001 >nul
setlocal

echo ============================================
echo   FORGE-HV 一键安装依赖
echo ============================================
echo.
echo 请选择安装方式:
echo   [1] pip install  (轻量，用现有 Python)
echo   [2] conda env    (推荐，连 Python 一起装，最接近 Maven)
echo   [3] 退出
echo.
set /p choice="请输入 1/2/3: "

if "%choice%"=="1" goto pip_install
if "%choice%"=="2" goto conda_install
if "%choice%"=="3" exit /b 0
echo 无效输入，退出。
pause
exit /b 1

:pip_install
echo.
echo --- 方式一: pip install ---
echo 检测 Python...
python --version 2>nul
if errorlevel 1 (
    echo [错误] 未找到 python，请先安装 Python 3.10+ 或 Miniconda。
    pause
    exit /b 1
)
echo.
echo 正在用清华镜像安装依赖（速度快）...
python -m pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple --trusted-host pypi.tuna.tsinghua.edu.cn
if errorlevel 1 (
    echo [错误] 安装失败，请检查上方报错。
    pause
    exit /b 1
)
echo.
echo --- 验证关键依赖 ---
python -c "import flask, sklearn, pandas, numpy, xgboost, torch; print('所有依赖安装成功!')"
echo.
echo 下一步: python app.py
pause
exit /b 0

:conda_install
echo.
echo --- 方式二: conda env create ---
echo 检测 conda...
conda --version 2>nul
if errorlevel 1 (
    echo [错误] 未找到 conda，请先安装 Miniconda:
    echo   https://docs.conda.io/en/latest/miniconda.html
    pause
    exit /b 1
)
echo.
echo 正在创建 conda 环境 forge-hv （会自动装 Python + 全部依赖）...
echo 首次创建较慢，请耐心等待...
conda env create -f environment.yml
if errorlevel 1 (
    echo [错误] 环境创建失败，请检查上方报错。
    pause
    exit /b 1
)
echo.
echo --- 验证 ---
conda activate forge-hv
python -c "import flask, sklearn, pandas, numpy, xgboost, torch; print('所有依赖安装成功!')"
echo.
echo 下一步:
echo   conda activate forge-hv
echo   python app.py
pause
exit /b 0
