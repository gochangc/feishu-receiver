@echo off
REM 飞书消息接收服务 - Windows 入口脚本

set SCRIPT_DIR=%~dp0
set BASH_SCRIPT=%SCRIPT_DIR%bin\feishu-receiver

REM 优先从 PATH 查找 bash.exe（Git Bash）
for /f "delims=" %%i in ('where bash.exe 2^>nul') do (
    "%%i" "%BASH_SCRIPT%" %*
    exit /b %ERRORLEVEL%
)

REM 尝试常见 Git Bash 安装路径
if exist "C:\Program Files\Git\bin\bash.exe" (
    "C:\Program Files\Git\bin\bash.exe" "%BASH_SCRIPT%" %*
    exit /b %ERRORLEVEL%
)

REM 尝试 WSL
where wsl >nul 2>&1
if not errorlevel 1 (
    wsl bash "%BASH_SCRIPT%" %*
    exit /b %ERRORLEVEL%
)

echo 错误: 未找到 Git Bash 或 WSL。
echo 请安装 Git for Windows: https://git-scm.com/downloads/win
exit 1
