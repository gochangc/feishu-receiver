@echo off
setlocal
REM 飞书消息接收服务 - Windows 入口脚本

set "SCRIPT_DIR=%~dp0"
set "BASH_SCRIPT=%SCRIPT_DIR%bin\feishu-receiver"
set "INSTALL_DIR=%SCRIPT_DIR:~0,-1%"

REM 逐个尝试 bash 路径
for %%p in (
    "D:\Program Files\Git\bin\bash.exe"
    "C:\Program Files\Git\bin\bash.exe"
    "%LOCALAPPDATA%\Programs\Git\bin\bash.exe"
) do if exist %%p (
    %%p "%BASH_SCRIPT%" %*
    goto :done
)

REM 尝试 where bash.exe
for /f "delims=" %%i in ('where bash.exe 2^>nul') do (
    "%%i" "%BASH_SCRIPT%" %*
    goto :done
)

REM 尝试 WSL
wsl -e bash "%BASH_SCRIPT%" %* 2>nul
if errorlevel 1 (
    echo 错误: 未找到 Git Bash 或 WSL。
    echo 请安装 Git for Windows: https://git-scm.com/downloads/win
    exit /b 1
)

:done
REM 卸载时清理安装目录
if /i "%~1"=="uninstall" (
    cd /d "%USERPROFILE%"
    rmdir /s /q "%INSTALL_DIR%" 2>nul
)
