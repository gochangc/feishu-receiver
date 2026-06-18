# 飞书消息接收服务 - PowerShell 安装脚本
# 用法: irm https://raw.githubusercontent.com/gochangc/feishu-receiver/main/install.ps1 | iex
param(
    [switch]$User,
    [string]$WorkDir = $env:FEISHU_RECEIVER_WORKDIR
)

$ErrorActionPreference = "Stop"

$InstallDir = "$env:LOCALAPPDATA\feishu-receiver"
$BinDir = "$InstallDir\bin"
$LibDir = "$InstallDir\lib"
$LogsDir = "$InstallDir\logs"
$RepoUrl = "https://github.com/gochangc/feishu-receiver.git"

if (-not $WorkDir) {
    $WorkDir = "$env:USERPROFILE\workspace"
}

Write-Host "==> 检查依赖..." -ForegroundColor Cyan
$missing = @()
foreach ($cmd in @("python3", "lark-cli", "claude")) {
    if (-not (Get-Command $cmd -ErrorAction SilentlyContinue)) {
        Write-Host "  错误: $cmd 未找到，请先安装。" -ForegroundColor Red
        $missing += $cmd
    }
}
if ($missing.Count -gt 0) {
    Write-Host ""
    Write-Host "缺少以下依赖: $($missing -join ', ')" -ForegroundColor Red
    Write-Host "请安装后再运行本脚本。" -ForegroundColor Red
    exit 1
}
Write-Host "  依赖检查通过"

Write-Host "==> 检查 lark-cli 配置..."
$larkStatus = lark-cli auth status 2>&1 | Out-String
if ($larkStatus -match "not configured") {
    Write-Host ""
    Write-Host "警告: lark-cli 尚未配置，服务安装后无法接收飞书消息。" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "请先执行以下命令完成配置:"
    Write-Host '  lark-cli config init --app-id <你的AppID> --app-secret-stdin --brand feishu'
    Write-Host ""
    if (-not $env:CI) {
        $confirm = Read-Host "是否继续安装? (y/N)"
        if ($confirm -ne "y" -and $confirm -ne "Y") {
            Write-Host "安装已取消。"
            exit 1
        }
    } else {
        Write-Host "检测到非交互模式，跳过确认，继续安装。"
    }
} else {
    Write-Host "  lark-cli 已配置"
}

Write-Host "==> 下载项目文件..."
if (Test-Path $InstallDir) {
    Write-Host "  安装目录已存在，删除旧版本..."
    Remove-Item -Recurse -Force $InstallDir
}
git clone --depth 1 $RepoUrl $InstallDir *>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "  克隆仓库失败，请检查网络连接。" -ForegroundColor Red
    exit 1
}
Remove-Item -Recurse -Force "$InstallDir\.git" -ErrorAction SilentlyContinue

Write-Host "==> 创建命令入口..."
$batPath = "$InstallDir\feishu-receiver.bat"
@"
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
"@ | Out-File -FilePath $batPath -Encoding ASCII

Write-Host "==> 添加到用户 PATH..."
$userPath = [Environment]::GetEnvironmentVariable("Path", "User")
if ($userPath -notlike "*$InstallDir*") {
    [Environment]::SetEnvironmentVariable("Path", "$userPath;$InstallDir", "User")
    $env:Path += ";$InstallDir"
    Write-Host "  已将安装目录添加到用户 PATH"
} else {
    Write-Host "  安装目录已在 PATH 中"
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "安装完成！" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "【基本信息】"
Write-Host "  安装目录: $InstallDir"
Write-Host "  启动命令: feishu-receiver <start|stop|status|restart|foreground>"
Write-Host "  工作目录: $WorkDir"
Write-Host "  日志目录: $LogsDir"
Write-Host ""
Write-Host "【独立模式管理 (Windows)】"
Write-Host "  后台启动: feishu-receiver start"
Write-Host "  停止服务: feishu-receiver stop"
Write-Host "  查看状态: feishu-receiver status"
Write-Host "  重启服务: feishu-receiver restart"
Write-Host "  前台运行: feishu-receiver foreground"
Write-Host ""
Write-Host "【前置步骤 (必须)】"
Write-Host ""
Write-Host "  1. 在飞书开放平台创建自建应用"
Write-Host "     - 访问 https://open.feishu.cn/app"
Write-Host "     - 获取 App ID 和 App Secret"
Write-Host ""
Write-Host "  2. 配置 lark-cli（如尚未配置）"
Write-Host "     lark-cli config init --app-id <你的AppID> --app-secret-stdin --brand feishu"
Write-Host ""
Write-Host "  3. 开通飞书权限并发布应用"
Write-Host "     - im:message"
Write-Host "     - im:message.p2p_msg:readonly"
Write-Host ""
Write-Host "【查看日志】"
Write-Host "  Get-Content $LogsDir\feishu-receiver.log -Wait"
Write-Host ""
Write-Host "【卸载】"
Write-Host "  删除目录 $InstallDir 并从 PATH 中移除即可。"
Write-Host "========================================" -ForegroundColor Green
