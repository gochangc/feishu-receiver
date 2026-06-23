# install.ps1
# 飞书消息接收服务 - PowerShell 安装脚本
# 用法: irm https://raw.githubusercontent.com/gochangc/feishu-receiver/main/install.ps1 | iex

$ErrorActionPreference = 'Stop'

# 强制使用 TLS 1.2（GitHub 要求）
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

$InstallDir = "$env:USERPROFILE\.feishu-receiver"
$LogDir = "$InstallDir\logs"
$RawBase = 'https://raw.githubusercontent.com/gochangc/feishu-receiver/main'

Write-Host '==> 检查依赖...' -ForegroundColor Cyan
foreach ($cmd in @('python', 'lark-cli')) {
    if (-not (Get-Command $cmd -ErrorAction SilentlyContinue)) {
        Write-Host "  错误: $cmd 未找到" -ForegroundColor Red
        exit 1
    }
}
Write-Host '  依赖检查通过'

Write-Host '==> 检查 lark-cli 配置...'
$prevEAP = $ErrorActionPreference
$ErrorActionPreference = 'SilentlyContinue'
$larkStatus = lark-cli auth status 2>&1 | Out-String
$ErrorActionPreference = $prevEAP
if ($larkStatus -match 'not configured') {
    Write-Host '  警告: lark-cli 尚未配置' -ForegroundColor Yellow
    Write-Host '  请执行: lark-cli config init --app-id <AppID> --app-secret-stdin --brand feishu'
} else {
    Write-Host '  lark-cli 已配置'
}

Write-Host '==> 下载文件...'

# 覆盖安装前先停止正在运行的服务
$PidFile = "$InstallDir\feishu-receiver.pid"
if (Test-Path $PidFile) {
    $svcPid = Get-Content $PidFile -ErrorAction SilentlyContinue
    if ($svcPid) {
        $proc = Get-Process -Id $svcPid -ErrorAction SilentlyContinue
        if ($proc) {
            Write-Host "  停止正在运行的服务 (PID: $svcPid)..."
            Stop-Process -Id $svcPid -Force -ErrorAction SilentlyContinue
            Start-Sleep -Seconds 2
        }
    }
    Remove-Item $PidFile -ErrorAction SilentlyContinue
}

# 清理安装目录（保留 config.json 和 sessions.db）
if (Test-Path $InstallDir) {
    # 先删除子目录（bin, lib, logs），再删除根目录下的旧文件
    foreach ($subdir in @('bin', 'lib', 'logs')) {
        $subdirPath = Join-Path $InstallDir $subdir
        if (Test-Path $subdirPath) {
            Remove-Item -Recurse -Force $subdirPath -ErrorAction SilentlyContinue
        }
    }
    # 删除根目录下的旧文件（.bat, .pid 等），但保留 config.json 和 sessions.db
    Get-ChildItem -Path $InstallDir -File | Where-Object {
        $_.Name -notin @('config.json', 'sessions.db')
    } | Remove-Item -Force -ErrorAction SilentlyContinue
}
New-Item -ItemType Directory -Force $InstallDir\bin, $InstallDir\lib\adapters, $InstallDir\lib\utils, $LogDir | Out-Null

$files = @(
    "bin/feishu-receiver",
    "bin/feishu-receiver.ps1",
    "lib/feishu-receiver.py",
    "lib/config_manager.py",
    "lib/session_manager.py",
    "lib/message_processor.py",
    "lib/logger.py",
    "lib/adapters/__init__.py",
    "lib/adapters/base.py",
    "lib/adapters/claude.py",
    "lib/adapters/codex.py",
    "lib/adapters/opencode.py",
    "lib/card_builder.py",
    "lib/card_action_handler.py",
    "lib/utils/__init__.py",
    "lib/utils/command.py"
)

foreach ($file in $files) {
    $url = "$RawBase/$file"
    $outFile = Join-Path $InstallDir $file
    $downloaded = $false
    for ($retry = 1; $retry -le 3; $retry++) {
        try {
            Invoke-WebRequest -Uri $url -OutFile $outFile
            $downloaded = $true
            break
        } catch {
            if ($retry -lt 3) {
                Write-Host "  下载失败，重试 ($retry/3): $file" -ForegroundColor Yellow
                Start-Sleep -Seconds 2
            } else {
                Write-Host "  错误: 下载失败 $file - $_" -ForegroundColor Red
                exit 1
            }
        }
    }
}

Write-Host '==> 创建命令入口...'
# 创建 .bat 入口
$batContent = @"
@echo off
setlocal
set "SCRIPT_DIR=%~dp0"
set "PS_SCRIPT=%SCRIPT_DIR%bin\feishu-receiver.ps1"
where pwsh.exe >nul 2>&1
if %errorlevel% equ 0 (
    pwsh -ExecutionPolicy Bypass -File "%PS_SCRIPT%" %*
    goto :done
)
powershell -ExecutionPolicy Bypass -File "%PS_SCRIPT%" %*
:done
"@
[System.IO.File]::WriteAllText("$InstallDir\feishu-receiver.bat", $batContent)

Write-Host '==> 添加 PATH...'
$userPath = [Environment]::GetEnvironmentVariable('PATH', 'User')
if ($userPath -notlike "*$InstallDir*") {
    if ($userPath) {
        $newPath = $userPath + ';' + $InstallDir
    } else {
        $newPath = $InstallDir
    }
    # 使用 .NET API 设置 PATH（避免 setx 1024 字符截断）
    [Environment]::SetEnvironmentVariable('PATH', $newPath, 'User')
    Write-Host '  已添加到用户 PATH'
} else {
    Write-Host '  已在 PATH 中'
}
# 更新当前会话 PATH
if ($env:Path -notlike "*$InstallDir*") {
    $env:Path = $env:Path + ';' + $InstallDir
}

Write-Host ''
Write-Host '========================================' -ForegroundColor Green
Write-Host '安装完成！' -ForegroundColor Green
Write-Host '========================================' -ForegroundColor Green
Write-Host "安装目录: $InstallDir"
Write-Host ''
Write-Host '接下来请运行配置向导 (新终端窗口):'
Write-Host ''
Write-Host '  feishu-receiver setup'
Write-Host ''
Write-Host '其他命令: feishu-receiver <start|stop|status|restart|foreground>'
Write-Host '========================================' -ForegroundColor Green
