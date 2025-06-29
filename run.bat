@echo off
ECHO Starting script...
:: 使用 UTF-8 代码页，防止中文乱码
chcp 65001 >nul
setlocal EnableDelayedExpansion

:: --- 1. 环境检查 ---
echo 正在检查环境...

:: 检查 Python 是否安装
where python >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [错误] Python 未安装，请先安装 Python！
    pause
    exit /b 1
)

:: 设置并检查虚拟环境目录
set "VENV_DIR=venv"
if not exist "%VENV_DIR%\Scripts\activate" (
    echo [错误] 虚拟环境 "%VENV_DIR%" 不存在或不完整。
    echo 请先运行 set_up.bat 来创建虚拟环境。
    pause
    exit /b 1
)

:: 设置并检查 Python 脚本
set "PY_SCRIPT=main.py"

if not exist "%PY_SCRIPT%" (
    echo [错误] 脚本 "%PY_SCRIPT%" 不存在！
    pause
    exit /b 1
)
:: --- 2. 激活并运行 ---
echo.
echo 正在激活虚拟环境...
call "%VENV_DIR%\Scripts\activate"
if !ERRORLEVEL! neq 0 (
    echo [错误] 激活虚拟环境失败！
    pause
    exit /b 1
)

:: 并行运行Python 脚本
echo 开始运行，若初次启动请耐心等待...
python %PY_SCRIPT%
cmd