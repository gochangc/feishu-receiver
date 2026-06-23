# feishu-receiver.ps1
# 飞书消息接收服务 - Windows PowerShell 主控脚本
# 用法: feishu-receiver <命令>

param(
    [Parameter(Position=0)]
    [string]$Command = "help",
    [switch]$h,
    [switch]$help
)

# 处理帮助标志
if ($h -or $help -or $Command -eq "--help") {
    $Command = "help"
}

$ErrorActionPreference = "Stop"

# 安装目录 = 数据目录（代码、配置、日志等都在这里）
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$InstallDir = Split-Path -Parent $ScriptDir
$LibDir = Join-Path $InstallDir "lib"
$ConfigFile = Join-Path $InstallDir "config.json"
$PidFile = Join-Path $InstallDir "feishu-receiver.pid"

# 检测 Python（验证命令真正可用，排除 Windows Store 占位符）
function Find-Python {
    foreach ($py in @("python3", "python")) {
        $cmd = Get-Command $py -ErrorAction SilentlyContinue
        if ($cmd) {
            try {
                $version = & $py --version 2>&1
                if ($LASTEXITCODE -eq 0) {
                    return $cmd.Source
                }
            } catch {
                continue
            }
        }
    }
    Write-Host "错误: Python 未找到" -ForegroundColor Red
    exit 1
}

$Python = Find-Python

# 加载配置
function Get-Config {
    if (Test-Path $ConfigFile) {
        $config = Get-Content $ConfigFile -Raw -Encoding UTF8 | ConvertFrom-Json
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

用法: feishu-receiver <命令>

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

function Invoke-Setup {
    Write-Host "========================================"
    Write-Host "  飞书消息接收服务 - 配置向导"
    Write-Host "========================================"
    Write-Host ""

    # 检查依赖
    Write-Host "==> 检查依赖..."
    $missing = @()
    foreach ($cmd in @("python", "lark-cli")) {
        if (-not (Get-Command $cmd -ErrorAction SilentlyContinue)) {
            Write-Host "  错误: $cmd 未找到" -ForegroundColor Red
            $missing += $cmd
        }
    }
    if ($missing.Count -gt 0) {
        Write-Host "请先安装: $($missing -join ', ')" -ForegroundColor Red
        exit 1
    }
    Write-Host "  依赖检查通过"
    Write-Host ""

    # 飞书应用配置
    Write-Host "==> 飞书应用配置"
    Write-Host "  需要从飞书开放平台获取 App ID 和 App Secret"
    Write-Host "  申请地址: https://open.feishu.cn/app"
    Write-Host ""
    Write-Host "  请确认已在飞书开放平台完成以下配置:"
    Write-Host ""
    Write-Host "  1. 开通应用权限:"
    Write-Host "     - im:message                   (发送消息)"
    Write-Host "     - im:message.p2p_msg:readonly  (读取私聊消息)"
    Write-Host ""
    Write-Host "  2. 配置事件订阅:"
    Write-Host "     - 添加事件: im.message.receive_v1 (接收消息)"
    Write-Host ""
    Write-Host "  3. 启用机器人能力:"
    Write-Host "     - 进入 应用能力 > 机器人 > 启用"
    Write-Host ""

    $appId = Read-Host "  请输入 App ID"
    $appSecret = Read-Host "  请输入 App Secret" -AsSecureString
    $appSecretPlain = [Runtime.InteropServices.Marshal]::PtrToStringAuto(
        [Runtime.InteropServices.Marshal]::SecureStringToBSTR($appSecret)
    )

    # 配置 lark-cli
    if ($appId -and $appSecretPlain) {
        $appSecretPlain | lark-cli config init --app-id $appId --app-secret-stdin --brand feishu
        Write-Host "  lark-cli 配置完成"
    }
    Write-Host ""

    # 配置 AI 工具
    Write-Host "==> AI 工具配置"
    Write-Host "  可选: claude, codex, opencode"
    $aiTool = Read-Host "  默认 AI 工具 (默认: claude)"
    if (-not $aiTool) { $aiTool = "claude" }

    if (-not (Get-Command $aiTool -ErrorAction SilentlyContinue)) {
        Write-Host "  警告: $aiTool 未找到，请确保已安装" -ForegroundColor Yellow
    }

    $aiTimeout = Read-Host "  超时秒数 (默认: 300)"
    if (-not $aiTimeout) { $aiTimeout = 300 }
    Write-Host ""

    # 工作目录
    Write-Host "==> 工作目录配置"
    $workDir = Read-Host "  工作目录 (默认: $env:USERPROFILE\workspace)"
    if (-not $workDir) { $workDir = Join-Path $env:USERPROFILE "workspace" }
    Write-Host ""

    # 会话配置
    Write-Host "==> 会话配置"
    $sessionInput = Read-Host "  启用会话模式? (Y/n)"
    $sessionEnabled = "true"
    if ($sessionInput -match "^[Nn]") { $sessionEnabled = "false" }

    $maxHistory = Read-Host "  最大会话历史条数 (默认: 50)"
    if (-not $maxHistory) { $maxHistory = 50 }

    $autoSummarizeInput = Read-Host "  达到上限时自动总结? (Y/n)"
    $autoSummarize = "true"
    if ($autoSummarizeInput -match "^[Nn]") { $autoSummarize = "false" }
    Write-Host ""

    # 日志配置
    Write-Host "==> 日志配置"
    Write-Host "  可选: DEBUG, INFO, WARNING, ERROR"
    $logLevel = Read-Host "  日志级别 (默认: INFO)"
    if (-not $logLevel) { $logLevel = "INFO" }
    Write-Host ""

    # 写入配置文件
    New-Item -ItemType Directory -Force $InstallDir | Out-Null
    $config = @{
        feishu = @{
            app_id = $appId
            app_secret = $appSecretPlain
            bot_name = "我的飞书机器人"
        }
        ai_tool = @{
            default = $aiTool
            timeout = [int]$aiTimeout
        }
        session = @{
            enabled = [System.Convert]::ToBoolean($sessionEnabled)
            max_history = [int]$maxHistory
            timeout = 3600
            auto_summarize = [System.Convert]::ToBoolean($autoSummarize)
        }
        workdir = $workDir
        logging = @{
            level = $logLevel
            file = "logs/feishu-receiver.log"
            max_size_mb = 10
            backup_count = 5
        }
    }
    $config | ConvertTo-Json -Depth 5 | Set-Content -Path $ConfigFile -Encoding UTF8
    Write-Host "==> 配置已保存到: $ConfigFile"
    Write-Host ""

    # 验证
    Write-Host "==> 验证配置..."
    Write-Host "  工作目录 : $workDir"
    Write-Host "  AI 工具  : $aiTool"
    Write-Host "  会话模式 : $sessionEnabled"
    Write-Host "  自动总结 : $autoSummarize"
    Write-Host "  日志级别 : $logLevel"
    Write-Host ""

    Write-Host "========================================"
    Write-Host "配置完成！"
    Write-Host ""
    Write-Host "启动服务: feishu-receiver start"
    Write-Host "========================================"
}

function Start-FeishuService {
    $config = Get-Config

    if (Test-Path $PidFile) {
        $svcPid = Get-Content $PidFile
        $proc = Get-Process -Id $svcPid -ErrorAction SilentlyContinue
        if ($proc) {
            Write-Host "服务已在运行中 (PID: $svcPid)"
            return
        }
        Remove-Item $PidFile
    }

    Write-Host "==> 启动飞书消息接收服务..."
    $logDir = Join-Path $InstallDir "logs"
    New-Item -ItemType Directory -Force $logDir | Out-Null

    $scriptPath = Join-Path $LibDir "feishu-receiver.py"
    $logFile = Join-Path $logDir "feishu-receiver.log"

    $env:PYTHONPATH = $InstallDir
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
        Write-Host "服务启动失败" -ForegroundColor Red
        # 读取错误日志，显示具体原因
        $errorLog = Join-Path $logDir "feishu-receiver-error.log"
        if (Test-Path $errorLog) {
            $lastLines = Get-Content $errorLog -Tail 10 -ErrorAction SilentlyContinue
            if ($lastLines) {
                Write-Host ""
                Write-Host "--- 错误日志 ---" -ForegroundColor Yellow
                $lastLines | ForEach-Object { Write-Host $_ }
                Write-Host "--- 日志文件: $errorLog ---" -ForegroundColor Yellow
            }
        }
        Remove-Item $PidFile -ErrorAction SilentlyContinue
        exit 1
    }
}

function Stop-FeishuService {
    if (-not (Test-Path $PidFile)) {
        Write-Host "服务未运行 (找不到 PID 文件)"
        return
    }

    $svcPid = Get-Content $PidFile
    $proc = Get-Process -Id $svcPid -ErrorAction SilentlyContinue

    if (-not $proc) {
        Write-Host "服务未运行 (PID: $svcPid 已不存在)"
        Remove-Item $PidFile
        return
    }

    Write-Host "==> 停止飞书消息接收服务 (PID: $svcPid)..."
    Stop-Process -Id $svcPid -Force -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 2

    # 清理残留的 lark-cli 事件监听进程
    $larkPids = Get-CimInstance Win32_Process -Filter "Name='lark-cli.exe'" -ErrorAction SilentlyContinue |
        Where-Object { $_.CommandLine -match 'event.*consume' } |
        Select-Object -ExpandProperty ProcessId
    foreach ($lp in $larkPids) {
        Stop-Process -Id $lp -Force -ErrorAction SilentlyContinue
    }

    Remove-Item $PidFile -ErrorAction SilentlyContinue
    Write-Host "服务已停止"
}

function Get-Status {
    if (-not (Test-Path $PidFile)) {
        Write-Host "状态: 未运行"
        return
    }

    $svcPid = Get-Content $PidFile
    $proc = Get-Process -Id $svcPid -ErrorAction SilentlyContinue

    if ($proc) {
        Write-Host "状态: 运行中 (PID: $svcPid)"
    } else {
        Write-Host "状态: 未运行 (PID 文件残留: $svcPid)"
    }
}

function Restart-FeishuService {
    Stop-FeishuService
    Start-Sleep -Seconds 1
    Start-FeishuService
}

function Start-Foreground {
    $config = Get-Config
    Write-Host "==> 前台启动飞书消息接收服务 (按 Ctrl+C 停止)..."
    Set-Location $config.WorkDir
    $env:PYTHONPATH = $InstallDir
    & $Python (Join-Path $LibDir "feishu-receiver.py")
}

function Invoke-Uninstall {
    Write-Host "==> 卸载飞书消息接收服务..."

    # 停止服务
    if (Test-Path $PidFile) {
        $svcPid = Get-Content $PidFile
        Stop-Process -Id $svcPid -Force -ErrorAction SilentlyContinue
        Remove-Item $PidFile -ErrorAction SilentlyContinue
    }

    # 删除安装目录（代码、配置、日志等）
    Write-Host "==> 清理安装文件..."
    Remove-Item -Recurse -Force $InstallDir -ErrorAction SilentlyContinue

    Write-Host ""
    Write-Host "卸载完成！"
    Write-Host "已删除: $InstallDir"
}

# 主逻辑
switch ($Command) {
    "start"       { Start-FeishuService }
    "stop"        { Stop-FeishuService }
    "status"      { Get-Status }
    "restart"     { Restart-FeishuService }
    "foreground"  { Start-Foreground }
    "setup"       { Invoke-Setup }
    "uninstall"   { Invoke-Uninstall }
    "help"        { Show-Help }
    default       { Write-Host "未知命令: $Command"; Show-Help; exit 1 }
}
