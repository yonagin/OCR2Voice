@echo off
setlocal EnableDelayedExpansion

:: 设置并检查 Python 脚本
set "PY_SCRIPT=build.py"

if not exist "%PY_SCRIPT%" (
    echo [错误] 脚本 "%PY_SCRIPT%" 不存在！
    pause
    exit /b 1
)
echo start building......
python %PY_SCRIPT%
cmd