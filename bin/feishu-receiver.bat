@echo off
setlocal
REM 飞书消息接收服务 - Windows 入口脚本

set SCRIPT_DIR=%~dp0
set BASH_SCRIPT=%SCRIPT_DIR%bin\feishu-receiver

REM 尝试从 PATH 查找 bash.exe
for /f "delims=" %%i in ('where bash.exe 2^>nul') do (
    "%%i" "%BASH_SCRIPT%" %*
    exit /b %ERRORLEVEL%
)

REM 尝试常见 Git Bash 安装路径
for %%d in (
    "%ProgramFiles%\Git\bin"
    "%ProgramW6432%\Git\bin"
    "C:\Program Files\Git\bin"
    "D:\Program Files\Git\bin"
) do (
    if exist "%%~d\bash.exe" (
        "%%~d\bash.exe" "%BASH_SCRIPT%" %*
        exit /b %ERRORLEVEL%
    )
)

REM 尝试 WSL
wsl -e bash "%BASH_SCRIPT%" %* 2>nul
if not errorlevel 1 exit /b 0

echo 错误: 未找到 Git Bash 或 WSL。
echo 请安装 Git for Windows: https://git-scm.com/downloads/win
exit /b 1
