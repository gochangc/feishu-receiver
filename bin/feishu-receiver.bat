@echo off
setlocal
REM 飞书消息接收服务 - Windows 入口脚本

set "SCRIPT_DIR=%~dp0"
set "BASH_SCRIPT=%SCRIPT_DIR%bin\feishu-receiver"

REM 尝试各种方式查找并运行 bash
call :try_path "C:\Program Files\Git\bin\bash.exe" %* && exit /b 0
call :try_path "D:\Program Files\Git\bin\bash.exe" %* && exit /b 0
call :try_path "%LOCALAPPDATA%\Programs\Git\bin\bash.exe" %* && exit /b 0
call :try_where %* && exit /b 0
call :try_wsl %* && exit /b 0

echo 错误: 未找到 Git Bash 或 WSL。
echo 请安装 Git for Windows: https://git-scm.com/downloads/win
exit /b 1

:try_path
if exist "%~1" (
    "%~1" "%BASH_SCRIPT%" %2 %3 %4 %5 %6 %7 %8 %9
    exit /b %ERRORLEVEL%
)
exit /b 1

:try_where
for /f "delims=" %%i in ('where bash.exe 2^>nul') do (
    "%%i" "%BASH_SCRIPT%" %1 %2 %3 %4 %5 %6 %7 %8 %9
    exit /b %ERRORLEVEL%
)
exit /b 1

:try_wsl
wsl -e bash "%BASH_SCRIPT%" %1 %2 %3 %4 %5 %6 %7 %8 %9 2>nul
exit /b %ERRORLEVEL%
