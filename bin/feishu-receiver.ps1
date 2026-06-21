# feishu-receiver.ps1
# 飞书消息接收服务 - Windows PowerShell 主控脚本
# 用法: .\feishu-receiver.ps1 <命令>

param(
    [Parameter(Position=0)]
    [string]$Command = "help"
)

$ErrorActionPreference = "Stop"

# 路径配置
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$BaseDir = Split-Path -Parent $ScriptDir
$LibDir = Join-Path $BaseDir "lib"
$ConfigFile = Join-Path $BaseDir "config.json"
$PidFile = Join-Path $BaseDir "feishu-receiver.pid"

# 检测 Python
function Find-Python {
    foreach ($py in @("python3", "python")) {
        $cmd = Get-Command $py -ErrorAction SilentlyContinue
        if ($cmd) {
            return $cmd.Source
        }
    }
    Write-Host "错误: Python 未找到" -ForegroundColor Red
    exit 1
}

$Python = Find-Python

# 加载配置
function Get-Config {
    if (Test-Path $ConfigFile) {
        $config = Get-Content $ConfigFile -Raw | ConvertFrom-Json
        return @{
            WorkDir = $config.workdir
            BotName = $config.feishu.bot_name
        }
    }
    return @{
        WorkDir = Join-Path $env:USERPROFILE "workspace"
        BotName = "我的飞书机器人"
    }
}

function Show-Help {
    Write-Host @"
飞书消息接收服务 - PowerShell 主控脚本

用法: .\feishu-receiver.ps1 <命令>

命令:
  start       后台启动服务
  stop        停止服务
  status      查看服务状态
  restart     重启服务
  foreground  前台运行（Ctrl+C 停止）
  setup       交互式配置向导
  uninstall   卸载服务
  help        显示此帮助信息

配置: $ConfigFile
"@
}

function Start-Service {
    $config = Get-Config

    if (Test-Path $PidFile) {
        $pid = Get-Content $PidFile
        $proc = Get-Process -Id $pid -ErrorAction SilentlyContinue
        if ($proc) {
            Write-Host "服务已在运行中 (PID: $pid)"
            return
        }
        Remove-Item $PidFile
    }

    Write-Host "==> 启动飞书消息接收服务..."
    $logDir = Join-Path $BaseDir "logs"
    New-Item -ItemType Directory -Force $logDir | Out-Null

    $scriptPath = Join-Path $LibDir "feishu-receiver.py"
    $logFile = Join-Path $logDir "feishu-receiver.log"

    $proc = Start-Process -FilePath $Python -ArgumentList $scriptPath `
        -WindowStyle Hidden `
        -RedirectStandardOutput $logFile `
        -RedirectStandardError (Join-Path $logDir "feishu-receiver-error.log") `
        -PassThru

    $proc.Id | Out-File -FilePath $PidFile -Encoding ascii
    Start-Sleep -Seconds 1

    $checkProc = Get-Process -Id $proc.Id -ErrorAction SilentlyContinue
    if ($checkProc) {
        Write-Host "服务已启动 (PID: $($proc.Id))"
        Write-Host "日志: Get-Content $logFile -Wait"
    } else {
        Write-Host "服务启动失败，请查看日志" -ForegroundColor Red
        Remove-Item $PidFile -ErrorAction SilentlyContinue
        exit 1
    }
}

function Stop-Service {
    if (-not (Test-Path $PidFile)) {
        Write-Host "服务未运行 (找不到 PID 文件)"
        return
    }

    $pid = Get-Content $PidFile
    $proc = Get-Process -Id $pid -ErrorAction SilentlyContinue

    if (-not $proc) {
        Write-Host "服务未运行 (PID: $pid 已不存在)"
        Remove-Item $PidFile
        return
    }

    Write-Host "==> 停止飞书消息接收服务 (PID: $pid)..."
    Stop-Process -Id $pid -Force -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 2

    Remove-Item $PidFile -ErrorAction SilentlyContinue
    Write-Host "服务已停止"
}

function Get-Status {
    if (-not (Test-Path $PidFile)) {
        Write-Host "状态: 未运行"
        return
    }

    $pid = Get-Content $PidFile
    $proc = Get-Process -Id $pid -ErrorAction SilentlyContinue

    if ($proc) {
        Write-Host "状态: 运行中 (PID: $pid)"
    } else {
        Write-Host "状态: 未运行 (PID 文件残留: $pid)"
    }
}

function Restart-Service {
    Stop-Service
    Start-Sleep -Seconds 1
    Start-Service
}

function Start-Foreground {
    $config = Get-Config
    Write-Host "==> 前台启动飞书消息接收服务 (按 Ctrl+C 停止)..."
    Set-Location $config.WorkDir
    & $Python (Join-Path $LibDir "feishu-receiver.py")
}

function Invoke-Uninstall {
    Write-Host "==> 卸载飞书消息接收服务..."

    # 停止服务
    if (Test-Path $PidFile) {
        $pid = Get-Content $PidFile
        Stop-Process -Id $pid -Force -ErrorAction SilentlyContinue
        Remove-Item $PidFile -ErrorAction SilentlyContinue
    }

    # 删除文件
    Write-Host "==> 清理文件..."
    Remove-Item -Recurse -Force (Join-Path $BaseDir "lib") -ErrorAction SilentlyContinue
    Remove-Item -Recurse -Force (Join-Path $BaseDir "logs") -ErrorAction SilentlyContinue
    Remove-Item -Recurse -Force (Join-Path $BaseDir "bin") -ErrorAction SilentlyContinue

    Write-Host ""
    Write-Host "卸载完成！"
    Write-Host "配置文件保留在: $ConfigFile"
}

# 主逻辑
switch ($Command) {
    "start"       { Start-Service }
    "stop"        { Stop-Service }
    "status"      { Get-Status }
    "restart"     { Restart-Service }
    "foreground"  { Start-Foreground }
    "setup"       { Write-Host "请运行: feishu-receiver setup" }
    "uninstall"   { Invoke-Uninstall }
    "help"        { Show-Help }
    default       { Write-Host "未知命令: $Command"; Show-Help; exit 1 }
}
