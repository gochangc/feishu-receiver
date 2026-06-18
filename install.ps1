# 飞书消息接收服务 - PowerShell 安装脚本
# 用法: irm https://raw.githubusercontent.com/gochangc/feishu-receiver/main/install.ps1 | iex

$ErrorActionPreference = 'Stop'

$InstallDir = "$env:USERPROFILE\.feishu-receiver"
$LogDir = "$InstallDir\logs"
$RawBase = 'https://raw.githubusercontent.com/gochangc/feishu-receiver/main'

if ($env:FEISHU_RECEIVER_WORKDIR) {
    $WorkDir = $env:FEISHU_RECEIVER_WORKDIR
} else {
    $WorkDir = "$env:USERPROFILE\workspace"
}

Write-Host '==> 检查依赖...' -ForegroundColor Cyan
foreach ($cmd in @('python3', 'lark-cli', 'claude')) {
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
if (Test-Path $InstallDir) {
    Remove-Item -Recurse -Force $InstallDir
}
New-Item -ItemType Directory -Force $InstallDir\bin, $InstallDir\lib, $LogDir 2>$null | Out-Null
Invoke-WebRequest -Uri "$RawBase/bin/feishu-receiver" -OutFile "$InstallDir\bin\feishu-receiver"
Invoke-WebRequest -Uri "$RawBase/bin/feishu-receiver.bat" -OutFile "$InstallDir\bin\feishu-receiver.bat"
Invoke-WebRequest -Uri "$RawBase/lib/feishu-receiver.py" -OutFile "$InstallDir\lib\feishu-receiver.py"

Write-Host '==> 创建命令入口...'
Copy-Item "$InstallDir\bin\feishu-receiver.bat" "$InstallDir\feishu-receiver.bat"

Write-Host '==> 添加 PATH...'
$userPath = [Environment]::GetEnvironmentVariable('PATH', 'User')
if ($userPath -notlike "*$InstallDir*") {
    if ($userPath) {
        $newPath = $userPath + ';' + $InstallDir
    } else {
        $newPath = $InstallDir
    }
    cmd /c "setx PATH `"$newPath`" 2>nul"
    Write-Host '  已添加到用户 PATH'
} else {
    Write-Host '  已在 PATH 中'
}

Write-Host ''
Write-Host '========================================' -ForegroundColor Green
Write-Host '安装完成！' -ForegroundColor Green
Write-Host '========================================' -ForegroundColor Green
Write-Host "安装目录: $InstallDir"
Write-Host "日志目录: $LogDir"
Write-Host "工作目录: $WorkDir"
Write-Host ''
Write-Host '接下来请运行配置向导 (新终端窗口):'
Write-Host ''
Write-Host '  feishu-receiver setup'
Write-Host ''
Write-Host '其他命令: feishu-receiver <start|stop|status|restart|foreground>'
Write-Host "卸载: 删除 $InstallDir 并从 PATH 移除即可"
Write-Host '========================================' -ForegroundColor Green