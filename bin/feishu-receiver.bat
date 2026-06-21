@echo off
setlocal
REM 飞书消息接收服务 - Windows 入口脚本

set "SCRIPT_DIR=%~dp0"
set "PS_SCRIPT=%SCRIPT_DIR%feishu-receiver.ps1"

REM 优先使用 PowerShell Core (pwsh)，其次使用 Windows PowerShell
where pwsh.exe >nul 2>&1
if %errorlevel% equ 0 (
    pwsh -ExecutionPolicy Bypass -File "%PS_SCRIPT%" %*
    goto :done
)

where powershell.exe >nul 2>&1
if %errorlevel% equ 0 (
    powershell -ExecutionPolicy Bypass -File "%PS_SCRIPT%" %*
    goto :done
)

echo 错误: 未找到 PowerShell。
echo 请安装 PowerShell: https://github.com/PowerShell/PowerShell
exit /b 1

:done
